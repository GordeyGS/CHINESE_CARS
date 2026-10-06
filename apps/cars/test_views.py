import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.cars.models import Modification, ModificationADAS, ModificationMarket, TrimLevel


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


def test_brand_list_and_detail(client):
    listing = client.get(reverse("cars:brand-list"))
    assert listing.status_code == 200
    assert "BYD Company" in listing.content.decode()
    detail = client.get(reverse("cars:brand-detail", args=["byd"]))
    assert detail.status_code == 200
    assert "BYD Seal" in detail.content.decode()


def test_car_catalog_and_filters(client):
    response = client.get(reverse("cars:model-list"), {"brand": "zeekr", "powertrain": "BEV", "drive": "AWD"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Zeekr 001" in content
    assert "BYD Seal" not in content


def test_model_and_modification_details(client):
    model = client.get(reverse("cars:model-detail", args=["byd-seal"]))
    assert model.status_code == 200
    assert "Первое поколение" in model.content.decode()
    assert reverse("cars:modification-detail", args=["byd-seal-long-range-rwd"]) in model.content.decode()
    assert "video-resource-card" in model.content.decode()
    modification = client.get(reverse("cars:modification-detail", args=["byd-seal-long-range-rwd"]))
    content = modification.content.decode()
    assert modification.status_code == 200
    assert "Силовая установка" in content
    assert "Батарея" in content
    assert "Электродвигатели" in content
    assert "Привод" in content
    assert "Трансмиссия" in content
    assert "Рынки и комплектации" in content
    assert "46990" in content and "EUR" in content
    assert "ADAS" in content
    assert "Адаптивный круиз-контроль" in content
    assert "передняя ось" not in content
    assert "задняя ось" in content
    assert content.count(">Blade Battery</a>") == 1


def test_demo_modifications_have_comparison_ready_relations():
    modifications = Modification.objects.filter(
        slug__in=["byd-seal-long-range-rwd", "zeekr-001-awd-100"]
    ).select_related("powertrain__transmission", "powertrain__battery")
    assert modifications.count() == 2
    for modification in modifications:
        assert modification.powertrain.type == "BEV"
        assert modification.powertrain.transmission is not None
        assert modification.powertrain.system_power_kw
        assert modification.powertrain.battery.gross_capacity_kwh
        assert modification.powertrain.motor_links.exists()
        assert modification.market_offers.filter(market__code="EU").exists()
        assert TrimLevel.objects.filter(
            modification_market__modification=modification,
            price_amount__isnull=False,
            currency_code="EUR",
        ).exists()
        assert modification.adas_links.count() >= 2


def test_demo_command_remains_idempotent():
    call_command("load_demo_data", verbosity=0)
    assert Modification.objects.filter(slug="byd-seal-long-range-rwd").count() == 1
    assert Modification.objects.filter(slug="zeekr-001-awd-100").count() == 1
    assert ModificationMarket.objects.filter(modification__slug="byd-seal-long-range-rwd", market__code="EU").count() == 1
    assert ModificationADAS.objects.filter(modification__slug="zeekr-001-awd-100").count() == 2


def test_empty_optional_modification_sections_are_hidden(client):
    modification = Modification.objects.get(slug="byd-seal-long-range-rwd")
    ModificationMarket.objects.filter(modification=modification).delete()
    ModificationADAS.objects.filter(modification=modification).delete()
    modification.powertrain.transmission = None
    modification.powertrain.save(update_fields=["transmission"])

    content = client.get(reverse("cars:modification-detail", args=[modification.slug])).content.decode()
    assert "Трансмиссия" not in content
    assert "Рынки и комплектации" not in content
    assert "<h2 class=\"h4\">ADAS</h2>" not in content


def test_technology_detail(client):
    response = client.get(reverse("cars:technology-detail", args=["blade-battery"]))
    assert response.status_code == 200
    assert "BYD Seal" in response.content.decode()
    assert "video-resource-card" in response.content.decode()
