from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.cars.models import DriveType, Market

from .forms import RecommendationForm
from .models import RecommendationCondition, RecommendationRule
from .services import RecommendationEngine


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    # Demo set: BYD Seal BEV RWD (230 kW, 570 km, 46 990 EUR) and
    # Zeekr 001 BEV AWD (400 kW, 580 km, 67 490 EUR); soft rules range ≥ 500 km, power ≥ 300 kW.
    call_command("load_demo_data", verbosity=0)


def recommend(data):
    form = RecommendationForm(data)
    assert form.is_valid(), form.errors
    return RecommendationEngine(form.cleaned_data).recommend()


def drive(code):
    return DriveType.objects.get(code=code).pk


def test_bev_rwd_finds_byd_seal_with_explanation():
    results, exact = recommend({"powertrain_type": "BEV", "drive_type": drive("RWD")})

    assert exact is True
    assert [result.modification.slug for result in results] == ["byd-seal-long-range-rwd"]
    best = results[0]
    assert "силовая установка: BEV" in best.matched
    assert "привод: RWD" in best.matched
    assert "запас хода не менее 500 км" in best.matched
    assert "не выполнено предпочтение «Высокая мощность»" in best.compromises
    # 2 hard criteria + long-range rule = 3 of 4 weights.
    assert best.score == 75


def test_bev_awd_finds_zeekr_001_with_full_score():
    results, exact = recommend({"powertrain_type": "BEV", "drive_type": drive("AWD")})

    assert exact is True
    assert results[0].modification.slug == "zeekr-001-awd-100"
    assert results[0].score == 100
    assert results[0].compromises == ()


def test_impossible_combination_returns_marked_partial_matches():
    results, exact = recommend({"powertrain_type": "ICE", "drive_type": drive("AWD")})

    assert exact is False
    assert results, "nearest variants must still be shown"
    assert all(not result.exact for result in results)
    # Zeekr satisfies the AWD condition, so it ranks above the Seal.
    assert results[0].modification.slug == "zeekr-001-awd-100"
    assert results[0].hard_match_count == 1


def test_score_formula_uses_weights_of_user_criteria():
    RecommendationRule.objects.update(is_active=False)

    results, exact = recommend({"powertrain_type": "BEV", "min_power_kw": "1000"})

    assert exact is True
    assert {result.score for result in results} == {50}
    assert all("не выполнено пожелание: мощность не ниже 1000 кВт" in r.compromises for r in results)


def test_active_hard_rule_from_database_excludes_exact_matches():
    rule = RecommendationRule.objects.create(
        name="Огромный запас хода",
        code="huge-range",
        rule_kind=RecommendationRule.Kind.HARD,
        weight=Decimal("2"),
        explanation_template="запас хода не менее 900 км",
    )
    RecommendationCondition.objects.create(rule=rule, field="range_km", operator="gte", value_json=900)

    results, exact = recommend({"powertrain_type": "BEV"})

    assert exact is False
    assert all("не выполнено обязательное правило «Огромный запас хода»" in r.compromises for r in results)


def test_disabled_rule_is_ignored_without_code_changes():
    RecommendationRule.objects.filter(code="high-power").update(is_active=False)

    results, _ = recommend({"powertrain_type": "BEV", "drive_type": drive("RWD")})

    assert results[0].score == 100


def test_negated_condition_inverts_result():
    RecommendationRule.objects.update(is_active=False)
    rule = RecommendationRule.objects.create(
        name="Не задний привод", code="not-rwd", rule_kind=RecommendationRule.Kind.HARD,
        explanation_template="привод не RWD",
    )
    RecommendationCondition.objects.create(rule=rule, field="drive_type", operator="eq", value_json="RWD", negate=True)

    results, exact = recommend({"powertrain_type": "BEV"})

    assert exact is True
    assert [result.modification.slug for result in results] == ["zeekr-001-awd-100"]


def test_budget_uses_market_price_and_currency():
    europe = Market.objects.get(code="EU")
    results, exact = recommend({"market": europe.pk, "max_price": "50000", "currency": "EUR"})

    assert exact is True
    assert [result.modification.slug for result in results] == ["byd-seal-long-range-rwd"]
    assert "46 990 EUR" in results[0].price_text


def test_budget_requires_market_and_currency():
    form = RecommendationForm({"max_price": "50000"})

    assert not form.is_valid()
    assert "market" in form.errors
    assert "currency" in form.errors


def test_recommendation_page_shows_results_and_partial_warning(client):
    exact_page = client.get(reverse("recommendations:index"), {"powertrain_type": "BEV", "drive_type": drive("AWD")})
    content = exact_page.content.decode()
    assert exact_page.status_code == 200
    assert "Zeekr 001" in content
    assert "Полных совпадений нет" not in content

    partial_page = client.get(reverse("recommendations:index"), {"powertrain_type": "ICE"})
    assert "Полных совпадений нет" in partial_page.content.decode()
    assert "Частично подходит" in partial_page.content.decode()
