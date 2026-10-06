from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from apps.knowledge.models import Article

from .models import (
    BodyType,
    Brand,
    DriveType,
    DriverAssistanceSystem,
    Model,
    Modification,
    Platform,
    Powertrain,
    Technology,
)


def brand_list(request):
    brands = (
        Brand.objects.filter(is_active=True, manufacturer__is_active=True)
        .select_related("manufacturer", "origin_country")
        .annotate(model_count=Count("models", filter=Q(models__is_active=True)))
    )
    manufacturer = request.GET.get("manufacturer")
    if manufacturer:
        brands = brands.filter(manufacturer_id=manufacturer)
    return render(request, "cars/brand_list.html", {"brands": brands})


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
    cars = Model.objects.filter(is_active=True, brand__is_active=True).select_related("brand", "brand__manufacturer")
    selected = {
        "brand": request.GET.get("brand", ""),
        "body": request.GET.get("body", ""),
        "powertrain": request.GET.get("powertrain", ""),
        "drive": request.GET.get("drive", ""),
    }
    if selected["brand"]:
        cars = cars.filter(brand__slug=selected["brand"])
    if selected["body"]:
        cars = cars.filter(generations__body_type__code=selected["body"])
    if selected["powertrain"]:
        cars = cars.filter(generations__modifications__powertrain__type=selected["powertrain"])
    if selected["drive"]:
        cars = cars.filter(generations__modifications__powertrain__drive_type__code=selected["drive"])
    cars = cars.prefetch_related("generations__body_type", "generations__modifications__powertrain").distinct()
    context = {
        "cars": cars,
        "brands": Brand.objects.filter(is_active=True),
        "body_types": BodyType.objects.filter(generations__model__is_active=True).distinct(),
        "powertrain_types": Powertrain.Type.choices,
        "drive_types": DriveType.objects.filter(powertrains__modifications__is_active=True).distinct(),
        "selected": selected,
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
    return render(request, "cars/model_detail.html", {"vehicle": vehicle, "articles": articles})


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
    return render(request, "cars/modification_detail.html", {"modification": modification})


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
