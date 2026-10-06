from django.shortcuts import get_object_or_404, render

from .models import Article


def article_list(request):
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")
    )
    return render(request, "knowledge/article_list.html", {"articles": articles})


def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.select_related("category", "author").prefetch_related(
            "tags",
            "sources",
            "brands",
            "vehicle_models__brand",
            "modifications__generation__model__brand",
            "technologies",
            "video_resources",
            "related_articles",
        ),
        slug=slug,
        status=Article.Status.PUBLISHED,
    )
    return render(request, "knowledge/article_detail.html", {"article": article})
