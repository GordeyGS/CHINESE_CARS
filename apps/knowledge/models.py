from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.cars.models import (
    Brand,
    DriverAssistanceSystem,
    Generation,
    Manufacturer,
    Model as VehicleModel,
    Modification,
    Platform,
    Technology,
)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=140, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Source(TimeStampedModel):
    name = models.CharField(max_length=200)
    publisher = models.CharField(max_length=160, blank=True)
    url = models.URLField(unique=True)
    accessed_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Article(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="articles")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="articles")
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    summary = models.TextField(blank=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True, db_table="article_tag")
    sources = models.ManyToManyField(Source, related_name="articles", blank=True, db_table="article_source")
    manufacturers = models.ManyToManyField(Manufacturer, related_name="articles", blank=True, db_table="article_manufacturer")
    brands = models.ManyToManyField(Brand, related_name="articles", blank=True, db_table="article_brand")
    vehicle_models = models.ManyToManyField(VehicleModel, related_name="articles", blank=True, db_table="article_model")
    generations = models.ManyToManyField(Generation, related_name="articles", blank=True, db_table="article_generation")
    modifications = models.ManyToManyField(Modification, related_name="articles", blank=True, db_table="article_modification")
    platforms = models.ManyToManyField(Platform, related_name="articles", blank=True, db_table="article_platform")
    technologies = models.ManyToManyField(Technology, related_name="articles", blank=True, db_table="article_technology")
    adas_systems = models.ManyToManyField(DriverAssistanceSystem, related_name="articles", blank=True, db_table="article_adas")
    related_articles = models.ManyToManyField(
        "self", through="RelatedArticle", through_fields=("from_article", "to_article"), symmetrical=False, blank=True
    )

    class Meta:
        ordering = ["-published_at", "title"]
        indexes = [models.Index(fields=["status", "published_at"], name="idx_article_status_date")]

    def clean(self):
        super().clean()
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            raise ValidationError({"published_at": "Published articles require a publication date."})

    def __str__(self):
        return self.title


class RelatedArticle(TimeStampedModel):
    from_article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="outgoing_article_links")
    to_article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="incoming_article_links")
    relation_type = models.CharField(max_length=80, blank=True)

    class Meta:
        db_table = "related_article"
        constraints = [
            models.UniqueConstraint(fields=["from_article", "to_article"], name="uq_related_article_pair"),
            models.CheckConstraint(
                condition=~models.Q(from_article=models.F("to_article")), name="ck_related_article_not_self"
            ),
        ]


class VideoResource(TimeStampedModel):
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    url = models.URLField(unique=True)
    provider = models.CharField(max_length=100)
    thumbnail_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    articles = models.ManyToManyField(Article, related_name="video_resources", blank=True, db_table="video_article")
    vehicle_models = models.ManyToManyField(VehicleModel, related_name="video_resources", blank=True, db_table="video_model")
    technologies = models.ManyToManyField(Technology, related_name="video_resources", blank=True, db_table="video_technology")

    class Meta:
        ordering = ["-published_at", "title"]

    def __str__(self):
        return self.title
