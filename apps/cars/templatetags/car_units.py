from django import template

from apps.cars.units import format_power


register = template.Library()


@register.filter
def power(power_kw):
    """{{ powertrain.system_power_kw|power }} -> "220 кВт (299 л.с.)"."""
    return format_power(power_kw)
