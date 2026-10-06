from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch
from django.urls import reverse

from apps.cars.models import Modification, ModificationADAS, TrimLevel
from apps.recommendations.models import RecommendationRule


@dataclass(frozen=True)
class Criterion:
    field: str
    operator: str
    expected: object
    label: str
    weight: Decimal = Decimal("1")
    negate: bool = False


@dataclass(frozen=True)
class RecommendationResult:
    modification: Modification
    score: int
    matched: tuple[str, ...]
    compromises: tuple[str, ...]
    exact: bool
    price_text: str
    detail_url: str
    compare_url: str
    hard_match_count: int


def recommendation_queryset():
    active_trims = TrimLevel.objects.filter(is_active=True).order_by("price_amount", "name")
    active_adas = ModificationADAS.objects.exclude(availability=ModificationADAS.Availability.UNAVAILABLE).select_related("adas")
    return Modification.objects.filter(
        is_active=True,
        generation__is_active=True,
        generation__model__is_active=True,
        generation__model__brand__is_active=True,
    ).select_related(
        "generation__body_type",
        "generation__model__brand",
        "powertrain__drive_type",
        "powertrain__battery__technology",
    ).prefetch_related(
        "generation__technologies",
        "generation__model__technologies",
        Prefetch("adas_links", queryset=active_adas, to_attr="available_adas_links"),
        "market_offers__market",
        Prefetch("market_offers__trim_levels", queryset=active_trims, to_attr="active_trims"),
    )


class RecommendationEngine:
    """Deterministic rule evaluator for active Modification objects."""

    RESULT_LIMIT = 5

    def __init__(self, criteria):
        self.criteria = criteria
        self.hard = self._build_hard_criteria()
        self.preferences = self._build_preferences()
        self.database_rules = list(
            RecommendationRule.objects.filter(is_active=True).prefetch_related("conditions").order_by("priority", "name")
        )

    def recommend(self):
        evaluated = [self._evaluate(item) for item in recommendation_queryset()]
        exact = [result for result in evaluated if result.exact]
        if exact:
            return sorted(exact, key=self._sort_key)[: self.RESULT_LIMIT], True
        return sorted(evaluated, key=self._partial_sort_key)[: self.RESULT_LIMIT], False

    def _build_hard_criteria(self):
        data = self.criteria
        criteria = []
        if data.get("body_type"):
            criteria.append(Criterion("body_type", "eq", data["body_type"].code, f"кузов: {data['body_type'].name}"))
        if data.get("powertrain_type"):
            criteria.append(Criterion("powertrain_type", "eq", data["powertrain_type"], f"силовая установка: {data['powertrain_type']}"))
        if data.get("drive_type"):
            criteria.append(Criterion("drive_type", "eq", data["drive_type"].code, f"привод: {data['drive_type'].code}"))
        if data.get("market"):
            criteria.append(Criterion("market", "eq", data["market"].code, f"доступен на рынке {data['market'].name}"))
        if data.get("min_price") is not None:
            criteria.append(Criterion("price", "gte", data["min_price"], f"цена не ниже {data['min_price']} {data['currency']}"))
        if data.get("max_price") is not None:
            criteria.append(Criterion("price", "lte", data["max_price"], f"цена не выше {data['max_price']} {data['currency']}"))
        return criteria

    def _build_preferences(self):
        data = self.criteria
        preferences = []
        if data.get("min_power_kw") is not None:
            preferences.append(Criterion("power_kw", "gte", data["min_power_kw"], f"мощность не ниже {data['min_power_kw']} кВт"))
        if data.get("min_battery_kwh") is not None:
            preferences.append(Criterion("battery_capacity", "gte", data["min_battery_kwh"], f"батарея не меньше {data['min_battery_kwh']} кВт·ч"))
        if data.get("technology"):
            preferences.append(Criterion("technology", "contains", data["technology"].id, f"есть технология {data['technology'].name}"))
        if data.get("adas"):
            preferences.append(Criterion("adas", "contains", data["adas"].id, f"есть ADAS: {data['adas'].name}"))
        return preferences

    def _evaluate(self, modification):
        hard_checks = [(criterion, self._matches(modification, criterion)) for criterion in self.hard]
        preference_checks = [(criterion, self._matches(modification, criterion)) for criterion in self.preferences]
        matched = [criterion.label for criterion, ok in hard_checks + preference_checks if ok]
        compromises = [f"не выполнено пожелание: {criterion.label}" for criterion, ok in preference_checks if not ok]
        earned = sum((criterion.weight for criterion, ok in hard_checks + preference_checks if ok), Decimal("0"))
        possible = sum((criterion.weight for criterion, _ in hard_checks + preference_checks), Decimal("0"))
        database_hard_ok = True

        for rule in self.database_rules:
            conditions = [Criterion(item.field, item.operator, item.value_json, rule.name, rule.weight, item.negate) for item in rule.conditions.all()]
            rule_ok = bool(conditions) and all(self._matches(modification, item) for item in conditions)
            possible += rule.weight
            if rule_ok:
                earned += rule.weight
                matched.append(rule.explanation_template)
            elif rule.rule_kind == RecommendationRule.Kind.HARD:
                database_hard_ok = False
                compromises.append(f"не выполнено обязательное правило «{rule.name}»")
            else:
                compromises.append(f"не выполнено предпочтение «{rule.name}»")

        exact = all(ok for _, ok in hard_checks) and database_hard_ok
        score = round(100 * earned / possible) if possible else 100
        return RecommendationResult(
            modification=modification,
            score=score,
            matched=tuple(matched),
            compromises=tuple(compromises),
            exact=exact,
            price_text=self._price_text(modification),
            detail_url=reverse("cars:modification-detail", args=[modification.slug]),
            compare_url=f"{reverse('cars:compare')}?left={modification.pk}",
            hard_match_count=sum(ok for _, ok in hard_checks),
        )

    def _matches(self, modification, criterion):
        actual = self._value(modification, criterion.field)
        if actual is None:
            matched = False
        elif criterion.operator == "contains":
            matched = criterion.expected in actual
        elif criterion.operator == "in":
            matched = actual in criterion.expected
        elif criterion.operator == "eq":
            matched = criterion.expected in actual if isinstance(actual, set) else actual == criterion.expected
        elif criterion.operator == "gte":
            matched = actual >= Decimal(str(criterion.expected))
        elif criterion.operator == "lte":
            matched = actual <= Decimal(str(criterion.expected))
        else:
            matched = False
        return not matched if criterion.negate else matched

    def _value(self, modification, field):
        if field == "body_type": return modification.generation.body_type.code
        if field == "powertrain_type": return modification.powertrain.type
        if field == "drive_type": return modification.powertrain.drive_type.code
        if field == "range_km": return Decimal(modification.range_km) if modification.range_km is not None else None
        if field == "power_kw": return modification.powertrain.system_power_kw
        if field == "seats": return Decimal(modification.seats) if modification.seats is not None else None
        if field == "battery_capacity":
            battery = modification.powertrain.battery
            return (battery.usable_capacity_kwh or battery.gross_capacity_kwh) if battery else None
        if field == "market": return {offer.market.code for offer in modification.market_offers.all()}
        if field == "price":
            prices = self._eligible_prices(modification)
            return min(prices) if prices else None
        if field == "technology":
            identifiers = {item.id for item in modification.generation.technologies.all()}
            identifiers.update(item.id for item in modification.generation.model.technologies.all())
            battery = modification.powertrain.battery
            if battery and battery.technology_id: identifiers.add(battery.technology_id)
            return identifiers
        if field == "adas": return {link.adas_id for link in modification.available_adas_links}
        return None

    def _eligible_prices(self, modification):
        market = self.criteria.get("market")
        currency = self.criteria.get("currency")
        return [trim.price_amount for offer in modification.market_offers.all() if not market or offer.market_id == market.id for trim in offer.active_trims if trim.price_amount is not None and (not currency or trim.currency_code == currency)]

    @staticmethod
    def _price_text(modification):
        offers = [f"{trim.price_amount:,.0f} {trim.currency_code} · {offer.market.name} · {trim.name}".replace(",", " ") for offer in modification.market_offers.all() for trim in offer.active_trims if trim.price_amount is not None]
        return "; ".join(offers) or "Цена не указана"

    @staticmethod
    def _sort_key(result): return (-result.score, str(result.modification))

    @staticmethod
    def _partial_sort_key(result): return (-result.hard_match_count, -result.score, str(result.modification))
