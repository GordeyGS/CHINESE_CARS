import pytest
from django.core.exceptions import ValidationError

from .models import RecommendationCondition, RecommendationRule


@pytest.mark.django_db
def test_recommendation_condition_accepts_limited_operand():
    rule = RecommendationRule.objects.create(
        name="Minimum range", code="minimum-range", rule_kind="soft", explanation_template="Range matches."
    )
    condition = RecommendationCondition(rule=rule, field="range_km", operator="gte", value_json=400)
    condition.full_clean()
    condition.save()
    assert rule.conditions.get() == condition


@pytest.mark.django_db
def test_recommendation_condition_rejects_nested_json():
    rule = RecommendationRule.objects.create(
        name="Drive", code="drive", rule_kind="hard", explanation_template="Drive matches."
    )
    condition = RecommendationCondition(rule=rule, field="drive_type", operator="eq", value_json={"code": "AWD"})
    with pytest.raises(ValidationError):
        condition.full_clean()
