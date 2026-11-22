from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Project user model reserved for future profile fields."""

    pass


class FavoriteArticle(models.Model):
    """Personal bookmark: a user saved an article."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_articles")
    article = models.ForeignKey("knowledge.Article", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorite_article"
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "article"], name="uq_favorite_article")]

    def __str__(self):
        return f"{self.user} ★ {self.article}"


class FavoriteModel(models.Model):
    """Personal bookmark: a user saved a vehicle model."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_models")
    vehicle_model = models.ForeignKey("cars.Model", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorite_model"
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "vehicle_model"], name="uq_favorite_model")]

    def __str__(self):
        return f"{self.user} ★ {self.vehicle_model}"
