from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import FavoriteArticle, FavoriteModel, User


admin.site.register(User, UserAdmin)


@admin.register(FavoriteArticle)
class FavoriteArticleAdmin(admin.ModelAdmin):
    list_display = ("user", "article", "created_at")
    search_fields = ("user__username", "article__title")


@admin.register(FavoriteModel)
class FavoriteModelAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle_model", "created_at")
    search_fields = ("user__username", "vehicle_model__name", "vehicle_model__brand__name")
