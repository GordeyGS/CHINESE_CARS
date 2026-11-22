from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render

from .models import Article, Source


ARTICLES_PER_PAGE = 10
SOURCES_PER_PAGE = 20


def article_list(request):
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")
    )
    page_obj = Paginator(articles, ARTICLES_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "knowledge/article_list.html", {"articles": page_obj, "page_obj": page_obj})


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


def source_list(request):
    """Public registry of active sources and the published articles that cite them."""
    published = Article.objects.filter(status=Article.Status.PUBLISHED).only("title", "slug")
    sources = (
        Source.objects.filter(is_active=True)
        .annotate(article_count=Count("articles", filter=Q(articles__status=Article.Status.PUBLISHED)))
        .prefetch_related(Prefetch("articles", queryset=published, to_attr="published_articles"))
        .order_by("publisher", "name")
    )
    page_obj = Paginator(sources, SOURCES_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "knowledge/source_list.html", {"sources": page_obj, "page_obj": page_obj})
