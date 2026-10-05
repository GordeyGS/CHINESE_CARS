import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class QueryType(StrEnum):
    WORD = "WORD"
    PHRASE = "PHRASE"
    SENTENCE = "SENTENCE"


class QueryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedQuery:
    original: str
    normalized: str
    query_type: QueryType
    terms: tuple[str, ...]
    phrase_candidates: tuple[str, ...]

    @property
    def search_text(self) -> str:
        return " ".join(self.terms)


class QueryParser:
    MAX_LENGTH = 300
    SENTENCE_TOKEN_THRESHOLD = 5
    TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
    SENTENCE_END_RE = re.compile(r"[.!?…]\s*$")
    LATIN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")

    # Short, explicit list: PostgreSQL performs morphology; the application only
    # removes question scaffolding that carries no automotive meaning.
    STOP_WORDS = {
        "а",
        "без",
        "в",
        "во",
        "для",
        "и",
        "из",
        "или",
        "использует",
        "используют",
        "какие",
        "какой",
        "как",
        "на",
        "о",
        "об",
        "по",
        "с",
        "со",
        "у",
        "что",
        "это",
    }

    def parse(self, raw_query: str | None) -> ParsedQuery:
        original = "" if raw_query is None else str(raw_query)
        normalized = " ".join(unicodedata.normalize("NFKC", original).split())
        if not normalized:
            raise QueryValidationError("Введите поисковый запрос.")
        if len(normalized) > self.MAX_LENGTH:
            raise QueryValidationError(f"Запрос должен быть не длиннее {self.MAX_LENGTH} символов.")

        tokens = tuple(self.TOKEN_RE.findall(normalized))
        if not tokens:
            raise QueryValidationError("Запрос должен содержать буквы или цифры.")

        if len(tokens) == 1:
            query_type = QueryType.WORD
        elif self.SENTENCE_END_RE.search(normalized) or len(tokens) >= self.SENTENCE_TOKEN_THRESHOLD:
            query_type = QueryType.SENTENCE
        else:
            query_type = QueryType.PHRASE

        terms = tuple(token for token in tokens if token.casefold() not in self.STOP_WORDS)
        if not terms:
            terms = tokens

        phrases: list[str] = []
        if query_type is QueryType.PHRASE:
            phrases.append(" ".join(tokens))
        elif query_type is QueryType.SENTENCE:
            latin_run: list[str] = []
            for token in tokens + ("",):
                if self.LATIN_RE.match(token):
                    latin_run.append(token)
                    continue
                if len(latin_run) >= 2:
                    phrases.append(" ".join(latin_run))
                latin_run = []

        return ParsedQuery(
            original=original,
            normalized=normalized,
            query_type=query_type,
            terms=terms,
            phrase_candidates=tuple(dict.fromkeys(phrases)),
        )
