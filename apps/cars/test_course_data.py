import pytest
from django.core.management import call_command

from apps.knowledge.models import Article, Source, VideoResource

from .models import Brand, Model, Modification, Powertrain


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
