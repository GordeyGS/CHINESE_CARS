import pytest
from django.core.management import call_command
from django.urls import reverse

from .models import Article, Source, VideoResource


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
    assert "video-resource-card" in content
    assert "video-placeholder" in content
    assert "Демо-провайдер" in content


def test_video_card_uses_thumbnail_when_available(client):
    video = VideoResource.objects.get(url="https://example.com/videos/chinese-ev-demo")
    video.thumbnail_url = "https://example.com/video-thumbnail.jpg"
    video.save(update_fields=["thumbnail_url"])
    content = client.get(reverse("knowledge:article-detail", args=["blade-battery-overview"])).content.decode()
    assert "video-thumbnail" in content
    assert video.thumbnail_url in content
    assert "video-placeholder" not in content


def test_unpublished_article_is_hidden(client):
    article = Article.objects.get(slug="blade-battery-overview")
    article.status = Article.Status.DRAFT
    article.save(update_fields=["status"])
    assert client.get(reverse("knowledge:article-detail", args=[article.slug])).status_code == 404
    assert article.title not in client.get(reverse("knowledge:article-list")).content.decode()


def test_source_list_shows_active_sources_with_published_articles(client):
    hidden = Source.objects.create(name="Скрытый источник", url="https://example.com/hidden", is_active=False)
    article = Article.objects.get(slug="blade-battery-overview")
    source = article.sources.first()

    response = client.get(reverse("knowledge:source-list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert source.name in content
    assert source.url in content
    assert reverse("knowledge:article-detail", args=[article.slug]) in content
    assert hidden.name not in content
    assert 'rel="noopener noreferrer nofollow"' in content


def test_source_list_hides_draft_articles(client):
    article = Article.objects.get(slug="blade-battery-overview")
    article.status = Article.Status.DRAFT
    article.save(update_fields=["status"])

    content = client.get(reverse("knowledge:source-list")).content.decode()

    assert reverse("knowledge:article-detail", args=[article.slug]) not in content


def test_article_list_is_paginated(client, monkeypatch):
    monkeypatch.setattr("apps.knowledge.views.ARTICLES_PER_PAGE", 1)

    response = client.get(reverse("knowledge:article-list"))

    assert response.context["page_obj"].paginator.num_pages == Article.objects.filter(status="published").count()
    assert "?page=2" in response.content.decode()


def test_youtube_video_card_is_click_to_play(client):
    video = VideoResource.objects.get(url="https://example.com/videos/chinese-ev-demo")
    video.url = "https://www.youtube.com/watch?v=N1f76YiT3v4"
    video.save(update_fields=["url"])

    content = client.get(reverse("knowledge:article-detail", args=["blade-battery-overview"])).content.decode()

    assert 'data-video-embed="https://www.youtube-nocookie.com/embed/N1f76YiT3v4?autoplay=1&amp;rel=0"' in content
    assert "https://i.ytimg.com/vi/N1f76YiT3v4/hqdefault.jpg" in content
    assert 'href="https://www.youtube.com/watch?v=N1f76YiT3v4"' in content
    assert "<iframe" not in content
    assert "js/video-embed.js" in content
