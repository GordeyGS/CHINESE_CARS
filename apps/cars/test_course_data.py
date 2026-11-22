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
    assert first["brands"] == 15
    assert first["models"] == 37
    assert first["modifications"] == 59
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


def test_course_data_uses_concrete_official_videos():
    call_command("load_course_data", verbosity=0)
    call_command("load_course_data", verbosity=0)

    active = VideoResource.objects.filter(is_active=True)
    assert active.count() == 8
    assert all(video.youtube_id and video.thumbnail_url for video in active)
    assert not active.filter(url__contains="/@").exists()
    assert VideoResource.objects.get(url="https://www.youtube.com/watch?v=N1f76YiT3v4").vehicle_models.filter(
        slug="xiaomi-su7"
    ).exists()
    assert not VideoResource.objects.filter(url="https://www.youtube.com/@cheryinternational", is_active=True).exists()


def test_course_data_groups_brands_by_manufacturer_and_shares_platforms():
    call_command("load_course_data", verbosity=0)
    sea_slug = Model.objects.get(slug="zeekr-001").generations.get().platform.slug
    call_command("load_course_data", verbosity=0)

    great_wall = Brand.objects.filter(manufacturer__name="Great Wall Motor").values_list("name", flat=True)
    assert set(great_wall) == {"Haval", "Tank"}
    # SEA is one platform record for Zeekr and Lynk & Co, and its slug does not change on reload.
    sea_models = Model.objects.filter(generations__platform__name="SEA").values_list("brand__name", flat=True)
    assert {"Zeekr", "Lynk & Co"} <= set(sea_models)
    assert Model.objects.get(slug="lynk-co-02").generations.get().platform.slug == sea_slug


def test_course_data_fills_confirmed_acceleration_for_fact_questions():
    call_command("load_course_data", verbosity=0)

    fastest = Modification.objects.exclude(acceleration_0_100_s=None).order_by("acceleration_0_100_s").first()
    assert fastest.slug == "xiaomi-su7-max-awd"
    assert Modification.objects.exclude(acceleration_0_100_s=None).count() >= 10
