import pytest
from django.core.management import call_command
from django.urls import reverse


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
    assert "First generation" in model.content.decode()
    assert reverse("cars:modification-detail", args=["byd-seal-long-range-rwd"]) in model.content.decode()
    modification = client.get(reverse("cars:modification-detail", args=["byd-seal-long-range-rwd"]))
    content = modification.content.decode()
    assert modification.status_code == 200
    assert "Силовая установка" in content
    assert "Батарея" in content
    assert "Электродвигатели" in content
    assert "Привод" in content


def test_technology_detail(client):
    response = client.get(reverse("cars:technology-detail", args=["blade-battery"]))
    assert response.status_code == 200
    assert "BYD Seal" in response.content.decode()
