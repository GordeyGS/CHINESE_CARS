from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import CommentForm
from .models import Article, ArticleComment, Category, Source, Tag


ARTICLES_PER_PAGE = 10
SOURCES_PER_PAGE = 20
PUBLISHED = Q(articles__status=Article.Status.PUBLISHED)


def article_list(request):
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")
    )
    active_tag = Tag.objects.filter(slug=request.GET.get("tag", "")).first()
    active_category = Category.objects.filter(slug=request.GET.get("category", "")).first()
    if active_tag:
        articles = articles.filter(tags=active_tag)
    if active_category:
        articles = articles.filter(category=active_category)
    page_obj = Paginator(articles, ARTICLES_PER_PAGE).get_page(request.GET.get("page"))
    context = {
        "articles": page_obj,
        "page_obj": page_obj,
        "active_tag": active_tag,
        "active_category": active_category,
        "tags": Tag.objects.annotate(article_count=Count("articles", filter=PUBLISHED)).filter(article_count__gt=0),
        "categories": Category.objects.annotate(article_count=Count("articles", filter=PUBLISHED)).filter(
            article_count__gt=0
        ),
    }
    return render(request, "knowledge/article_list.html", context)


def _published_article(slug):
    return get_object_or_404(Article, slug=slug, status=Article.Status.PUBLISHED)


def article_detail(request, slug, comment_form=None):
    visible_comments = ArticleComment.objects.filter(is_visible=True).select_related("author")
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
            Prefetch("comments", queryset=visible_comments, to_attr="visible_comments"),
        ),
        slug=slug,
        status=Article.Status.PUBLISHED,
    )
    is_favorite = request.user.is_authenticated and article.favorited_by.filter(user=request.user).exists()
    context = {
        "article": article,
        "comment_form": comment_form or CommentForm(),
        "is_favorite": is_favorite,
    }
    return render(request, "knowledge/article_detail.html", context)


@login_required
@require_POST
def add_comment(request, slug):
    article = _published_article(slug)
    form = CommentForm(request.POST)
    if not form.is_valid():
        # Re-render the article so the error is shown next to the field.
        return article_detail(request, slug, comment_form=form)
    comment = form.save(commit=False)
    comment.article = article
    comment.author = request.user
    comment.save()
    messages.success(request, "Комментарий опубликован.")
    return redirect(f"{reverse('knowledge:article-detail', args=[slug])}#comment-{comment.pk}")


@login_required
@require_POST
def delete_comment(request, slug, comment_id):
    comment = get_object_or_404(ArticleComment, pk=comment_id, article__slug=slug, author=request.user)
    comment.delete()
    messages.info(request, "Комментарий удалён.")
    return redirect(f"{reverse('knowledge:article-detail', args=[slug])}#comments")


def source_list(request):
    """Public registry of active sources and the published articles that cite them."""
    published = Article.objects.filter(status=Article.Status.PUBLISHED).only("title", "slug")
    sources = (
        Source.objects.filter(is_active=True)
        .annotate(article_count=Count("articles", filter=PUBLISHED))
        .prefetch_related(Prefetch("articles", queryset=published, to_attr="published_articles"))
        .order_by("publisher", "name")
    )
    page_obj = Paginator(sources, SOURCES_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "knowledge/source_list.html", {"sources": page_obj, "page_obj": page_obj})
