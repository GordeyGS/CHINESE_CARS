from django.db.models import Count, Q
from django.shortcuts import render

from apps.cars.models import Brand, Model, Technology
from apps.knowledge.models import Article


def home(request):
    context = {
        "popular_brands": Brand.objects.filter(is_active=True)
        .select_related("manufacturer")
        .annotate(model_count=Count("models", filter=Q(models__is_active=True)))
        .order_by("-model_count", "name")[:4],
        "popular_models": Model.objects.filter(is_active=True)
        .select_related("brand")
        .prefetch_related("technologies")[:4],
        "articles": Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")[:3],
        "technologies": Technology.objects.filter(is_active=True).order_by("name")[:4],
    }
    return render(request, "core/home.html", context)
