import pytest
from django.core.management import call_command
from django.urls import reverse

from .services import (
    ExternalSearchProvider, QueryCorrector, SearchAssistanceService, SearchCoordinator,
)
from .services.correction import WORD_RE


VOCABULARY_TEXT = (
    "BYD Seal Zeekr 001 Geely Monjaro Chery Tiggo Haval Jolion Blade Battery "
    "электромобиль гибрид кроссовер самый быстрый какие"
)


@pytest.fixture
def corrector():
    vocabulary = {word.casefold(): word for word in WORD_RE.findall(VOCABULARY_TEXT)}
    return QueryCorrector(vocabulary)


# --- Word-level rules (no database) -------------------------------------------------


@pytest.mark.parametrize(("query", "expected", "reason"), [
    ("зикр 001", "Zeekr 001", "русское написание"),
    ("джили", "Geely", "русское написание"),
    ("инв", "BYD", "неверная раскладка"),            # "byd" typed on the Russian layout
    ("Яуулк 001", "Zeekr 001", "неверная раскладка"),
    ("ktrnhjvj,bkm", "электромобиль", "неверная раскладка"),  # layout + missing letter
    ("Zekr 001", "Zeekr 001", "опечатка"),
    ("blade batery", "blade Battery", "опечатка"),
    ("элктромобиль BYD", "электромобиль BYD", "опечатка"),
    ("тигго", "Tiggo", "написано по-русски"),
    ("Хавал Джолион", "Haval Jolion", "русское написание"),
])
def test_word_is_corrected_with_reason(corrector, query, expected, reason):
    correction = corrector.correct(query)

    assert correction.corrected == expected
    assert correction.changes[0].reason == reason


@pytest.mark.parametrize("query", [
    "BYD Seal",                     # known words
    "какие электромобили",          # another ending of a known word: FTS handles it
    "самый быстрый кроссовер",
    "Zeekr 001",
    "2024",
    "надёжный",                     # unknown but not close to anything: left as typed
])
def test_correct_query_is_not_changed(corrector, query):
    assert corrector.correct(query) is None


def test_only_misspelled_word_changes_in_a_sentence(corrector):
    correction = corrector.correct("самый быстрый зикр?")

    assert correction.corrected == "самый быстрый Zeekr?"
    assert correction.explanation == "«зикр» → «Zeekr» (русское написание)"


def test_correction_is_deterministic(corrector):
    assert corrector.correct("Zekr 001") == corrector.correct("Zekr 001")


def test_prefix_in_russian_layout_is_switched_for_autocomplete(corrector):
    assert corrector.complete_prefix("яуу") == "zee"
    assert corrector.complete_prefix("эле") is None
    assert corrector.complete_prefix("by") is None


# --- Search page and coordinator ----------------------------------------------------


@pytest.fixture
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


class RecordingProvider(ExternalSearchProvider):
    name = "test"

    def __init__(self):
        self.queries = []

    def search(self, query, *, limit, language):
        self.queries.append(query)
        return []


def test_certain_correction_is_applied_like_google(demo_data):
    provider = RecordingProvider()

    response = SearchCoordinator(external_provider=provider).search("зикр 001")

    assert response.correction_applied
    assert response.internal.query.original == "Zeekr 001"
    assert any("Zeekr 001" in result.title for result in response.internal.groups["Cars"])
    assert provider.queries == ["Zeekr 001"]


def test_exact_search_keeps_typed_query(demo_data):
    response = SearchCoordinator(external_provider=RecordingProvider()).search("зикр 001", allow_correction=False)

    assert not response.correction_applied
    assert response.correction.corrected == "Zeekr 001"
    assert response.internal.query.original == "зикр 001"


def test_typo_is_only_suggested_when_original_query_finds_results(demo_data):
    response = SearchCoordinator(external_provider=RecordingProvider()).search("Zeek 001")

    # Trigram search already finds Zeekr 001, so the typed query is kept.
    assert response.internal.total > 0
    assert response.correction.corrected == "Zeekr 001"
    assert not response.correction_applied


def test_typo_is_applied_when_original_query_finds_nothing(demo_data):
    response = SearchCoordinator(external_provider=RecordingProvider()).search("элктромобиль")

    assert response.correction.corrected == "электромобиль"
    assert response.correction_applied
    assert response.internal.total > 0


def test_search_page_shows_applied_correction_and_exact_link(demo_data, client):
    content = client.get(reverse("search:index"), {"q": "зикр 001"}).content.decode()

    assert "Показаны результаты по запросу <strong>Zeekr 001</strong>" in content
    assert "exact=1" in content
    assert "«зикр» → «Zeekr» (русское написание)" in content


def test_exact_link_shows_did_you_mean(demo_data, client):
    content = client.get(reverse("search:index"), {"q": "зикр 001", "exact": "1"}).content.decode()

    assert "Показаны результаты по запросу" not in content
    assert "Возможно, вы имели в виду" in content


def test_search_page_without_typo_has_no_correction(demo_data, client):
    content = client.get(reverse("search:index"), {"q": "BYD Seal"}).content.decode()

    assert "Исправлено:" not in content


# --- Autocomplete -------------------------------------------------------------------


def test_autocomplete_finds_model_without_brand(demo_data):
    labels = [item.label for item in SearchAssistanceService().autocomplete("seal")]

    assert "BYD Seal" in labels


def test_autocomplete_switches_keyboard_layout(demo_data):
    labels = [item.label for item in SearchAssistanceService().autocomplete("яуу")]

    assert "Zeekr 001" in labels


def test_autocomplete_puts_corrected_query_first(demo_data):
    suggestions = SearchAssistanceService().autocomplete("зикр")

    assert (suggestions[0].label, suggestions[0].type) == ("Zeekr", "correction")
    assert "Zeekr 001" in [item.label for item in suggestions]


def test_autocomplete_falls_back_to_similar_names(demo_data):
    labels = [item.label for item in SearchAssistanceService().autocomplete("Zeekk 00")]

    assert "Zeekr 001" in labels
