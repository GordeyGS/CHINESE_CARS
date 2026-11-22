from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.cars.models import Model as VehicleModel
from apps.knowledge.models import Article

from .forms import RegistrationForm
from .models import FavoriteArticle, FavoriteModel


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Регистрация завершена. Добро пожаловать!")
        return redirect("core:home")
    return render(request, "users/register.html", {"form": form})


def _back(request, fallback):
    """Return to the page that sent the form, but never to another site."""
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def _toggle(request, favorite_model, **lookup):
    favorite, created = favorite_model.objects.get_or_create(user=request.user, **lookup)
    if not created:
        favorite.delete()
    messages.success(request, "Добавлено в избранное." if created else "Удалено из избранного.")


@login_required
@require_POST
def toggle_favorite_article(request, slug):
    article = get_object_or_404(Article, slug=slug, status=Article.Status.PUBLISHED)
    _toggle(request, FavoriteArticle, article=article)
    return _back(request, reverse("knowledge:article-detail", args=[slug]))


@login_required
@require_POST
def toggle_favorite_model(request, slug):
    vehicle = get_object_or_404(VehicleModel, slug=slug, is_active=True)
    _toggle(request, FavoriteModel, vehicle_model=vehicle)
    return _back(request, reverse("cars:model-detail", args=[slug]))


@login_required
def favorites(request):
    """Personal page; unpublished or archived items are kept but not shown."""
    articles = (
        FavoriteArticle.objects.filter(user=request.user, article__status=Article.Status.PUBLISHED)
        .select_related("article__category")
    )
    vehicles = (
        FavoriteModel.objects.filter(user=request.user, vehicle_model__is_active=True)
        .select_related("vehicle_model__brand")
    )
    return render(request, "users/favorites.html", {"favorite_articles": articles, "favorite_models": vehicles})
