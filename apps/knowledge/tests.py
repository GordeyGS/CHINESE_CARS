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
