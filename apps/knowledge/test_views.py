import pytest
from django.core.management import call_command
from django.urls import reverse

from .models import Article


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


def test_article_list_and_detail(client):
    listing = client.get(reverse("knowledge:article-list"))
    assert listing.status_code == 200
    assert "Blade Battery в электромобилях BYD" in listing.content.decode()
    detail = client.get(reverse("knowledge:article-detail", args=["blade-battery-overview"]))
    content = detail.content.decode()
    assert detail.status_code == 200
    assert "Источники" in content
    assert reverse("cars:model-detail", args=["byd-seal"]) in content


def test_unpublished_article_is_hidden(client):
    article = Article.objects.get(slug="blade-battery-overview")
    article.status = Article.Status.DRAFT
    article.save(update_fields=["status"])
    assert client.get(reverse("knowledge:article-detail", args=[article.slug])).status_code == 404
    assert article.title not in client.get(reverse("knowledge:article-list")).content.decode()
