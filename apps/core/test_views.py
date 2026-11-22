import pytest
from django.core.management import call_command
from django.urls import reverse


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


def test_homepage_uses_shared_navigation_and_content(client):
    response = client.get(reverse("core:home"))
    content = response.content.decode()
    assert response.status_code == 200
    assert "База знаний по китайскому автопрому" in content
    assert "Марки" in content and "Автомобили" in content and "Статьи" in content
    assert "BYD" in content and "Zeekr" in content


def test_guide_page_explains_terms_and_counts_powertrains(client):
    response = client.get(reverse("core:guide"))
    content = response.content.decode()

    assert response.status_code == 200
    for code in ("ICE", "BEV", "HEV", "PHEV", "EREV"):
        assert code in content
    bev = next(item for item in response.context["powertrain_types"] if item["code"] == "BEV")
    assert bev["count"] == 2
    assert "Нет данных" in content and "Не применяется" in content
    assert reverse("knowledge:source-list") in content
    assert f"{reverse('cars:model-list')}?powertrain=BEV" in content
    assert f"{reverse('cars:model-list')}?powertrain=ICE" not in content


def test_navigation_links_to_guide_and_sources(client):
    content = client.get(reverse("core:home")).content.decode()

    assert reverse("core:guide") in content
    assert reverse("knowledge:source-list") in content
