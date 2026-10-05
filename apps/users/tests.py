import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_custom_user_model():
    user = get_user_model().objects.create_user(username="student", password="safe-test-password")
    assert user.check_password("safe-test-password")
    assert user._meta.label == "users.User"
