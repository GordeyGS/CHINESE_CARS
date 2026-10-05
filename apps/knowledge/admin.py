from django.contrib import admin

from .models import Article, Category, RelatedArticle, Source, Tag, VideoResource


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "status", "published_at", "updated_at")
    search_fields = ("title", "summary", "body")
    list_filter = ("status", "category", "tags")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags", "sources", "manufacturers", "brands", "vehicle_models", "generations", "modifications", "platforms", "technologies", "adas_systems")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "publisher", "accessed_at", "is_active")
    search_fields = ("name", "publisher", "url")
    list_filter = ("is_active", "publisher")


@admin.register(VideoResource)
class VideoResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "published_at", "is_active")
    search_fields = ("title", "description", "provider")
    list_filter = ("provider", "is_active")
    filter_horizontal = ("articles", "vehicle_models", "technologies")


admin.site.register(RelatedArticle)
