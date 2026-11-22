"""Role definitions for the knowledge base (FR-34, FR-36).

Roles are ordinary Django groups with model permissions, so access is checked by
Django Admin on the server. Editors do not delete reference data: entities are
archived through ``is_active`` or the article status instead (NFR-11). Only
link rows without their own meaning may be deleted by an editor.
"""

from django.contrib.auth.models import Group, Permission
from django.db import transaction

EDITOR = "Editor"
ADMINISTRATOR = "Administrator"

CONTENT_APPS = ("cars", "knowledge", "recommendations")
EDITOR_ACTIONS = ("view", "add", "change")
EDITOR_DELETABLE_MODELS = (
    ("knowledge", "relatedarticle"),
    ("knowledge", "articlecomment"),
    ("recommendations", "recommendationcondition"),
)
ADMINISTRATOR_EXTRA = (
    ("users", "user", ("view", "add", "change", "delete")),
    ("auth", "group", ("view", "add", "change", "delete")),
    ("auth", "permission", ("view",)),
)


def editor_permissions():
    content = Permission.objects.filter(content_type__app_label__in=CONTENT_APPS)
    allowed = content.filter(codename__regex=rf"^({'|'.join(EDITOR_ACTIONS)})_")
    deletable = Permission.objects.none()
    for app_label, model in EDITOR_DELETABLE_MODELS:
        deletable |= Permission.objects.filter(
            content_type__app_label=app_label, codename=f"delete_{model}"
        )
    return allowed | deletable


def administrator_permissions():
    permissions = Permission.objects.filter(content_type__app_label__in=CONTENT_APPS)
    for app_label, model, actions in ADMINISTRATOR_EXTRA:
        permissions |= Permission.objects.filter(
            content_type__app_label=app_label,
            content_type__model=model,
            codename__in=[f"{action}_{model}" for action in actions],
        )
    return permissions


@transaction.atomic
def setup_roles():
    """Create or update both groups; safe to run repeatedly."""
    result = {}
    for name, permissions in ((EDITOR, editor_permissions()), (ADMINISTRATOR, administrator_permissions())):
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.set(permissions.distinct())
        result[name] = group.permissions.count()
    return result
