"""Import of car models from the open Wikidata knowledge graph (with Wikipedia intros).

Wikidata is used only as a read-only source of *entities*: which models a brand
produces, their names, short descriptions, photos and discontinuation. Technical
characteristics of modifications are not taken from it, because for Chinese cars
they are mostly absent there and are entered manually from official sources.

The import is deterministic: every candidate passes the same explicit rules, and
every skipped candidate gets a human-readable reason in the report.

Licences: Wikidata statements are CC0. Photos are Wikimedia Commons files under
their own free licences, so the author and licence are stored in ``image_credit``.
Descriptions are the introductions of Wikipedia articles (CC BY-SA 4.0): the article
link and licence are stored in ``description_source_url`` / ``description_credit``.
"""

import html
import json
import re
import socket
import time
from dataclasses import dataclass, field
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils.text import slugify

from apps.cars.models import Brand, Model


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/{qid}"
USER_AGENT = "china-auto-kb-course-project/1.0 (educational knowledge base)"
MAX_RESPONSE_BYTES = 10_000_000
COMMONS_BATCH_SIZE = 50
WIKIPEDIA_API_ENDPOINT = "https://{language}.wikipedia.org/w/api.php"
WIKIPEDIA_ARTICLE_URL = "https://{language}.wikipedia.org/wiki/{title}"
# The extracts API returns at most 20 intros per request.
WIKIPEDIA_BATCH_SIZE = 20
# Wikimedia APIs answer 429 with Retry-After when a client is too fast; we wait and retry.
MAX_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 30
MAX_DESCRIPTION_CHARS = 1200
MIN_DESCRIPTION_CHARS = 40
IMAGE_WIDTH_PX = 960

# Wikidata class "automobile model" (Q3231690).
AUTOMOBILE_MODEL_QID = "Q3231690"

# Brand in the knowledge base -> (Wikidata items that stand for it, label prefixes).
# Items were chosen by hand: a brand item (BYD Auto) and, where Wikidata splits it,
# the company item that is used as "manufacturer" of the same cars (Geely Auto + Geely).
# The label prefix is the brand name as written at the start of English labels:
# "Li Auto L9" and "Li L6" both belong to Li Auto.
WIKIDATA_BRANDS = {
    "BYD": (("Q27423",), ("BYD",)),
    "Zeekr": (("Q106621124",), ("Zeekr",)),
    "Geely": (("Q739000", "Q55118127"), ("Geely",)),
    "Chery": (("Q591001", "Q98172997"), ("Chery",)),
    "Li Auto": (("Q98139925",), ("Li Auto", "Li")),
    "NIO": (("Q29921278",), ("NIO", "Nio")),
    "Xiaomi": (("Q123574937",), ("Xiaomi",)),
    "Hongqi": (("Q1611731",), ("Hongqi",)),
    "XPeng": (("Q63035278",), ("XPeng", "Xpeng")),
    "Leapmotor": (("Q99510294",), ("Leapmotor",)),
    "Haval": (("Q28223947",), ("Haval",)),
    "Tank": (("Q106620909",), ("Tank",)),
    "Deepal": (("Q112874951",), ("Deepal",)),
    "Lynk & Co": (("Q27555283",), ("Lynk & Co",)),
    "Omoda": (("Q118646009",), ("Chery Omoda", "Omoda")),
}

# The same car is sold in China and abroad under different names. Wikidata has an
# item for the Chinese name, the knowledge base stores the export name; without this
# table the import would create a duplicate (brand, Wikidata name) -> existing name.
MARKET_TWINS = {
    ("Geely", "Galaxy E5"): "EX5",
    ("Geely", "Xingyue L"): "Monjaro",
    ("Geely", "Boyue L"): "Atlas",
    ("Geely", "Binyue"): "Coolray",
    ("Deepal", "S7"): "S07",
}

# The knowledge base describes passenger cars; Wikidata's "automobile model"
# also contains trucks, buses, concepts and prototypes. English entries are whole
# words, Russian entries are stems ("грузов" covers "грузовик", "грузовой").
EXCLUDED_WORDS = (
    "truck", "bus", "commercial", "concept", "prototype", "pre-production",
    "грузов", "автобус", "концепт", "прототип",
)

# Descriptions that carry no knowledge and are therefore not stored.
GENERIC_DESCRIPTIONS = {
    "motor vehicle", "car model", "motor car", "automobile model", "chinese car model",
    "chinese automobile", "легковой автомобиль", "китайский автомобиль", "модель автомобиля",
}


class WikidataError(RuntimeError):
    """A safe, human-readable failure of the Wikidata or Commons API."""


@dataclass(frozen=True)
class WikidataCar:
    qid: str
    label_en: str
    label_ru: str = ""
    description: str = ""
    brand_qids: frozenset[str] = frozenset()
    manufacturer_qids: frozenset[str] = frozenset()
    image_file: str = ""
    is_discontinued: bool = False
    # Titles of Wikipedia articles about the same car (Wikidata sitelinks).
    ru_article: str = ""
    en_article: str = ""

    @property
    def url(self):
        return ENTITY_URL.format(qid=self.qid)


@dataclass(frozen=True)
class CommonsImage:
    url: str
    credit: str


@dataclass(frozen=True)
class WikipediaIntro:
    text: str
    url: str
    credit: str


@dataclass
class ImportReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    images_found: int = 0
    descriptions_found: int = 0


# --- Wikidata / Commons HTTP client -------------------------------------------------


def build_sparql_query(owner_qids):
    """All automobile models whose brand (P1716) or manufacturer (P176) is one of the owners."""
    values = " ".join(f"wd:{qid}" for qid in sorted(owner_qids))
    return f"""
SELECT ?car ?labelEn ?labelRu ?descRu ?descEn ?brand ?maker ?image ?ended ?ruArticle ?enArticle WHERE {{
  VALUES ?owner {{ {values} }}
  {{ ?car wdt:P1716 ?owner }} UNION {{ ?car wdt:P176 ?owner }}
  ?car wdt:P31 wd:{AUTOMOBILE_MODEL_QID} .
  OPTIONAL {{ ?car wdt:P1716 ?brand }}
  OPTIONAL {{ ?car wdt:P176 ?maker }}
  OPTIONAL {{ ?car rdfs:label ?labelEn FILTER(LANG(?labelEn) = "en") }}
  OPTIONAL {{ ?car rdfs:label ?labelRu FILTER(LANG(?labelRu) = "ru") }}
  OPTIONAL {{ ?car schema:description ?descRu FILTER(LANG(?descRu) = "ru") }}
  OPTIONAL {{ ?car schema:description ?descEn FILTER(LANG(?descEn) = "en") }}
  OPTIONAL {{ ?car wdt:P18 ?image }}
  OPTIONAL {{ ?car wdt:P2669|wdt:P730|wdt:P582 ?ended }}
  OPTIONAL {{ ?ruPage schema:about ?car ; schema:isPartOf <https://ru.wikipedia.org/> ; schema:name ?ruArticle }}
  OPTIONAL {{ ?enPage schema:about ?car ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?enArticle }}
}}"""


def _entity_id(uri):
    return uri.rsplit("/", 1)[-1]


def parse_sparql_cars(payload):
    """Collapse SPARQL rows (one per combination of OPTIONAL values) into one car per item."""
    try:
        rows = payload["results"]["bindings"]
    except (KeyError, TypeError) as error:
        raise WikidataError("Wikidata вернула ответ неожиданного формата.") from error

    collected = {}
    for row in rows:
        def value(name):
            return row.get(name, {}).get("value", "")

        qid = _entity_id(value("car"))
        car = collected.setdefault(qid, {
            "qid": qid,
            "label_en": value("labelEn"),
            "label_ru": value("labelRu"),
            "description": value("descRu") or value("descEn"),
            "brand_qids": set(),
            "manufacturer_qids": set(),
            "image_file": "",
            "is_discontinued": False,
            "ru_article": value("ruArticle"),
            "en_article": value("enArticle"),
        })
        if value("brand"):
            car["brand_qids"].add(_entity_id(value("brand")))
        if value("maker"):
            car["manufacturer_qids"].add(_entity_id(value("maker")))
        if value("image") and not car["image_file"]:
            # P18 is returned as .../Special:FilePath/<file name>
            car["image_file"] = _commons_file_name(value("image"))
        if value("ended"):
            car["is_discontinued"] = True

    return [
        WikidataCar(
            **{**car, "brand_qids": frozenset(car["brand_qids"]),
               "manufacturer_qids": frozenset(car["manufacturer_qids"])}
        )
        for car in sorted(collected.values(), key=lambda item: item["qid"])
    ]


def _commons_file_name(file_path_url):
    return unquote(file_path_url.rsplit("/", 1)[-1]).replace("_", " ")


def _strip_html(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


def clean_intro(text):
    """Join the intro into one paragraph and cut it at a sentence end within the limit."""
    text = re.sub(r"\s+", " ", text or "").strip()
    # Wikipedia intros sometimes keep empty brackets left from removed pronunciations.
    text = re.sub(r"\s*\(\s*[,;]?\s*\)", "", text)
    if len(text) <= MAX_DESCRIPTION_CHARS:
        return text if len(text) >= MIN_DESCRIPTION_CHARS else ""
    cut = text[:MAX_DESCRIPTION_CHARS]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end >= MIN_DESCRIPTION_CHARS else ""


def parse_wikipedia_intros(payload, language, requested_titles):
    """Map each requested article title -> WikipediaIntro, following normalisation and redirects."""
    query = payload.get("query") or {}
    aliases = {}
    for step in (query.get("normalized") or []) + (query.get("redirects") or []):
        aliases[step.get("from", "")] = step.get("to", "")

    def final_title(title):
        seen = set()
        while title in aliases and title not in seen:
            seen.add(title)
            title = aliases[title]
        return title

    by_title = {}
    for page in (query.get("pages") or {}).values():
        text = clean_intro(page.get("extract"))
        title = page.get("title", "")
        if not text or "missing" in page:
            continue
        name = "Википедия" if language == "ru" else "англ. Википедия"
        by_title[title] = WikipediaIntro(
            text=text,
            url=WIKIPEDIA_ARTICLE_URL.format(language=language, title=quote(title.replace(" ", "_"))),
            credit=f"{name}, статья «{title}», CC BY-SA 4.0"[:200],
        )
    return {title: by_title[final_title(title)] for title in requested_titles if final_title(title) in by_title}


def parse_commons_images(payload):
    """Map Commons file name -> thumbnail URL and an attribution line (author, licence, file)."""
    images = {}
    pages = (payload.get("query") or {}).get("pages") or {}
    for page in pages.values():
        info = (page.get("imageinfo") or [None])[0]
        title = page.get("title", "")
        if not info or not title.startswith("File:"):
            continue
        metadata = info.get("extmetadata") or {}
        author = _strip_html((metadata.get("Artist") or {}).get("value"))
        licence = _strip_html((metadata.get("LicenseShortName") or {}).get("value"))
        url = info.get("thumburl") or info.get("url") or ""
        # Without an author or licence the photo cannot be credited correctly.
        if not (author and licence and url.startswith("https://")):
            continue
        file_name = title.removeprefix("File:")
        credit = f"{author}, {licence}, Wikimedia Commons ({file_name.replace(' ', '_')})"
        images[file_name] = CommonsImage(url=url[:500], credit=credit[:200])
    return images


class WikidataClient:
    def __init__(self, *, timeout=60.0, opener=None, sleep=time.sleep):
        self.timeout = timeout
        self.opener = opener or urlopen
        self.sleep = sleep

    def fetch_cars(self, owner_qids):
        query = urlencode({"query": build_sparql_query(owner_qids), "format": "json"})
        request = Request(
            SPARQL_ENDPOINT,
            data=query.encode("utf-8"),
            headers={
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        return parse_sparql_cars(self._request_json(request))

    def fetch_images(self, file_names):
        images = {}
        names = sorted(set(file_names))
        for start in range(0, len(names), COMMONS_BATCH_SIZE):
            batch = names[start:start + COMMONS_BATCH_SIZE]
            params = urlencode({
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": IMAGE_WIDTH_PX,
                "titles": "|".join(f"File:{name}" for name in batch),
            })
            request = Request(f"{COMMONS_API_ENDPOINT}?{params}", headers={"User-Agent": USER_AGENT})
            images.update(parse_commons_images(self._request_json(request)))
        return images

    def fetch_wikipedia_intros(self, language, titles):
        """Plain-text introductions of Wikipedia articles (MediaWiki extracts API)."""
        intros = {}
        names = sorted(set(titles))
        for start in range(0, len(names), WIKIPEDIA_BATCH_SIZE):
            batch = names[start:start + WIKIPEDIA_BATCH_SIZE]
            params = urlencode({
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": WIKIPEDIA_BATCH_SIZE,
                "redirects": 1,
                "titles": "|".join(batch),
            })
            request = Request(
                f"{WIKIPEDIA_API_ENDPOINT.format(language=language)}?{params}", headers={"User-Agent": USER_AGENT}
            )
            intros.update(parse_wikipedia_intros(self._request_json(request), language, batch))
        return intros

    def _request_json(self, request):
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._request_json_once(request)
            except HTTPError as error:
                if error.code != 429 or attempt == MAX_RETRIES:
                    raise WikidataError(f"API вернул ошибку HTTP {error.code}.") from error
                self.sleep(_retry_after_seconds(error, attempt))

    def _request_json_once(self, request):
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw_body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise WikidataError("API не ответил за отведённое время.") from error
        except (URLError, HTTPException, OSError) as error:
            raise WikidataError("Не удалось подключиться к API.") from error

        if len(raw_body) > MAX_RESPONSE_BYTES:
            raise WikidataError("Ответ API слишком большой.")
        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WikidataError("API вернул некорректный JSON (возможно, временная перегрузка).") from error


def _retry_after_seconds(error, attempt):
    """Seconds from the Retry-After header, or 2, 4, 8 s when it is absent; capped."""
    try:
        seconds = float((error.headers or {}).get("Retry-After", ""))
    except (TypeError, ValueError):
        seconds = 2 ** (attempt + 1)
    return max(1, min(seconds, MAX_RETRY_WAIT_SECONDS))


# --- Matching rules ------------------------------------------------------------------


def owner_qids():
    return {qid for qids, _prefixes in WIKIDATA_BRANDS.values() for qid in qids}


def assign_brand(car):
    """Return (brand name, model name) or (None, reason).

    1. Candidate brands come from the "brand" statement (P1716). Only if a car has no
       brand mapped here do we fall back to "manufacturer" (P176).
    2. The English label must start with the brand name: this rejects cars of other
       brands of the same company (Jaecoo J7 made by Chery, Denza D9 made by BYD).
    3. The model name is the label without the brand prefix and without "(...)".
    """
    if not car.label_en:
        return None, "нет английского названия"
    text = f"{car.label_en} {car.description}".lower()
    for word in EXCLUDED_WORDS:
        # English words are matched whole ("bus", not "business"), Russian ones by stem.
        word_end = r"\b" if word.isascii() else ""
        if re.search(rf"\b{re.escape(word)}{word_end}", text):
            return None, f"не легковая серийная модель («{word}»)"

    candidates = [name for name, (qids, _p) in WIKIDATA_BRANDS.items() if car.brand_qids & set(qids)]
    if not candidates:
        candidates = [name for name, (qids, _p) in WIKIDATA_BRANDS.items() if car.manufacturer_qids & set(qids)]

    label = re.sub(r"\s*\([^)]*\)", "", car.label_en).strip()
    best = None
    for brand_name in candidates:
        for prefix in WIKIDATA_BRANDS[brand_name][1]:
            if label.lower().startswith(prefix.lower() + " ") and (best is None or len(prefix) > len(best[1])):
                best = (brand_name, prefix)
    if best is None:
        return None, "название не начинается с марки (другая марка того же концерна)"

    model_name = label[len(best[1]):].strip()
    return best[0], model_name


def _useful_description(text):
    text = (text or "").strip()
    if text.lower() in GENERIC_DESCRIPTIONS:
        return ""
    return text[:1].upper() + text[1:]


def _unique_slug(base, taken):
    slug = slugify(base)[:190] or "model"
    candidate, number = slug, 2
    while candidate in taken:
        candidate = f"{slug}-{number}"
        number += 1
    taken.add(candidate)
    return candidate


# --- Import --------------------------------------------------------------------------


class WikidataImporter:
    """Creates new models as drafts (is_active=False) and only fills empty fields of existing ones."""

    def __init__(self, client=None):
        self.client = client or WikidataClient()

    def run(self, *, publish=False, with_images=True, with_descriptions=True, dry_run=False):
        cars = self.client.fetch_cars(owner_qids())
        report = ImportReport()

        brands = {brand.name: brand for brand in Brand.objects.filter(name__in=WIKIDATA_BRANDS)}
        planned = []
        seen = set()
        for car in cars:
            brand_name, model_name = assign_brand(car)
            if brand_name is None:
                report.skipped.append((car.label_en or car.qid, model_name))
                continue
            if brand_name not in brands:
                report.skipped.append((car.label_en, f"марки {brand_name} нет в базе"))
                continue
            key = (brand_name, model_name.lower())
            if key in seen:
                report.skipped.append((car.label_en, "дубликат названия в Wikidata"))
                continue
            seen.add(key)
            planned.append((brands[brand_name], model_name, car))

        images = {}
        if with_images:
            images = self.client.fetch_images(car.image_file for _b, _n, car in planned if car.image_file)
            report.images_found = len(images)

        intros = {}
        if with_descriptions:
            intros = self._fetch_intros([car for _b, _n, car in planned])
            report.descriptions_found = len(intros)

        with transaction.atomic():
            self._apply(planned, images, intros, report, publish=publish)
            if dry_run:
                transaction.set_rollback(True)
        return report

    def _fetch_intros(self, cars):
        """Russian article if it exists, otherwise the English one. Returns qid -> WikipediaIntro."""
        ru_titles = {car.qid: car.ru_article for car in cars if car.ru_article}
        en_titles = {car.qid: car.en_article for car in cars if car.en_article and not car.ru_article}
        intros = {}
        for language, titles in (("ru", ru_titles), ("en", en_titles)):
            if not titles:
                continue
            by_title = self.client.fetch_wikipedia_intros(language, titles.values())
            intros.update({qid: by_title[title] for qid, title in titles.items() if title in by_title})
        return intros

    def _apply(self, planned, images, intros, report, *, publish):
        taken_slugs = set(Model.objects.values_list("slug", flat=True))
        for brand, model_name, car in planned:
            image = images.get(car.image_file)
            intro = intros.get(car.qid)
            title = f"{brand.name} {model_name}"
            existing = self._find_existing(brand, model_name, car)
            if existing is not None:
                changed = self._fill_empty_fields(existing, car, image, intro)
                (report.updated if changed else report.unchanged).append(title)
                continue

            Model.objects.create(
                brand=brand,
                name=model_name[:160],
                slug=_unique_slug(f"{brand.slug}-{model_name}", taken_slugs),
                description=intro.text if intro else _useful_description(car.description),
                description_source_url=intro.url if intro else "",
                description_credit=intro.credit if intro else "",
                production_status=(
                    # Wikidata rarely states production periods: without an explicit end
                    # (P2669 discontinued date, P730 service retirement, P582 end time)
                    # the status is unknown rather than assumed "in production".
                    Model.ProductionStatus.DISCONTINUED if car.is_discontinued
                    else Model.ProductionStatus.UNKNOWN
                ),
                image_url=image.url if image else "",
                image_credit=image.credit if image else "",
                source_url=car.url,
                source_note=f"Импортировано из Wikidata ({car.qid}, CC0). Требует проверки редактором.",
                is_active=publish,
            )
            report.created.append(title)

    @staticmethod
    def _find_existing(brand, model_name, car):
        """Match by the Wikidata URL of an earlier import, then by English, Russian or export name."""
        by_source = Model.objects.filter(source_url=car.url).first()
        if by_source is not None:
            return by_source
        names = {model_name.lower()}
        twin = MARKET_TWINS.get((brand.name, model_name))
        if twin:
            names.add(twin.lower())
        for prefix in WIKIDATA_BRANDS[brand.name][1]:
            if car.label_ru.lower().startswith(prefix.lower() + " "):
                names.add(car.label_ru[len(prefix):].strip().lower())
        for candidate in brand.models.all():
            if candidate.name.lower() in names:
                return candidate
        return None

    @staticmethod
    def _fill_empty_fields(model, car, image, intro=None):
        """Never overwrite manually verified data: only empty fields are filled.

        The one exception is the short Wikidata caption saved by an earlier import
        ("Гибридный автомобиль"): it is replaced by the fuller Wikipedia intro.
        """
        changed = []
        short_caption = _useful_description(car.description)
        if intro and (not model.description or model.description == short_caption):
            model.description = intro.text
            model.description_source_url, model.description_credit = intro.url, intro.credit
            changed += ["description", "description_source_url", "description_credit"]
        elif not model.description and short_caption:
            model.description = short_caption
            changed.append("description")
        if not model.image_url and image:
            model.image_url, model.image_credit = image.url, image.credit
            changed += ["image_url", "image_credit"]
        if not model.source_url:
            model.source_url = car.url
            changed.append("source_url")
        if changed:
            model.save(update_fields=[*changed, "updated_at"])
        return bool(changed)
