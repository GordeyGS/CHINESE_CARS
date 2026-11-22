import pytest
from django.core.management import call_command
from django.urls import reverse

from .models import Modification, ModificationADAS
from .services.comparison import NOT_APPLICABLE, NOT_AVAILABLE, build_comparison, comparison_queryset


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


@pytest.fixture
def pair():
    queryset = comparison_queryset()
    return queryset.get(slug="byd-seal-long-range-rwd"), queryset.get(slug="zeekr-001-awd-100")


def rows_by_label(sections):
    return {row["label"]: row for section in sections for row in section["rows"]}


def test_comparison_rows_have_same_parameters_and_mark_differences(pair):
    rows = rows_by_label(build_comparison(*pair))

    assert rows["Марка"]["left"].text == "BYD"
    assert rows["Марка"]["right"].text == "Zeekr"
    assert rows["Марка"]["different"] is True
    assert rows["Тип"]["different"] is False
    assert rows["Суммарная мощность"]["left"].text == "230 кВт (313 л.с.)"
    assert rows["Суммарная мощность"]["right"].text == "400 кВт (544 л.с.)"


def test_not_applicable_is_distinguished_from_missing(pair):
    left, right = pair
    rows = rows_by_label(build_comparison(left, right))
    assert rows["Двигатель внутреннего сгорания"]["left"] == NOT_APPLICABLE
    assert rows["Расход топлива"]["left"] == NOT_APPLICABLE

    ModificationADAS.objects.filter(modification=left).delete()
    left = comparison_queryset().get(pk=left.pk)
    rows = rows_by_label(build_comparison(left, right))
    assert rows["ADAS"]["left"] == NOT_AVAILABLE
    assert rows["ADAS"]["right"] != NOT_AVAILABLE


def test_compare_page_renders_selected_pair(client, pair):
    left, right = pair
    response = client.get(reverse("cars:compare"), {"left": left.pk, "right": right.pk})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Увеличенный запас хода RWD" in content
    assert "100 кВт·ч AWD" in content
    assert "Не применяется" in content
    assert "46990" in content and "67490" in content


def test_compare_rejects_same_modification(client, pair):
    left, _ = pair
    response = client.get(reverse("cars:compare"), {"left": left.pk, "right": left.pk})

    assert response.status_code == 200
    assert "Выберите две разные модификации." in response.content.decode()
    assert response.context["form"].errors


def test_compare_rejects_inactive_or_unknown_modification(client, pair):
    left, right = pair
    Modification.objects.filter(pk=right.pk).update(is_active=False)

    inactive = client.get(reverse("cars:compare"), {"left": left.pk, "right": right.pk})
    unknown = client.get(reverse("cars:compare"), {"left": left.pk, "right": 999999})

    assert "right" in inactive.context["form"].errors
    assert "right" in unknown.context["form"].errors
    assert "sections" not in inactive.context


def test_compare_with_single_car_preselects_it_without_errors(client, pair):
    left, _right = pair
    response = client.get(reverse("cars:compare"), {"left": left.pk})

    assert response.status_code == 200
    assert response.context["form"].initial["left"] == str(left.pk)
    assert not response.context["form"].errors
    assert "Обязательное поле" not in response.content.decode()


def test_compare_options_are_short_and_grouped_by_brand(client, pair):
    left, _right = pair
    content = client.get(reverse("cars:compare")).content.decode()
    model = left.generation.model

    assert f'<optgroup label="{model.brand.name}">' in content
    assert f"{model.name} · {left.name}" in content
    assert " / " not in content.split("<form", 1)[1].split("</form>", 1)[0]
