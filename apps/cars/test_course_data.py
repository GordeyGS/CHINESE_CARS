import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.knowledge.models import Article, Source, VideoResource

from .models import Brand, Model, Modification, Powertrain, validate_image_reference


pytestmark = pytest.mark.django_db


def snapshot():
    return {
        "brands": Brand.objects.count(),
        "models": Model.objects.count(),
        "modifications": Modification.objects.count(),
        "articles": Article.objects.count(),
        "sources": Source.objects.count(),
        "videos": VideoResource.objects.count(),
    }


def test_course_data_has_defence_scope_and_is_idempotent():
    call_command("load_course_data", verbosity=0)
    first = snapshot()
    call_command("load_course_data", verbosity=0)

    assert first == snapshot()
    assert first["brands"] == 8
    assert first["models"] == 16
    assert first["modifications"] == 32
    types = set(Modification.objects.values_list("powertrain__type", flat=True))
    assert {Powertrain.Type.ICE, Powertrain.Type.BEV, Powertrain.Type.PHEV, Powertrain.Type.EREV} <= types


def test_course_data_keeps_byd_zeekr_scenario():
    call_command("load_course_data", verbosity=0)

    assert Modification.objects.filter(slug="byd-seal-long-range-rwd", is_active=True).exists()
    assert Modification.objects.filter(slug="zeekr-001-awd-100", is_active=True).exists()
    assert Article.objects.filter(slug="blade-battery-overview", status=Article.Status.PUBLISHED).exists()


def test_course_data_adds_attributed_commons_images():
    call_command("load_course_data", verbosity=0)

    for model in Model.objects.all():
        assert model.image_url.startswith("https://upload.wikimedia.org/wikipedia/commons/"), model
        assert "Wikimedia Commons" in model.image_credit
        assert "CC" in model.image_credit
    assert not Brand.objects.filter(image_url="").exists()
    hongqi = Brand.objects.get(slug="hongqi")
    assert hongqi.image_url == "/static/img/brands/hongqi.png"
    assert (settings.BASE_DIR / "static/img/brands/hongqi.png").exists()


@pytest.mark.parametrize("value", ["https://example.com/logo.png", "/static/img/brands/hongqi.png"])
def test_image_reference_accepts_external_url_and_project_static_file(value):
    validate_image_reference(value)


@pytest.mark.parametrize(
    "value", ["javascript:alert(1)", "ftp://example.com/a.png", "/media/logo.png", "/static/img/../../settings.py"]
)
def test_image_reference_rejects_unsafe_values(value):
    with pytest.raises(ValidationError):
        validate_image_reference(value)
