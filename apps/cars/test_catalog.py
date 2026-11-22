import pytest
from django.core.management import call_command
from django.urls import reverse

from .models import Brand, Market, Model, ModificationMarket, TrimLevel


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    # BYD Seal: BEV RWD, EU 46 990 EUR; Zeekr 001: BEV AWD, EU 67 490 EUR.
    call_command("load_demo_data", verbosity=0)


def model_names(response):
    return {str(vehicle) for vehicle in response.context["cars"]}


def test_filter_by_market(client):
    china = Market.objects.create(name="Китай", code="CN")
    ModificationMarket.objects.create(modification=Model.objects.get(slug="byd-seal").generations.get().modifications.get(), market=china)

    response = client.get(reverse("cars:model-list"), {"market": "CN"})

    assert model_names(response) == {"BYD Seal"}


def test_filter_by_price_range_and_currency(client):
    response = client.get(reverse("cars:model-list"), {"min_price": "50000", "max_price": "70000", "currency": "EUR"})

    assert model_names(response) == {"Zeekr 001"}


def test_price_filter_requires_currency(client):
    response = client.get(reverse("cars:model-list"), {"max_price": "50000"})
    content = response.content.decode()

    assert "Фильтр по цене не применён" in content
    assert model_names(response) == {"BYD Seal", "Zeekr 001"}


def test_unknown_or_inactive_prices_do_not_match(client):
    TrimLevel.objects.filter(modification_market__modification__slug="zeekr-001-awd-100").update(price_amount=None)
    TrimLevel.objects.filter(modification_market__modification__slug="byd-seal-long-range-rwd").update(is_active=False)

    response = client.get(reverse("cars:model-list"), {"min_price": "0", "currency": "EUR"})

    assert model_names(response) == set()


def test_market_and_price_must_belong_to_same_offer(client):
    china = Market.objects.create(name="Китай", code="CN")
    seal = Model.objects.get(slug="byd-seal").generations.get().modifications.get()
    offer = ModificationMarket.objects.create(modification=seal, market=china)
    TrimLevel.objects.create(modification_market=offer, name="CN base", price_amount=179800, currency_code="CNY")

    # The CNY price exists only in China, so "EU + CNY" must not match.
    mismatched = client.get(reverse("cars:model-list"), {"market": "EU", "min_price": "1", "currency": "CNY"})
    matched = client.get(reverse("cars:model-list"), {"market": "CN", "min_price": "1", "currency": "CNY"})

    assert model_names(mismatched) == set()
    assert model_names(matched) == {"BYD Seal"}


def test_powertrain_and_drive_are_checked_on_same_modification(client):
    response = client.get(reverse("cars:model-list"), {"powertrain": "BEV", "drive": "RWD"})

    assert model_names(response) == {"BYD Seal"}


def test_catalog_pagination_keeps_filters(client, monkeypatch):
    monkeypatch.setattr("apps.cars.views.CARS_PER_PAGE", 1)

    first = client.get(reverse("cars:model-list"), {"powertrain": "BEV"})
    second = client.get(reverse("cars:model-list"), {"powertrain": "BEV", "page": 2})

    assert first.context["page_obj"].paginator.num_pages == 2
    assert "?powertrain=BEV&amp;page=2" in first.content.decode()
    assert model_names(first) | model_names(second) == {"BYD Seal", "Zeekr 001"}
    assert model_names(first) != model_names(second)


def test_model_image_and_credit_are_rendered_with_fallback(client):
    seal = Model.objects.get(slug="byd-seal")
    without_image = client.get(reverse("cars:model-list")).content.decode()
    assert "entity-media-placeholder" in without_image

    seal.image_url = "https://example.com/byd-seal.jpg"
    seal.image_credit = "Пресс-служба BYD"
    seal.save(update_fields=["image_url", "image_credit"])
    Brand.objects.filter(slug="byd").update(image_url="https://example.com/byd-logo.png")

    detail = client.get(reverse("cars:model-detail", args=["byd-seal"])).content.decode()
    listing = client.get(reverse("cars:model-list")).content.decode()
    brands = client.get(reverse("cars:brand-list")).content.decode()
    assert 'src="https://example.com/byd-seal.jpg"' in detail
    assert "Фото: Пресс-служба BYD" in detail
    assert 'src="https://example.com/byd-seal.jpg"' in listing
    assert 'alt="Логотип BYD"' in brands
