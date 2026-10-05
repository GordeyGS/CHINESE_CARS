from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class RecommendationRule(models.Model):
    class Kind(models.TextChoices):
        HARD = "hard", "Hard filter"
        SOFT = "soft", "Soft preference"

    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    rule_kind = models.CharField(max_length=10, choices=Kind.choices)
    weight = models.DecimalField(max_digits=7, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    explanation_template = models.CharField(max_length=500)
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        constraints = [models.CheckConstraint(condition=models.Q(weight__gte=0), name="ck_rule_weight_nonnegative")]

    def __str__(self):
        return self.name


class RecommendationCondition(models.Model):
    class Field(models.TextChoices):
        BODY_TYPE = "body_type", "Body type"
        POWERTRAIN_TYPE = "powertrain_type", "Powertrain type"
        DRIVE_TYPE = "drive_type", "Drive type"
        MARKET = "market", "Market"
        PRICE = "price", "Price"
        RANGE = "range_km", "Range"
        POWER = "power_kw", "System power"
        SEATS = "seats", "Seats"

    class Operator(models.TextChoices):
        EQ = "eq", "Equals"
        IN = "in", "In list"
        LTE = "lte", "Less than or equal"
        GTE = "gte", "Greater than or equal"

    rule = models.ForeignKey(RecommendationRule, on_delete=models.CASCADE, related_name="conditions")
    field = models.CharField(max_length=30, choices=Field.choices)
    operator = models.CharField(max_length=10, choices=Operator.choices)
    value_json = models.JSONField()
    negate = models.BooleanField(default=False)

    class Meta:
        ordering = ["rule", "id"]

    def clean(self):
        super().clean()
        value = self.value_json
        if self.operator == self.Operator.IN:
            if not isinstance(value, list) or not value or any(isinstance(item, (dict, list)) for item in value):
                raise ValidationError({"value_json": "The 'in' operator requires a non-empty list of scalar values."})
        elif isinstance(value, (dict, list)) or value is None:
            raise ValidationError({"value_json": "This operator requires one scalar value."})

        numeric_fields = {self.Field.PRICE, self.Field.RANGE, self.Field.POWER, self.Field.SEATS}
        if self.field in numeric_fields:
            values = value if isinstance(value, list) else [value]
            try:
                if any(Decimal(str(item)) < 0 for item in values):
                    raise ValidationError({"value_json": "Numeric operands cannot be negative."})
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({"value_json": "This field requires numeric operands."}) from None
        elif self.operator in {self.Operator.LTE, self.Operator.GTE}:
            raise ValidationError({"operator": "Ordering operators are only valid for numeric fields."})

    def __str__(self):
        return f"{self.rule.code}: {self.field} {self.operator} {self.value_json}"
