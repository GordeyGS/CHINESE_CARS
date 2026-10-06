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
