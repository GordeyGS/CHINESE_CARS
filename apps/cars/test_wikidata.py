import io
import json
from urllib.error import URLError

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from .models import Brand, Manufacturer, Model
from .services.wikidata import (
    WikidataCar, WikidataClient, WikidataError, WikidataImporter, assign_brand, clean_intro, parse_commons_images,
    parse_sparql_cars, parse_wikipedia_intros,
)


ENTITY = "http://www.wikidata.org/entity/"
FILE_PATH = "http://commons.wikimedia.org/wiki/Special:FilePath/"


def sparql_row(qid, label, *, brand=None, maker=None, desc="", ru="", image=None, discontinued=False,
               ru_article="", en_article=""):
    row = {"car": {"value": ENTITY + qid}, "labelEn": {"value": label}}
    if brand:
        row["brand"] = {"value": ENTITY + brand}
    if maker:
        row["maker"] = {"value": ENTITY + maker}
    if desc:
        row["descEn"] = {"value": desc}
    if ru:
        row["labelRu"] = {"value": ru}
    if image:
        row["image"] = {"value": FILE_PATH + image}
    if discontinued:
        row["ended"] = {"value": "2018-01-01T00:00:00Z"}
    if ru_article:
        row["ruArticle"] = {"value": ru_article}
    if en_article:
        row["enArticle"] = {"value": en_article}
    return row


SPARQL_RESPONSE = {"results": {"bindings": [
    # New BYD model with a photo; two rows because it has two manufacturer statements.
    sparql_row("Q98886444", "BYD Han", brand="Q27423", maker="Q27423", desc="full-size luxury sedan by BYD",
               image="BYD_Han_001.jpg", ru_article="BYD Han", en_article="BYD Han"),
    sparql_row("Q98886444", "BYD Han", brand="Q27423", maker="Q2608329", desc="full-size luxury sedan by BYD",
               image="BYD_Han_001.jpg", ru_article="BYD Han", en_article="BYD Han"),
    # Already in the knowledge base: only empty fields may be filled.
    sparql_row("Q114414285", "BYD Seal", brand="Q27423", desc="Chinese electric sedan", image="BYD_Seal.jpg"),
    # Discontinued model.
    sparql_row("Q797218", "BYD F3", brand="Q27423", desc="compact car", discontinued=True, en_article="BYD F3"),
    # Another brand of the same group (Denza is made by BYD): rejected by the label rule.
    sparql_row("Q115120716", "Denza D9", brand="Q2381970", maker="Q27423", desc="minivan"),
    # Not a passenger car.
    sparql_row("Q102046494", "BYD 8TT", maker="Q27423", desc="all-electric heavy duty semi-truck"),
]}}

COMMONS_RESPONSE = {"query": {"pages": {
    "1": {
        "title": "File:BYD Han 001.jpg",
        "imageinfo": [{
            "thumburl": "https://upload.wikimedia.org/thumb/BYD_Han_001.jpg/960px-BYD_Han_001.jpg",
            "extmetadata": {
                "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Author">Some Author</a>'},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
            },
        }],
    },
}}}


HAN_INTRO = "BYD Han — полноразмерный седан китайской компании BYD Auto, выпускаемый с 2020 года."
F3_INTRO = "The BYD F3 is a compact sedan manufactured by BYD Auto from 2005 to 2021."


def wikipedia_response(request_url):
    if "ru.wikipedia.org" in request_url:
        return {"query": {"pages": {"1": {"title": "BYD Han", "extract": HAN_INTRO}}}}
    return {"query": {
        "normalized": [{"from": "BYD_F3", "to": "BYD F3"}],
        "pages": {"2": {"title": "BYD F3", "extract": F3_INTRO}},
    }}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeOpener:
    """Returns canned JSON for Wikidata SPARQL and Commons requests instead of using the network."""

    def __init__(self, sparql=SPARQL_RESPONSE, commons=COMMONS_RESPONSE):
        self.sparql, self.commons = sparql, commons
        self.urls = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        if "query.wikidata.org" in request.full_url:
            payload = self.sparql
        elif "wikipedia.org" in request.full_url:
            payload = wikipedia_response(request.full_url)
        else:
            payload = self.commons
        return FakeResponse(json.dumps(payload).encode())


def failing_opener(request, timeout):
    raise URLError("network is down")


def importer(opener=None):
    return WikidataImporter(WikidataClient(opener=opener or FakeOpener()))


# --- Parsing and rules (no database) --------------------------------------------------


def test_sparql_rows_are_collapsed_into_one_car():
    cars = {car.qid: car for car in parse_sparql_cars(SPARQL_RESPONSE)}

    han = cars["Q98886444"]
    assert han.manufacturer_qids == {"Q27423", "Q2608329"}
    assert han.image_file == "BYD Han 001.jpg"
    assert han.url == "https://www.wikidata.org/wiki/Q98886444"
    assert cars["Q797218"].is_discontinued


def test_commons_credit_contains_author_and_licence_without_html():
    images = parse_commons_images(COMMONS_RESPONSE)

    assert images["BYD Han 001.jpg"].credit == "Some Author, CC BY-SA 4.0, Wikimedia Commons (BYD_Han_001.jpg)"


def test_commons_image_without_licence_is_not_used():
    payload = {"query": {"pages": {"1": {"title": "File:X.jpg", "imageinfo": [{"url": "https://x/X.jpg"}]}}}}

    assert parse_commons_images(payload) == {}


@pytest.mark.parametrize(("car", "expected"), [
    (WikidataCar("Q1", "BYD Han", brand_qids=frozenset({"Q27423"})), ("BYD", "Han")),
    (WikidataCar("Q2", "Li Auto L9", manufacturer_qids=frozenset({"Q98139925"})), ("Li Auto", "L9")),
    (WikidataCar("Q3", "Li L6", manufacturer_qids=frozenset({"Q98139925"})), ("Li Auto", "L6")),
    (WikidataCar("Q4", "Chery Omoda S5", brand_qids=frozenset({"Q118646009"}),
                 manufacturer_qids=frozenset({"Q591001"})), ("Omoda", "S5")),
    (WikidataCar("Q5", "BYD M6 (2010)", brand_qids=frozenset({"Q27423"})), ("BYD", "M6")),
])
def test_brand_and_model_name_are_derived_from_statements_and_label(car, expected):
    assert assign_brand(car) == expected


@pytest.mark.parametrize(("car", "reason"), [
    (WikidataCar("Q1", "Jaecoo J7", manufacturer_qids=frozenset({"Q591001"})), "не начинается с марки"),
    (WikidataCar("Q2", "BYD 8TT", description="semi-truck", manufacturer_qids=frozenset({"Q27423"})), "truck"),
    (WikidataCar("Q3", "Geely Vision Concept", manufacturer_qids=frozenset({"Q739000"})), "concept"),
    (WikidataCar("Q4", "", manufacturer_qids=frozenset({"Q27423"})), "нет английского названия"),
])
def test_unsuitable_candidates_are_rejected_with_a_reason(car, reason):
    brand, explanation = assign_brand(car)

    assert brand is None
    assert reason in explanation


def test_word_rule_does_not_match_inside_other_words():
    car = WikidataCar("Q1", "BYD Han", description="business sedan", brand_qids=frozenset({"Q27423"}))

    assert assign_brand(car) == ("BYD", "Han")


# --- Import into the database ---------------------------------------------------------


@pytest.fixture
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


def test_new_models_are_created_as_drafts_with_source_and_credit(demo_data):
    report = importer().run()

    han = Model.objects.get(brand__name="BYD", name="Han")
    assert sorted(report.created) == ["BYD F3", "BYD Han"]
    assert han.is_active is False
    assert han.slug == "byd-han"
    assert han.source_url == "https://www.wikidata.org/wiki/Q98886444"
    assert "Q98886444" in han.source_note
    assert han.description == HAN_INTRO
    assert han.description_source_url == "https://ru.wikipedia.org/wiki/BYD_Han"
    assert han.description_credit == "Википедия, статья «BYD Han», CC BY-SA 4.0"
    assert han.image_url.startswith("https://upload.wikimedia.org/")
    assert han.image_credit.startswith("Some Author, CC BY-SA 4.0")
    assert Model.objects.get(name="F3").production_status == Model.ProductionStatus.DISCONTINUED
    # No production period in Wikidata: the status is not invented.
    assert han.production_status == Model.ProductionStatus.UNKNOWN
    assert not Model.objects.filter(name__in=["D9", "8TT"]).exists()
    assert {title for title, _reason in report.skipped} == {"Denza D9", "BYD 8TT"}


def test_existing_model_keeps_verified_data(demo_data):
    seal = Model.objects.get(slug="byd-seal")
    seal.description = "Проверенное описание"
    seal.source_url = "https://www.byd.com/eu/electric-cars/seal"
    seal.save()

    importer().run()

    seal.refresh_from_db()
    assert seal.description == "Проверенное описание"
    assert seal.source_url == "https://www.byd.com/eu/electric-cars/seal"
    assert Model.objects.filter(brand__name="BYD", name="Seal").count() == 1


def test_import_is_idempotent(demo_data):
    importer().run()
    count = Model.objects.count()

    report = importer().run()

    assert Model.objects.count() == count
    assert report.created == []


def test_market_twin_is_matched_to_export_name(demo_data):
    geely = Brand.objects.create(
        manufacturer=Manufacturer.objects.get(name="Geely Holding"),
        origin_country=Brand.objects.get(name="BYD").origin_country,
        name="Geely", slug="geely",
    )
    Model.objects.create(brand=geely, name="EX5", slug="geely-ex5")
    sparql = {"results": {"bindings": [sparql_row("Q127240756", "Geely Galaxy E5", maker="Q55118127")]}}

    report = importer(FakeOpener(sparql=sparql)).run(with_images=False)

    assert report.created == []
    assert not Model.objects.filter(name="Galaxy E5").exists()


def test_publish_flag_makes_new_models_active(demo_data):
    importer().run(publish=True)

    assert Model.objects.get(name="Han").is_active is True


def test_dry_run_does_not_change_database(demo_data):
    count = Model.objects.count()

    report = importer().run(dry_run=True)

    assert len(report.created) == 2
    assert Model.objects.count() == count


def test_without_images_commons_is_not_called(demo_data):
    opener = FakeOpener()

    importer(opener).run(with_images=False)

    assert all("commons" not in url for url in opener.urls)
    assert Model.objects.get(name="Han").image_url == ""


def test_draft_model_is_hidden_from_public_catalog(demo_data, client):
    importer().run()

    response = client.get("/cars/byd-han/")

    assert response.status_code == 404


def test_unavailable_api_stops_command_without_changes(demo_data, monkeypatch):
    monkeypatch.setattr("apps.cars.services.wikidata.urlopen", failing_opener)
    count = Model.objects.count()

    with pytest.raises(CommandError, match="Не удалось подключиться"):
        call_command("import_wikidata", verbosity=0)

    assert Model.objects.count() == count


def test_invalid_json_is_reported_safely(demo_data):
    class BrokenOpener(FakeOpener):
        def __call__(self, request, timeout):
            return FakeResponse(b"<html>Too many requests</html>")

    with pytest.raises(WikidataError, match="некорректный JSON"):
        importer(BrokenOpener()).run()


def test_published_model_without_generations_renders_in_catalog_and_detail(demo_data, client):
    importer().run(publish=True)

    detail = client.get("/cars/byd-han/")
    catalog = client.get("/cars/", {"brand": "byd"})

    assert detail.status_code == 200
    assert "Some Author, CC BY-SA 4.0" in detail.content.decode()
    assert "Нет данных" in detail.content.decode()
    assert catalog.status_code == 200
    assert "Нет данных" in catalog.content.decode()


# --- Wikipedia descriptions -------------------------------------------------------


def test_wikipedia_intro_follows_redirects_and_normalisation():
    payload = {"query": {
        "normalized": [{"from": "Geely_Atlas", "to": "Geely Atlas"}],
        "redirects": [{"from": "Geely Atlas", "to": "Geely Boyue"}],
        "pages": {"1": {"title": "Geely Boyue", "extract": "Geely Boyue / Atlas — кроссовер китайского автоконцерна Geely."}},
    }}

    intros = parse_wikipedia_intros(payload, "ru", ["Geely_Atlas"])

    assert intros["Geely_Atlas"].url == "https://ru.wikipedia.org/wiki/Geely_Boyue"


def test_missing_or_too_short_article_is_ignored():
    payload = {"query": {"pages": {
        "-1": {"title": "Nothing", "missing": ""},
        "2": {"title": "Stub", "extract": "Автомобиль."},
    }}}

    assert parse_wikipedia_intros(payload, "ru", ["Nothing", "Stub"]) == {}


def test_long_intro_is_cut_at_sentence_end():
    sentence = "Это предложение об автомобиле, повторённое для проверки длины. "
    text = clean_intro(sentence * 40)

    assert len(text) <= 1200
    assert text.endswith(".")


def test_english_article_is_used_when_russian_is_absent(demo_data):
    importer().run()

    f3 = Model.objects.get(name="F3")
    assert f3.description == F3_INTRO
    assert f3.description_credit.startswith("англ. Википедия")


def test_short_wikidata_caption_from_earlier_import_is_upgraded(demo_data):
    importer().run(with_descriptions=False)
    assert Model.objects.get(name="Han").description == "Full-size luxury sedan by BYD"

    report = importer().run()

    assert "BYD Han" in report.updated
    assert Model.objects.get(name="Han").description == HAN_INTRO


def test_verified_description_is_not_replaced_by_wikipedia(demo_data):
    seal = Model.objects.get(slug="byd-seal")
    seal.description = "Проверенное описание"
    seal.save()
    sparql = {"results": {"bindings": [sparql_row("Q114414285", "BYD Seal", brand="Q27423", ru_article="BYD Han")]}}

    importer(FakeOpener(sparql=sparql)).run()

    seal.refresh_from_db()
    assert seal.description == "Проверенное описание"
    assert seal.description_credit == ""


def test_model_page_shows_description_source(demo_data, client):
    importer().run(publish=True)

    content = client.get("/cars/byd-han/").content.decode()

    assert HAN_INTRO in content
    assert 'href="https://ru.wikipedia.org/wiki/BYD_Han"' in content
    assert "Википедия, статья «BYD Han», CC BY-SA 4.0" in content


def test_rate_limit_is_retried_after_server_delay(demo_data):
    from email.message import Message
    from urllib.error import HTTPError

    class RateLimitedOnce(FakeOpener):
        failed = False

        def __call__(self, request, timeout):
            if "wikipedia.org" in request.full_url and not self.failed:
                self.failed = True
                headers = Message()
                headers["Retry-After"] = "8"
                raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)
            return super().__call__(request, timeout)

    waits = []
    client = WikidataClient(opener=RateLimitedOnce(), sleep=waits.append)

    WikidataImporter(client).run()

    assert waits == [8.0]
    assert Model.objects.get(name="Han").description == HAN_INTRO


def test_persistent_rate_limit_stops_import_safely(demo_data):
    from email.message import Message
    from urllib.error import HTTPError

    def always_limited(request, timeout):
        raise HTTPError(request.full_url, 429, "Too Many Requests", Message(), None)

    waits = []
    count = Model.objects.count()

    with pytest.raises(WikidataError, match="429"):
        WikidataImporter(WikidataClient(opener=always_limited, sleep=waits.append)).run()

    assert waits == [2, 4, 8]
    assert Model.objects.count() == count


# --- Editorial translations of English intros ------------------------------------------


F3_RU = "BYD F3 – компактный седан BYD Auto, выпускавшийся с 2005 по 2021 год."


def test_translation_replaces_english_intro_on_create(demo_data, monkeypatch):
    monkeypatch.setattr("apps.cars.services.wikidata.load_translations", lambda: {"Q797218": F3_RU})

    importer().run()

    f3 = Model.objects.get(name="F3")
    assert f3.description == F3_RU
    assert f3.description_credit == "перевод статьи англ. Википедии «BYD F3», CC BY-SA 4.0"
    assert f3.description_source_url == "https://en.wikipedia.org/wiki/BYD_F3"


def test_translation_upgrades_english_text_from_earlier_import(demo_data, monkeypatch):
    monkeypatch.setattr("apps.cars.services.wikidata.load_translations", lambda: {})
    importer().run()
    assert Model.objects.get(name="F3").description == F3_INTRO

    monkeypatch.setattr("apps.cars.services.wikidata.load_translations", lambda: {"Q797218": F3_RU})
    report = importer().run()

    assert "BYD F3" in report.updated
    assert Model.objects.get(name="F3").description == F3_RU


def test_translation_does_not_touch_russian_intro_or_edited_text(demo_data, monkeypatch):
    monkeypatch.setattr("apps.cars.services.wikidata.load_translations", lambda: {})
    importer().run()
    Model.objects.filter(name="F3").update(description="Текст, исправленный редактором")
    translations = {"Q797218": F3_RU, "Q98886444": "Не должен применяться к русской статье"}
    monkeypatch.setattr("apps.cars.services.wikidata.load_translations", lambda: translations)

    importer().run()

    assert Model.objects.get(name="F3").description == "Текст, исправленный редактором"
    assert Model.objects.get(name="Han").description == HAN_INTRO


def test_translations_file_is_valid_and_has_no_chinese_characters():
    from .services.wikidata import load_translations

    translations = load_translations()
    assert translations
    for qid, text in translations.items():
        assert qid.startswith("Q") and len(text) > 40
        assert not any("一" <= ch <= "鿿" for ch in text), qid


def test_brackets_with_chinese_name_are_removed_from_intro():
    from .services.wikidata import strip_chinese_brackets

    text = "Geely Boyue / Atlas (кит. 吉利博越, пиньинь Jílì Bóyuè) — кроссовер Geely (2016–2023)."

    assert strip_chinese_brackets(text) == "Geely Boyue / Atlas — кроссовер Geely (2016–2023)."


def test_items_rejected_by_editor_are_skipped_with_reason(demo_data, monkeypatch):
    monkeypatch.setitem(
        __import__("apps.cars.services.wikidata", fromlist=["EXCLUDED_ITEMS"]).EXCLUDED_ITEMS,
        "Q98886444", "проверено редактором: не серийная модель",
    )

    report = importer().run()

    assert not Model.objects.filter(name="Han").exists()
    assert ("BYD Han", "проверено редактором: не серийная модель") in report.skipped


def test_name_match_ignores_model_imported_from_another_item(demo_data):
    byd = Brand.objects.get(name="BYD")
    Model.objects.create(brand=byd, name="Han", slug="byd-han-old",
                         source_url="https://www.wikidata.org/wiki/Q1", is_active=False)
    sparql = {"results": {"bindings": [sparql_row("Q98886444", "BYD Han", brand="Q27423")]}}

    report = importer(FakeOpener(sparql=sparql)).run(with_images=False, with_descriptions=False)

    assert report.created == []  # unique (brand, name) forbids a second "Han" ...
    assert ("BYD Han", "название занято моделью из другого элемента Wikidata") in report.skipped
