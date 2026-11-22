from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch
from django.template.defaultfilters import floatformat

from ..models import Modification, Powertrain, TrimLevel
from ..units import format_power


@dataclass(frozen=True)
class ComparisonValue:
    text: str
    state: str = "value"


NOT_AVAILABLE = ComparisonValue("Нет данных", "missing")
NOT_APPLICABLE = ComparisonValue("Не применяется", "not-applicable")


def comparison_queryset():
    return (
        Modification.objects.filter(
            is_active=True,
            generation__is_active=True,
            generation__model__is_active=True,
            generation__model__brand__is_active=True,
        )
        .select_related(
            "generation__model__brand",
            "generation__platform",
            "generation__body_type",
            "powertrain__drive_type",
            "powertrain__transmission",
            "powertrain__combustion_engine",
            "powertrain__battery__technology",
        )
        .prefetch_related(
            "powertrain__motor_links__electric_motor",
            Prefetch("market_offers__trim_levels", queryset=TrimLevel.objects.filter(is_active=True)),
            "market_offers__market",
            "adas_links__adas",
            "generation__model__technologies",
            "generation__technologies",
        )
        .order_by("generation__model__brand__name", "generation__model__name", "name")
    )


def _number(value):
    """Show 230.00 as 230 (same rule as |floatformat:"-2" in detail pages)."""
    if isinstance(value, Decimal):
        return floatformat(value, -2)
    return value


def _value(value, suffix=""):
    if value is None or value == "":
        return NOT_AVAILABLE
    return ComparisonValue(f"{_number(value)}{suffix}")


def _power_value(power_kw):
    return NOT_AVAILABLE if power_kw is None else ComparisonValue(format_power(power_kw))


def _combustion_engine_value(modification):
    powertrain = modification.powertrain
    engine = powertrain.combustion_engine
    if powertrain.type == Powertrain.Type.BEV:
        return NOT_APPLICABLE
    if not engine:
        return NOT_AVAILABLE
    details = [engine.code, engine.get_fuel_type_display()]
    if engine.displacement_cc:
        details.append(f"{engine.displacement_cc} см³")
    if engine.power_kw is not None:
        details.append(format_power(engine.power_kw))
    return ComparisonValue(" · ".join(details))


def _motors_value(modification):
    if modification.powertrain.type == Powertrain.Type.ICE:
        return NOT_APPLICABLE
    axle_labels = {"front": "передняя ось", "rear": "задняя ось", "central": "центральное расположение"}
    motors = []
    for link in modification.powertrain.motor_links.all():
        details = [link.electric_motor.code, axle_labels.get(link.axle, link.axle)]
        if link.quantity > 1:
            details.append(f"× {link.quantity}")
        if link.electric_motor.power_kw is not None:
            details.append(format_power(link.electric_motor.power_kw))
        motors.append(" · ".join(details))
    return ComparisonValue("\n".join(motors)) if motors else NOT_AVAILABLE


def _battery_value(modification, attribute, suffix=""):
    powertrain = modification.powertrain
    if powertrain.type == Powertrain.Type.ICE:
        return NOT_APPLICABLE
    if not powertrain.battery:
        return NOT_AVAILABLE
    return _value(getattr(powertrain.battery, attribute), suffix)


def _offers_value(modification, kind):
    lines = []
    for offer in modification.market_offers.all():
        if kind == "market":
            dates = ""
            if offer.available_from:
                dates = f" (с {offer.available_from:%d.%m.%Y}"
                dates += f" по {offer.available_to:%d.%m.%Y})" if offer.available_to else ")"
            lines.append(f"{offer.market.name}{dates}")
            continue
        for trim in offer.trim_levels.all():
            if kind == "trim":
                lines.append(f"{offer.market.name}: {trim.name}")
            elif trim.price_amount is not None:
                period = ""
                if trim.valid_from:
                    period = f"; с {trim.valid_from:%d.%m.%Y}"
                    if trim.valid_to:
                        period += f" по {trim.valid_to:%d.%m.%Y}"
                lines.append(f"{offer.market.name}, {trim.name}: {_number(trim.price_amount)} {trim.currency_code}{period}")
    return ComparisonValue("\n".join(lines)) if lines else NOT_AVAILABLE


def _adas_value(modification):
    availability = {"standard": "стандартно", "optional": "опция", "unavailable": "недоступно"}
    values = [
        f"{link.adas.name} — {availability.get(link.availability, link.availability)}"
        for link in modification.adas_links.all()
    ]
    return ComparisonValue("\n".join(values)) if values else NOT_AVAILABLE


def _technologies_value(modification):
    technologies = {
        technology.name
        for technology in (*modification.generation.model.technologies.all(), *modification.generation.technologies.all())
        if technology.is_active
    }
    battery = modification.powertrain.battery
    if battery and battery.technology and battery.technology.is_active:
        technologies.add(battery.technology.name)
    return ComparisonValue("\n".join(sorted(technologies))) if technologies else NOT_AVAILABLE


def build_comparison(left, right):
    def row(label, getter):
        left_value = getter(left)
        right_value = getter(right)
        return {"label": label, "left": left_value, "right": right_value, "different": left_value != right_value}

    return [
        {
            "title": "Основная информация",
            "rows": [
                row("Марка", lambda item: _value(item.generation.model.brand.name)),
                row("Модель", lambda item: _value(item.generation.model.name)),
                row("Поколение", lambda item: _value(item.generation.name)),
                row("Модификация", lambda item: _value(item.name)),
                row("Кузов", lambda item: _value(item.generation.body_type.name)),
                row("Платформа", lambda item: _value(item.generation.platform.name)),
            ],
        },
        {
            "title": "Силовая установка",
            "rows": [
                row("Тип", lambda item: _value(item.powertrain.type)),
                row("Привод", lambda item: _value(f"{item.powertrain.drive_type.code} — {item.powertrain.drive_type.name}")),
                row("Трансмиссия", lambda item: _value(item.powertrain.transmission.name if item.powertrain.transmission else None)),
                row("Двигатель внутреннего сгорания", _combustion_engine_value),
                row("Электродвигатели", _motors_value),
                row("Суммарная мощность", lambda item: _power_value(item.powertrain.system_power_kw)),
                row("Суммарный крутящий момент", lambda item: _value(item.powertrain.system_torque_nm, " Н·м")),
            ],
        },
        {
            "title": "Энергия и батарея",
            "rows": [
                row("Батарея", lambda item: _battery_value(item, "name")),
                row("Полная ёмкость", lambda item: _battery_value(item, "gross_capacity_kwh", " кВт·ч")),
                row("Полезная ёмкость", lambda item: _battery_value(item, "usable_capacity_kwh", " кВт·ч")),
                row("Химический состав", lambda item: _battery_value(item, "chemistry")),
                row("Напряжение", lambda item: _battery_value(item, "voltage_v", " В")),
                row("Запас хода", lambda item: _value(item.range_km, f" км {item.range_cycle}".rstrip())),
                row("Расход энергии", lambda item: _value(item.energy_consumption_kwh_100km, " кВт·ч/100 км")),
                row(
                    "Расход топлива",
                    lambda item: NOT_APPLICABLE
                    if item.powertrain.type == Powertrain.Type.BEV
                    else _value(item.fuel_consumption_l_100km, " л/100 км"),
                ),
            ],
        },
        {
            "title": "Рынки и комплектации",
            "rows": [
                row("Рынки", lambda item: _offers_value(item, "market")),
                row("Комплектации", lambda item: _offers_value(item, "trim")),
                row("Цены", lambda item: _offers_value(item, "price")),
            ],
        },
        {
            "title": "Функции и знания",
            "rows": [row("ADAS", _adas_value), row("Технологии", _technologies_value)],
        },
    ]
