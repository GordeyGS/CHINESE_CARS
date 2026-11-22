import pytest
from django.core.exceptions import ValidationError

from apps.cars.models import Brand, Country, Manufacturer, Model, Technology
from apps.users.models import User

from .models import Article, Category, Source, Tag, VideoResource


@pytest.mark.django_db
def test_article_category_tag_source_and_video_links():
    user = User.objects.create_user(username="editor", password="test-password")
    category = Category.objects.create(name="Technology", slug="technology")
    tag = Tag.objects.create(name="EV", slug="ev")
    source = Source.objects.create(name="Official source", url="https://example.com/source")
    article = Article.objects.create(
        category=category, author=user, title="Blade Battery", slug="blade", body="Knowledge text."
    )
    article.tags.add(tag)
    article.sources.add(source)
    video = VideoResource.objects.create(
        title="Blade Battery video", url="https://example.com/video", provider="Demo"
    )
    video.articles.add(article)
    assert article.category == category
    assert list(article.tags.all()) == [tag]
    assert list(article.sources.all()) == [source]
    assert list(video.articles.all()) == [article]


@pytest.mark.django_db
def test_video_model_and_technology_links():
    country = Country.objects.create(name="China", iso_code="CN")
    manufacturer = Manufacturer.objects.create(name="BYD Company", slug="byd-company", country=country)
    brand = Brand.objects.create(manufacturer=manufacturer, origin_country=country, name="BYD", slug="byd")
    vehicle_model = Model.objects.create(brand=brand, name="Seal", slug="byd-seal")
    technology = Technology.objects.create(name="Blade Battery", slug="blade-battery")
    video = VideoResource.objects.create(title="Seal", url="https://example.com/seal", provider="Demo")
    video.vehicle_models.add(vehicle_model)
    video.technologies.add(technology)
    assert video.vehicle_models.get() == vehicle_model
    assert video.technologies.get() == technology


@pytest.mark.django_db
def test_published_article_requires_date():
    user = User.objects.create_user(username="publisher")
    category = Category.objects.create(name="History", slug="history")
    article = Article(
        category=category, author=user, title="Published", slug="published", body="Text", status=Article.Status.PUBLISHED
    )
    with pytest.raises(ValidationError):
        article.full_clean()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=N1f76YiT3v4", "N1f76YiT3v4"),
        ("https://www.youtube.com/watch?feature=share&v=jUs6cQkl4Ug", "jUs6cQkl4Ug"),
        ("https://youtu.be/vTSGPLqvcvc", "vTSGPLqvcvc"),
        ("https://www.youtube.com/shorts/OJJYhO0_4PI", "OJJYhO0_4PI"),
        ("https://www.youtube.com/embed/xg2x21o5u0A", "xg2x21o5u0A"),
        ("https://www.youtube.com/@xiaomi", None),
        ("https://www.nio.com/videos", None),
        ("https://evil.example/watch?v=N1f76YiT3v4", None),
    ],
)
def test_video_youtube_id_is_parsed_only_from_youtube_links(url, expected):
    video = VideoResource(title="t", url=url, provider="p")

    assert video.youtube_id == expected
    if expected:
        assert video.embed_url.startswith(f"https://www.youtube-nocookie.com/embed/{expected}")
        assert video.preview_url == f"https://i.ytimg.com/vi/{expected}/hqdefault.jpg"
    else:
        assert video.embed_url == "" and video.preview_url == ""
