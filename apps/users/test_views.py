import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


pytestmark = pytest.mark.django_db


def test_registration_creates_and_logs_in_user(client):
    response = client.post(
        reverse("users:register"),
        {"username": "student", "password1": "CourseProject!2026", "password2": "CourseProject!2026"},
        follow=True,
    )
    assert response.status_code == 200
    assert get_user_model().objects.filter(username="student").exists()
    assert response.context["user"].is_authenticated


def test_login_and_logout(client):
    get_user_model().objects.create_user(username="reader", password="CourseProject!2026")
    login_response = client.post(
        reverse("users:login"), {"username": "reader", "password": "CourseProject!2026"}, follow=True
    )
    assert login_response.context["user"].is_authenticated
    logout_response = client.post(reverse("users:logout"), follow=True)
    assert not logout_response.context["user"].is_authenticated
