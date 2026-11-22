import pytest
from django.core.management import call_command
from django.urls import reverse

from .services import FactQuestionService, SearchCoordinator, NullExternalSearchProvider


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    # Demo set: BYD Seal — 570 км, 5.9 с, 230 кВт; Zeekr 001 — 580 км, 3.8 с, 400 кВт.
    call_command("load_demo_data", verbosity=0)


def names(answer):
    return [f"{item.modification.generation.model.name} {item.modification.name}" for item in answer.items]


def test_largest_range_question_returns_car_with_largest_range():
    answer = FactQuestionService().answer("машина с самым большим запасом хода")

    assert answer.attribute.key == "range"
    assert answer.largest_first is True
    assert [item.value for item in answer.items] == [580, 570]
    assert names(answer)[0].startswith("001")
    assert answer.items[0].value_display.startswith("580 км")
    assert "запас хода" in answer.explanation and "по убыванию" in answer.explanation


def test_typo_in_word_ending_is_tolerated_by_stems():
    answer = FactQuestionService().answer("машина с самым большим запасам хода")

    assert answer is not None and answer.items[0].value == 580


def test_fastest_car_uses_smallest_acceleration_time():
    answer = FactQuestionService().answer("самая быстрая машина")

    assert answer.attribute.key == "acceleration"
    assert answer.largest_first is False
    assert [str(item.value) for item in answer.items] == ["3.80", "5.90"]


def test_explicit_smallest_reverses_order():
    answer = FactQuestionService().answer("наименьший запас хода")

    assert answer.largest_first is False
    assert answer.items[0].value == 570


def test_brand_and_powertrain_filters_are_applied_and_explained():
    service = FactQuestionService()

    byd = service.answer("самый мощный BYD")
    assert [item.value for item in byd.items] == [230]
    assert "марка BYD" in byd.explanation

    hybrids = service.answer("самый мощный гибрид")
    assert hybrids.items == ()
    assert "гибриды" in hybrids.explanation


@pytest.mark.parametrize("query", ["BYD", "Blade Battery", "запас хода", "Какие электромобили BYD используют Blade Battery?"])
def test_ordinary_queries_are_not_treated_as_fact_questions(query):
    assert FactQuestionService().answer(query) is None


def test_coordinator_returns_fact_answer_next_to_internal_results():
    response = SearchCoordinator(external_provider=NullExternalSearchProvider()).search("самый большой запас хода")

    assert response.fact_answer is not None
    assert response.internal is not None


def test_search_page_shows_answer_card_with_compare_link(client):
    response = client.get(reverse("search:index"), {"q": "машина с самым большим запасом хода"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Ответ из базы знаний" in content
    assert "580 км" in content
    assert "Сравнить первые два" in content


def test_search_page_without_fact_question_has_no_answer_card(client):
    response = client.get(reverse("search:index"), {"q": "Blade Battery"})

    assert "Ответ из базы знаний" not in response.content.decode()
