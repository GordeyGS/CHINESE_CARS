"""Deterministic query correction ("did you mean" / "showing results for").

The corrector works word by word, so a sentence keeps its correct words and only the
misspelled ones change. For every word it tries three explicit rules, in this order:

1. **Russian spelling of a brand** from a fixed table: «зикр» -> Zeekr, «джили» -> Geely.
2. **Wrong keyboard layout**: «инв» typed on the Russian layout is "byd" -> BYD.
3. **Typo**: the closest word of the knowledge-base vocabulary by
   ``difflib.SequenceMatcher`` (standard library), if it is similar enough.
   A Russian word that is not close to any Russian word is also transliterated and
   compared with Latin names («тигго» -> Tiggo); a word in the wrong layout may
   additionally contain a typo.

The vocabulary is built from the database (names of brands, models, technologies and
titles of published articles) plus a short glossary of domain words. Every change is
returned with its reason, so the interface can explain what was corrected and why.
No external AI API or machine learning is used.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from apps.cars.models import Brand, Model as VehicleModel, Technology
from apps.knowledge.models import Article

from .query_parser import QueryParser


WORD_RE = re.compile(r"[\w&+-]+", re.UNICODE)
# In a query, keys that are letters on the Russian layout ("," = б, ";" = ж, "[" = х ...)
# may stand inside a word typed in the wrong layout: "ktrnhjvj,bkm".
QUERY_WORD_RE = re.compile(r"[\w&+-]+(?:[\[\];',.`][\w&+-]+)*", re.UNICODE)
CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)

# Russian spellings of brands and technologies (lower case) -> name in the knowledge base.
RUSSIAN_SPELLINGS = {
    "бид": "BYD", "бяд": "BYD", "биуайди": "BYD", "бивайди": "BYD",
    "зикр": "Zeekr", "зекр": "Zeekr", "зикер": "Zeekr", "зеекр": "Zeekr",
    "джили": "Geely", "джилли": "Geely", "гели": "Geely", "жили": "Geely",
    "чери": "Chery", "черри": "Chery",
    "нио": "NIO",
    "сяоми": "Xiaomi", "шаоми": "Xiaomi", "ксиаоми": "Xiaomi", "ксяоми": "Xiaomi",
    "хунци": "Hongqi", "хончи": "Hongqi", "хонгки": "Hongqi", "хонгчи": "Hongqi",
    "икспенг": "XPeng", "сяопэн": "XPeng", "хпенг": "XPeng",
    "липмотор": "Leapmotor", "липмоторс": "Leapmotor",
    "хавал": "Haval", "хавейл": "Haval", "хавэйл": "Haval",
    "дипал": "Deepal",
    "омода": "Omoda",
    "блейд": "Blade",
}

# Domain words that are not names but appear in typical questions.
GLOSSARY = (
    "электромобиль", "электромобили", "гибрид", "гибридный", "кроссовер", "седан", "внедорожник",
    "минивэн", "хэтчбек", "батарея", "аккумулятор", "запас", "хода", "мощность", "мощный", "разгон",
    "скорость", "быстрый", "зарядка", "платформа", "привод", "полный", "задний", "передний", "самый",
    "самая", "самое", "лучший", "дешёвый", "китайский", "автомобиль", "машина", "двигатель", "мотор",
    "технология", "обзор", "видео", "сравнение", "цена", "расход", "багажник",
)

# Similarity threshold of SequenceMatcher.ratio(). Cyrillic words are longer and
# inflected, so the bar is higher to avoid "correcting" a valid word form.
LATIN_THRESHOLD = 0.75
CYRILLIC_THRESHOLD = 0.82
MIN_LATIN_LENGTH = 3
MIN_CYRILLIC_LENGTH = 5
MIN_TRANSLIT_LENGTH = 4

# Simple transliteration used only to compare a Russian-spelled name with Latin names.
TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})

_RU = "йцукенгшщзхъфывапролджэячсмитьбю"
_EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,."
RU_TO_EN = str.maketrans(_RU + _RU.upper(), _EN + _EN.upper())
EN_TO_RU = str.maketrans(_EN + _EN.upper(), _RU + _RU.upper())


@dataclass(frozen=True)
class WordCorrection:
    original: str
    replacement: str
    reason: str


@dataclass(frozen=True)
class QueryCorrection:
    original: str
    corrected: str
    changes: tuple[WordCorrection, ...]

    @property
    def explanation(self) -> str:
        return "; ".join(f"«{change.original}» → «{change.replacement}» ({change.reason})" for change in self.changes)


def _is_cyrillic(word: str) -> bool:
    return bool(CYRILLIC_RE.search(word))


def build_vocabulary() -> dict[str, str]:
    """Lower-case word -> word as written in the knowledge base (keeps "BYD", "XPeng")."""
    texts = [
        *Brand.objects.filter(is_active=True).values_list("name", flat=True),
        *VehicleModel.objects.filter(is_active=True).values_list("name", flat=True),
        *Technology.objects.filter(is_active=True).values_list("name", flat=True),
        *Article.objects.filter(status=Article.Status.PUBLISHED).values_list("title", flat=True),
        *GLOSSARY,
        *QueryParser.STOP_WORDS,
    ]
    vocabulary = {}
    for text in texts:
        for word in WORD_RE.findall(text):
            vocabulary.setdefault(word.casefold(), word)
    return vocabulary


class QueryCorrector:
    def __init__(self, vocabulary: dict[str, str] | None = None):
        self.vocabulary = vocabulary if vocabulary is not None else build_vocabulary()
        self._latin = sorted(word for word in self.vocabulary if not _is_cyrillic(word))
        self._cyrillic = sorted(word for word in self.vocabulary if _is_cyrillic(word))

    def correct(self, raw_query: str) -> QueryCorrection | None:
        query = " ".join((raw_query or "").split())
        changes = []

        def replace(match):
            word = match.group(0)
            correction = self.correct_word(word)
            if correction is None:
                return word
            changes.append(correction)
            return correction.replacement

        corrected = QUERY_WORD_RE.sub(replace, query)
        if not changes or corrected.casefold() == query.casefold():
            return None
        return QueryCorrection(original=query, corrected=corrected, changes=tuple(changes))

    def correct_word(self, word: str) -> WordCorrection | None:
        key = word.casefold()
        if key in self.vocabulary or key.isdigit() or len(key) < 2:
            return None

        if key in RUSSIAN_SPELLINGS:
            return WordCorrection(word, RUSSIAN_SPELLINGS[key], "русское написание")

        switched = key.translate(RU_TO_EN if _is_cyrillic(key) else EN_TO_RU)
        if switched in self.vocabulary:
            return WordCorrection(word, self.vocabulary[switched], "неверная раскладка")

        if _is_cyrillic(key):
            if self._has_known_stem(key):
                return None
            if len(key) >= MIN_CYRILLIC_LENGTH:
                match = self._closest(key, self._cyrillic, CYRILLIC_THRESHOLD)
                if match:
                    return WordCorrection(word, self.vocabulary[match], "опечатка")
            # A Latin model name typed in Russian letters: «тигго» -> Tiggo, «монжаро» -> Monjaro.
            transliterated = key.replace("дж", "j").translate(TRANSLIT)
            if len(key) >= MIN_TRANSLIT_LENGTH and transliterated.isalpha():
                match = self._closest(transliterated, self._latin, LATIN_THRESHOLD)
                if match:
                    return WordCorrection(word, self.vocabulary[match], "написано по-русски")
        elif len(key) >= MIN_LATIN_LENGTH and WORD_RE.fullmatch(key) and key.isalpha():
            match = self._closest(key, self._latin, LATIN_THRESHOLD)
            if match:
                return WordCorrection(word, self.vocabulary[match], "опечатка")

        # Wrong layout and a typo at the same time: «ktrnhjvj,bkm» -> «лектромобиль» -> электромобиль.
        if len(switched) >= MIN_CYRILLIC_LENGTH and switched.replace("'", "").isalpha():
            pool, threshold = (self._cyrillic, CYRILLIC_THRESHOLD) if _is_cyrillic(switched) else (
                self._latin, LATIN_THRESHOLD)
            match = self._closest(switched, pool, threshold)
            if match:
                return WordCorrection(word, self.vocabulary[match], "неверная раскладка")
        return None

    def _has_known_stem(self, key: str) -> bool:
        """A different ending of a known word ("электромобилями") is not a typo: FTS handles it."""
        stem = key[: max(4, len(key) - 3)]
        return any(word.startswith(stem) for word in self._cyrillic)

    @staticmethod
    def _closest(key: str, candidates: list[str], threshold: float) -> str | None:
        best, best_ratio = None, threshold
        for candidate in candidates:
            if abs(len(candidate) - len(key)) > 3:
                continue
            ratio = SequenceMatcher(None, key, candidate).ratio()
            # Strictly greater: on equal similarity the alphabetically first word wins.
            if ratio > best_ratio or (best is None and ratio == best_ratio):
                best, best_ratio = candidate, ratio
        return best

    def complete_prefix(self, prefix: str) -> str | None:
        """For autocomplete while typing: a Latin name typed on the Russian layout
        ("яуу" -> "zee"), if it looks like the start of a known Latin word.

        Only the Russian -> Latin direction is used here: brand and model names are
        Latin, and a short Latin prefix converted to Cyrillic would match too many words.
        """
        key = " ".join(prefix.split()).casefold()
        if not key or not _is_cyrillic(key):
            return None
        switched = key.translate(RU_TO_EN)
        if _is_cyrillic(switched):
            return None
        last = switched.split()[-1]
        if any(word.startswith(last) for word in self._latin):
            return switched
        return None
