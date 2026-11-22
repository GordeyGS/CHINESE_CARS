import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.cars.models import Model as VehicleModel
from apps.knowledge.models import Article

from .models import FavoriteArticle, FavoriteModel


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


@pytest.fixture
def reader():
    return get_user_model().objects.create_user(username="reader", password="safe-test-password")


def test_guest_is_sent_to_login(client):
    toggle = client.post(reverse("users:favorite-model", args=["byd-seal"]))
    page = client.get(reverse("users:favorites"))
    detail = client.get(reverse("cars:model-detail", args=["byd-seal"])).content.decode()

    assert toggle.status_code == 302 and reverse("users:login") in toggle.url
    assert page.status_code == 302
    assert "Войдите, чтобы сохранить" in detail
    assert not FavoriteModel.objects.exists()


def test_toggle_model_and_article_favorites(client, reader):
    client.force_login(reader)
    model_url = reverse("users:favorite-model", args=["byd-seal"])
    article_url = reverse("users:favorite-article", args=["blade-battery-overview"])

    client.post(model_url, {"next": reverse("cars:model-list")})
    client.post(article_url)
    page = client.get(reverse("users:favorites")).content.decode()
    detail = client.get(reverse("cars:model-detail", args=["byd-seal"])).content.decode()

    assert FavoriteModel.objects.filter(user=reader, vehicle_model__slug="byd-seal").exists()
    assert FavoriteArticle.objects.filter(user=reader, article__slug="blade-battery-overview").exists()
    assert "BYD Seal" in page and "Blade Battery в электромобилях BYD" in page
    assert "★ В избранном" in detail

    client.post(model_url)
    assert not FavoriteModel.objects.exists()


def test_favorites_are_private(client, reader):
    other = get_user_model().objects.create_user(username="other", password="safe-test-password")
    FavoriteModel.objects.create(user=other, vehicle_model=VehicleModel.objects.get(slug="zeekr-001"))
    client.force_login(reader)

    assert "Zeekr 001" not in client.get(reverse("users:favorites")).content.decode()


def test_next_redirect_stays_on_site(client, reader):
    client.force_login(reader)
    url = reverse("users:favorite-model", args=["byd-seal"])

    local = client.post(url, {"next": "/cars/?brand=byd"})
    external = client.post(url, {"next": "https://evil.example/"})

    assert local.url == "/cars/?brand=byd"
    assert external.url == reverse("cars:model-detail", args=["byd-seal"])


def test_toggle_requires_post_and_published_content(client, reader):
    client.force_login(reader)
    Article.objects.filter(slug="blade-battery-overview").update(status=Article.Status.DRAFT)

    assert client.get(reverse("users:favorite-model", args=["byd-seal"])).status_code == 405
    assert client.post(reverse("users:favorite-article", args=["blade-battery-overview"])).status_code == 404


def test_archived_favorite_is_hidden_from_list(client, reader):
    FavoriteArticle.objects.create(user=reader, article=Article.objects.get(slug="blade-battery-overview"))
    Article.objects.filter(slug="blade-battery-overview").update(status=Article.Status.ARCHIVED)
    client.force_login(reader)

    assert "Blade Battery в электромобилях BYD" not in client.get(reverse("users:favorites")).content.decode()
