from decimal import Decimal

import pytest
from django.core.management import call_command

from .models import Modification
from .units import format_power, kw_to_hp


@pytest.mark.parametrize(("kw", "hp"), [
    (Decimal("220"), 299),   # Xiaomi SU7 RWD: 299 л.с. по данным производителя
    (Decimal("230"), 313),
    (Decimal("400"), 544),
    (100, 136),
    (Decimal("0.37"), 1),    # 0.503 -> rounded half up
])
def test_kw_is_converted_to_metric_horsepower(kw, hp):
    assert kw_to_hp(kw) == hp


def test_unknown_power_stays_empty():
    assert kw_to_hp(None) is None
    assert format_power(None) == ""


def test_power_is_formatted_in_kw_and_hp():
    assert format_power(Decimal("230.00")) == "230 кВт (313 л.с.)"
    assert format_power(Decimal("160.50")) == "160,50 кВт (218 л.с.)"  # same rule as |floatformat:"-2" elsewhere


@pytest.mark.django_db
def test_modification_page_shows_horsepower_and_model_photo(client):
    call_command("load_demo_data", verbosity=0)
    modification = Modification.objects.select_related("generation__model").get(generation__model__slug="byd-seal")
    model = modification.generation.model
    model.image_url = "https://upload.wikimedia.org/seal.jpg"
    model.image_credit = "Author, CC BY-SA 4.0, Wikimedia Commons (seal.jpg)"
    model.save()

    content = client.get(f"/cars/modifications/{modification.slug}/").content.decode()

    assert "230 кВт (313 л.с.)" in content
    assert 'src="https://upload.wikimedia.org/seal.jpg"' in content
    assert "Фото: Author, CC BY-SA 4.0" in content


@pytest.mark.django_db
def test_modification_page_without_photo_has_no_empty_figure(client):
    call_command("load_demo_data", verbosity=0)
    modification = Modification.objects.get(generation__model__slug="byd-seal")
    modification.generation.model.__class__.objects.filter(slug="byd-seal").update(image_url="")

    content = client.get(f"/cars/modifications/{modification.slug}/").content.decode()

    assert "entity-hero-image" not in content
