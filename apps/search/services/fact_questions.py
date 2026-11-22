"""Answers to factual questions such as «машина с самым большим запасом хода».

Full text search finds documents that *mention* the words of a query. A question with
a superlative asks for a *fact* stored as a number, so it is answered with an ordered
database query instead. Recognition uses explicit rules (word stems), no AI API:

1. the query must contain a ranking word («самый», «наибольший», «максимальный»…);
2. a stem names the parameter («запас» → ``range_km``, «разгон» → acceleration…);
3. optional filters: brand name and powertrain type (BEV, «электромобиль», «гибрид»…);
4. the direction is the parameter's natural "best" order unless the query asks
   explicitly for the largest/smallest value.

Every answer carries a human-readable explanation of what was recognised.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import F

from apps.cars.models import Brand, Modification
from apps.cars.units import format_power


@dataclass(frozen=True)
class FactAttribute:
    key: str
    label: str
    field: str  # ORM path from Modification
    unit: str
    stems: tuple[str, ...]
    best_is_max: bool  # True: "best" = the largest value (range); False: the smallest (0–100 time)


# Order matters: the first attribute whose stem occurs in the query wins,
# so «максимальная скорость» is matched by top speed before acceleration («быстр»).
ATTRIBUTES = (
    FactAttribute("range", "Запас хода", "range_km", "км", ("запас", "пробег", "дальнобойн"), True),
    FactAttribute("top_speed", "Максимальная скорость", "top_speed_kmh", "км/ч", ("скорост",), True),
    FactAttribute("acceleration", "Разгон 0–100 км/ч", "acceleration_0_100_s", "с", ("разгон", "быстр", "динамичн"), False),
    FactAttribute("power", "Мощность", "powertrain__system_power_kw", "кВт", ("мощн", "сильн", "лошад"), True),
    FactAttribute("battery", "Ёмкость батареи", "powertrain__battery__gross_capacity_kwh", "кВт·ч", ("батаре", "аккумулятор", "емкост"), True),
    FactAttribute("consumption", "Расход энергии", "energy_consumption_kwh_100km", "кВт·ч/100 км", ("расход", "экономичн", "потреблени"), False),
    FactAttribute("cargo", "Объём багажника", "cargo_l", "л", ("багажник", "вместительн"), True),
)

RANKING_STEMS = ("сам", "наибол", "наимен", "макс", "миним", "больш", "меньш", "лучш", "рекорд", "длинн", "коротк", "мал", "медлен", "худш", "слаб")
LARGEST_STEMS = ("наибол", "макс", "больш", "длинн", "высок")
SMALLEST_STEMS = ("наимен", "миним", "меньш", "мал", "коротк", "низк")
WORST_STEMS = ("медлен", "худш", "слаб")

# Powertrain type filter: Latin codes and Russian words with the same meaning.
POWERTRAIN_STEMS = (
    (("bev", "электромобил", "электрическ", "электрокар"), ("BEV",), "электромобили (BEV)"),
    (("phev", "erev", "hev", "гибрид"), ("PHEV", "EREV", "HEV"), "гибриды (PHEV/EREV/HEV)"),
    (("ice", "бензин", "двс"), ("ICE",), "автомобили с ДВС"),
)

TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)
RESULT_LIMIT = 3


@dataclass(frozen=True)
class FactAnswerItem:
    modification: Modification
    value: Decimal | int
    value_display: str


@dataclass(frozen=True)
class FactAnswer:
    attribute: FactAttribute
    largest_first: bool
    filters: tuple[str, ...]
    items: tuple[FactAnswerItem, ...]

    @property
    def title(self) -> str:
        adjective = "Наибольший" if self.largest_first else "Наименьший"
        return f"{adjective} показатель «{self.attribute.label.lower()}»"

    @property
    def explanation(self) -> str:
        order = "по убыванию" if self.largest_first else "по возрастанию"
        parts = [f"параметр «{self.attribute.label.lower()}»", f"сортировка {order}"]
        parts.extend(self.filters)
        return "Распознано: " + ", ".join(parts) + ". Модификации без этого значения не учитываются."


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")


def _has_stem(tokens: list[str], stems: tuple[str, ...]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)


def _format_value(value, attribute: FactAttribute, modification: Modification) -> str:
    if isinstance(value, Decimal):
        value = value.normalize()
        text = f"{value:f}".replace(".", ",")
    else:
        text = str(value)
    if attribute.key == "power":
        return format_power(value)
    result = f"{text} {attribute.unit}"
    if attribute.key == "range" and modification.range_cycle:
        result += f" ({modification.range_cycle})"
    return result


class FactQuestionService:
    def recognize(self, raw_query: str):
        """Return (attribute, largest_first, brand, powertrain types, filter labels) or None."""
        normalized = _normalize(raw_query or "")
        tokens = TOKEN_RE.findall(normalized)
        if not tokens or not _has_stem(tokens, RANKING_STEMS):
            return None
        attribute = next((item for item in ATTRIBUTES if _has_stem(tokens, item.stems)), None)
        if attribute is None:
            return None

        if _has_stem(tokens, SMALLEST_STEMS):
            largest_first = False
        elif _has_stem(tokens, LARGEST_STEMS):
            largest_first = True
        elif _has_stem(tokens, WORST_STEMS):
            largest_first = not attribute.best_is_max
        else:
            largest_first = attribute.best_is_max

        filters = []
        brand = None
        padded = f" {' '.join(tokens)} "
        for candidate in Brand.objects.filter(is_active=True).only("name", "slug"):
            if f" {_normalize(candidate.name)} " in padded:
                brand = candidate
                filters.append(f"марка {candidate.name}")
                break

        powertrain_types = ()
        for stems, types, label in POWERTRAIN_STEMS:
            if _has_stem(tokens, stems):
                powertrain_types = types
                filters.append(label)
                break
        return attribute, largest_first, brand, powertrain_types, tuple(filters)

    def answer(self, raw_query: str) -> FactAnswer | None:
        recognized = self.recognize(raw_query)
        if recognized is None:
            return None
        attribute, largest_first, brand, powertrain_types, filters = recognized

        queryset = Modification.objects.filter(
            is_active=True,
            generation__is_active=True,
            generation__model__is_active=True,
            generation__model__brand__is_active=True,
            **{f"{attribute.field}__isnull": False},
        )
        if brand is not None:
            queryset = queryset.filter(generation__model__brand=brand)
        if powertrain_types:
            queryset = queryset.filter(powertrain__type__in=powertrain_types)

        order = F(attribute.field).desc() if largest_first else F(attribute.field).asc()
        queryset = (
            queryset.select_related("generation__model__brand", "powertrain__drive_type")
            .annotate(fact_value=F(attribute.field))
            .order_by(order, "generation__model__brand__name", "generation__model__name", "name")[:RESULT_LIMIT]
        )
        items = tuple(
            FactAnswerItem(modification, modification.fact_value, _format_value(modification.fact_value, attribute, modification))
            for modification in queryset
        )
        return FactAnswer(attribute=attribute, largest_first=largest_first, filters=filters, items=items)
