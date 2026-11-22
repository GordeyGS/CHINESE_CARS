"""Catalog filtering for vehicle models.

All modification-level conditions are checked on the *same* modification through
one EXISTS subquery. Otherwise a model with "BEV + RWD" and "PHEV + AWD" versions
would wrongly match the filter "BEV + AWD". Unknown prices (NULL) never satisfy a
price filter.
"""

from django.db.models import Exists, OuterRef

from ..models import Modification, ModificationMarket, TrimLevel


def filter_vehicle_models(queryset, filters):
    if filters.get("brand"):
        queryset = queryset.filter(brand__slug=filters["brand"])

    modifications = Modification.objects.filter(
        generation__model=OuterRef("pk"),
        generation__is_active=True,
        is_active=True,
    )
    has_modification_filter = False
    if filters.get("body"):
        modifications = modifications.filter(generation__body_type__code=filters["body"])
        has_modification_filter = True
    if filters.get("powertrain"):
        modifications = modifications.filter(powertrain__type=filters["powertrain"])
        has_modification_filter = True
    if filters.get("drive"):
        modifications = modifications.filter(powertrain__drive_type__code=filters["drive"])
        has_modification_filter = True

    market = filters.get("market")
    has_price = filters.get("min_price") is not None or filters.get("max_price") is not None
    if market or has_price:
        trims_or_offers = _matching_offers(filters)
        modifications = modifications.filter(Exists(trims_or_offers))
        has_modification_filter = True

    if has_modification_filter:
        queryset = queryset.filter(Exists(modifications))
    return queryset


def _matching_offers(filters):
    """Offers (or priced trims) of the outer modification that satisfy market/price."""
    if filters.get("min_price") is None and filters.get("max_price") is None:
        return ModificationMarket.objects.filter(
            modification=OuterRef("pk"), market__code=filters["market"]
        )

    trims = TrimLevel.objects.filter(
        modification_market__modification=OuterRef("pk"),
        is_active=True,
        price_amount__isnull=False,
        currency_code=filters["currency"],
    )
    if filters.get("market"):
        trims = trims.filter(modification_market__market__code=filters["market"])
    if filters.get("min_price") is not None:
        trims = trims.filter(price_amount__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        trims = trims.filter(price_amount__lte=filters["max_price"])
    return trims
