"""Display units for power.

The database stores power only in kilowatts (SI unit used by manufacturers' type
approval data). Horsepower is derived for display, so the two values can never
disagree. "л.с." is metric horsepower (PS): 1 kW = 1.35962 л.с.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.template.defaultfilters import floatformat


KW_TO_HP = Decimal("1.35962")


def kw_to_hp(power_kw):
    if power_kw is None:
        return None
    return int((Decimal(str(power_kw)) * KW_TO_HP).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_power(power_kw):
    """220 -> "220 кВт (299 л.с.)"; None -> ""."""
    if power_kw is None:
        return ""
    return f"{floatformat(power_kw, -2)} кВт ({kw_to_hp(power_kw)} л.с.)"
