from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from apps.knowledge.models import Article

from .forms import CarFilterForm, ComparisonForm
from .models import (
    BodyType,
    Brand,
    DriveType,
    DriverAssistanceSystem,
    Market,
    Model,
    Modification,
    Platform,
    Powertrain,
    Technology,
    TrimLevel,
)
from .services.catalog import filter_vehicle_models
from .services.comparison import build_comparison, comparison_queryset


CARS_PER_PAGE = 12
BRANDS_PER_PAGE = 24


def compare(request):
    modifications = comparison_queryset()
    is_submitted = "left" in request.GET or "right" in request.GET
    form = ComparisonForm(request.GET if is_submitted else None, queryset=modifications)
    context = {"form": form}
    if is_submitted and form.is_valid():
        left = form.cleaned_data["left"]
        right = form.cleaned_data["right"]
        context.update({"left": left, "right": right, "sections": build_comparison(left, right)})
    return render(request, "cars/compare.html", context)


def brand_list(request):
    brands = (
        Brand.objects.filter(is_active=True, manufacturer__is_active=True)
        .select_related("manufacturer", "origin_country")
        .annotate(model_count=Count("models", filter=Q(models__is_active=True)))
        .order_by("name")
    )
    manufacturer = request.GET.get("manufacturer")
    if manufacturer and manufacturer.isdigit():
        brands = brands.filter(manufacturer_id=manufacturer)
    page_obj = Paginator(brands, BRANDS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "cars/brand_list.html", {"brands": page_obj, "page_obj": page_obj})


def brand_detail(request, slug):
    brand = get_object_or_404(
        Brand.objects.select_related("manufacturer", "origin_country"), slug=slug, is_active=True
    )
    models = brand.models.filter(is_active=True).prefetch_related("technologies")
    articles = brand.articles.filter(status=Article.Status.PUBLISHED).select_related("category")
    technology_ids = set(models.values_list("technologies__id", flat=True))
    technologies = Technology.objects.filter(id__in=technology_ids, is_active=True)
    return render(
        request,
        "cars/brand_detail.html",
        {"brand": brand, "models": models, "articles": articles, "technologies": technologies},
    )


def car_list(request):
    form = CarFilterForm(request.GET or None)
    filters = {}
    if form.is_bound:
        form.is_valid()
        filters = dict(form.cleaned_data)
        if form.errors:
            # An invalid budget is reported to the user and ignored; other filters still apply.
            for name in ("min_price", "max_price", "currency"):
                filters.pop(name, None)
    cars = filter_vehicle_models(
        Model.objects.filter(is_active=True, brand__is_active=True).select_related("brand", "brand__manufacturer"),
        filters,
    ).prefetch_related("generations__body_type", "generations__modifications__powertrain__drive_type")
    page_obj = Paginator(cars, CARS_PER_PAGE).get_page(request.GET.get("page"))
    selected = {name: request.GET.get(name, "") for name in CarFilterForm.base_fields}
    active_filter_count = sum(1 for name, value in selected.items() if value)
    context = {
        "cars": page_obj,
        "page_obj": page_obj,
        "form": form,
        "brands": Brand.objects.filter(is_active=True),
        "body_types": BodyType.objects.filter(generations__model__is_active=True).distinct(),
        "powertrain_types": Powertrain.Type.choices,
        "drive_types": DriveType.objects.filter(powertrains__modifications__is_active=True).distinct(),
        "markets": Market.objects.filter(modification_offers__modification__is_active=True).distinct().order_by("name"),
        "currencies": TrimLevel.objects.filter(is_active=True, price_amount__isnull=False)
        .exclude(currency_code="")
        .values_list("currency_code", flat=True)
        .distinct()
        .order_by("currency_code"),
        "selected": selected,
        "active_filter_count": active_filter_count,
    }
    return render(request, "cars/model_list.html", context)


def model_detail(request, slug):
    vehicle = get_object_or_404(
        Model.objects.select_related("brand", "brand__manufacturer").prefetch_related(
            "technologies",
            "video_resources",
            "generations__platform",
            "generations__body_type",
            "generations__technologies",
            "generations__modifications__powertrain__drive_type",
        ),
        slug=slug,
        is_active=True,
    )
    articles = vehicle.articles.filter(status=Article.Status.PUBLISHED).select_related("category")
    is_favorite = request.user.is_authenticated and vehicle.favorited_by.filter(user=request.user).exists()
    return render(
        request, "cars/model_detail.html", {"vehicle": vehicle, "articles": articles, "is_favorite": is_favorite}
    )


def modification_detail(request, slug):
    modification = get_object_or_404(
        Modification.objects.select_related(
            "generation__model__brand__manufacturer",
            "generation__platform",
            "generation__body_type",
            "powertrain__battery__technology",
            "powertrain__combustion_engine",
            "powertrain__drive_type",
            "powertrain__transmission",
        ).prefetch_related(
            "powertrain__motor_links__electric_motor",
            "market_offers__market",
            "market_offers__trim_levels",
            "adas_links__adas",
            "generation__technologies",
            "generation__model__technologies",
        ),
        slug=slug,
        is_active=True,
    )
    technology_ids = set(modification.generation.model.technologies.values_list("id", flat=True))
    technology_ids.update(modification.generation.technologies.values_list("id", flat=True))
    if modification.powertrain.battery and modification.powertrain.battery.technology_id:
        technology_ids.add(modification.powertrain.battery.technology_id)
    technologies = Technology.objects.filter(id__in=technology_ids, is_active=True)
    return render(
        request,
        "cars/modification_detail.html",
        {"modification": modification, "technologies": technologies},
    )


def technology_list(request):
    return render(
        request,
        "cars/technology_list.html",
        {
            "technologies": Technology.objects.filter(is_active=True),
            "platforms": Platform.objects.filter(is_active=True).select_related("manufacturer"),
            "adas_systems": DriverAssistanceSystem.objects.filter(is_active=True),
        },
    )


def technology_detail(request, slug):
    technology = get_object_or_404(
        Technology.objects.prefetch_related("models__brand", "articles", "video_resources"), slug=slug, is_active=True
    )
    articles = technology.articles.filter(status=Article.Status.PUBLISHED)
    return render(request, "cars/technology_detail.html", {"technology": technology, "articles": articles})
