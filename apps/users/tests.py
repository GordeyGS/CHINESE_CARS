import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse


@pytest.mark.django_db
def test_custom_user_model():
    user = get_user_model().objects.create_user(username="student", password="safe-test-password")
    assert user.check_password("safe-test-password")
    assert user._meta.label == "users.User"


@pytest.mark.django_db
def test_setup_roles_creates_groups_and_is_idempotent():
    call_command("setup_roles", verbosity=0)
    first = {group.name: group.permissions.count() for group in Group.objects.all()}
    call_command("setup_roles", verbosity=0)
    second = {group.name: group.permissions.count() for group in Group.objects.all()}

    assert set(first) == {"Editor", "Administrator"}
    assert first == second


@pytest.mark.django_db
def test_editor_and_administrator_permissions():
    call_command("setup_roles", verbosity=0)
    User = get_user_model()
    editor = User.objects.create_user(username="editor", password="safe-test-password", is_staff=True)
    editor.groups.add(_group("Editor"))
    admin = User.objects.create_user(username="chief", password="safe-test-password", is_staff=True)
    admin.groups.add(_group("Administrator"))

    assert editor.has_perm("knowledge.change_article")
    assert editor.has_perm("knowledge.add_videoresource")
    assert editor.has_perm("cars.change_modification")
    assert editor.has_perm("recommendations.change_recommendationrule")
    assert not editor.has_perm("cars.delete_brand")
    assert not editor.has_perm("knowledge.delete_article")
    assert not editor.has_perm("users.change_user")
    assert admin.has_perm("cars.delete_brand")
    assert admin.has_perm("users.change_user")
    assert admin.has_perm("auth.change_group")


@pytest.mark.django_db
def test_admin_access_is_checked_on_server(client):
    call_command("setup_roles", verbosity=0)
    editor = get_user_model().objects.create_user(username="editor", password="safe-test-password", is_staff=True)
    editor.groups.add(_group("Editor"))
    client.force_login(editor)

    assert client.get(reverse("admin:knowledge_article_add")).status_code == 200
    assert client.get(reverse("admin:users_user_changelist")).status_code == 403
    client.logout()
    assert client.get(reverse("admin:knowledge_article_add")).status_code == 302


def _group(name):
    return Group.objects.get(name=name)
