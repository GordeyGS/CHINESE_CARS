import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.cars.models import Technology
from apps.knowledge.models import Article, VideoResource

from .services import InternalSearchService, QueryParser, QueryType, QueryValidationError


pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module", autouse=True)
def demo_search_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("load_demo_data", verbosity=0)


def find(response, group, *, result_type=None, title=None):
    return [
        result
        for result in response.groups[group]
        if (result_type is None or result.result_type == result_type)
        and (title is None or title.casefold() in result.title.casefold())
    ]


def test_query_parser_classifies_word_phrase_and_sentence():
    parser = QueryParser()
    assert parser.parse("  BYD ").query_type is QueryType.WORD
    assert parser.parse("Blade   Battery").query_type is QueryType.PHRASE
    sentence = parser.parse("Какие электромобили BYD используют Blade Battery?")
    assert sentence.query_type is QueryType.SENTENCE
    assert sentence.normalized == "Какие электромобили BYD используют Blade Battery?"
    assert sentence.terms == ("электромобили", "BYD", "Blade", "Battery")
    assert sentence.phrase_candidates == ("Blade Battery",)


def test_word_search_byd_returns_all_result_groups():
    response = InternalSearchService().search("BYD")
    assert all(response.groups[group] for group in ("Articles", "Cars", "Technologies", "Videos"))


def test_phrase_search_blade_battery():
    response = InternalSearchService().search("Blade Battery")
    assert find(response, "Technologies", result_type="Technology", title="Blade Battery")
    assert find(response, "Articles", title="Blade Battery")


def test_exact_phrase_ranks_above_scattered_terms():
    scattered = Technology.objects.create(
        name="Blade energy module",
        slug="blade-energy-module",
        description="Battery construction for a demonstration.",
    )
    response = InternalSearchService().search("Blade Battery")
    exact = find(response, "Technologies", title="Blade Battery")[0]
    scattered_result = find(response, "Technologies", title=scattered.name)[0]
    assert exact.score > scattered_result.score


def test_zeekr_001_search_returns_vehicle_model():
    response = InternalSearchService().search("Zeekr 001")
    assert find(response, "Cars", result_type="Model", title="Zeekr 001")


def test_sentence_search_extracts_terms_and_returns_grouped_knowledge():
    response = InternalSearchService().search("Какие электромобили BYD используют Blade Battery?")
    assert response.query.query_type is QueryType.SENTENCE
    assert find(response, "Articles", result_type="Article")
    assert find(response, "Cars", result_type="Model", title="BYD Seal")
    assert find(response, "Technologies", result_type="Technology", title="Blade Battery")
    assert find(response, "Videos", result_type="Video")


def test_trigram_typo_finds_brand():
    response = InternalSearchService().search("Zekr")
    assert find(response, "Cars", result_type="Brand", title="Zeekr")


def test_empty_query_is_rejected_before_search():
    with pytest.raises(QueryValidationError, match="Введите поисковый запрос"):
        InternalSearchService().search("   ")


def test_unknown_query_returns_empty_groups():
    response = InternalSearchService().search("xqznonexistentterm")
    assert response.total == 0
    assert all(not results for results in response.groups.values())


@pytest.mark.parametrize(
    ("group", "result_type", "query"),
    [
        ("Articles", "Article", "Blade Battery"),
        ("Cars", "Model", "Zeekr 001"),
        ("Technologies", "Technology", "Blade Battery"),
        ("Videos", "Video", "BYD"),
    ],
)
def test_entity_is_placed_in_expected_group(group, result_type, query):
    response = InternalSearchService().search(query)
    assert find(response, group, result_type=result_type)


def test_inactive_video_is_excluded_without_breaking_search():
    video = VideoResource.objects.get(url="https://example.com/videos/chinese-ev-demo")
    video.is_active = False
    video.save(update_fields=["is_active"])
    response = InternalSearchService().search("BYD")
    assert not response.groups["Videos"]
    assert response.groups["Articles"]


def test_draft_article_is_not_returned():
    article = Article.objects.get(slug="blade-battery-overview")
    article.status = Article.Status.DRAFT
    article.save(update_fields=["status"])
    response = InternalSearchService().search("Blade Battery")
    assert not find(response, "Articles", title=article.title)


def test_search_page_handles_empty_and_successful_queries(client):
    empty = client.get(reverse("search:index"), {"q": " "})
    assert empty.status_code == 200
    assert "Введите поисковый запрос" in empty.content.decode()

    response = client.get(reverse("search:index"), {"q": "Zeekr 001"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Результаты для «Zeekr 001»" in content
    assert "Автомобили" in content
    assert "Zeekr 001" in content
