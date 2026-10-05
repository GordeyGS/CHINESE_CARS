from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


FTS_INDEXES = {
    "idx_article_search_fts": (
        "knowledge_article",
        "setweight(to_tsvector('russian'::regconfig, coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(summary, '')), 'B') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(body, '')), 'C')",
        "status = 'published'",
    ),
    "idx_video_search_fts": (
        "knowledge_videoresource",
        "setweight(to_tsvector('russian'::regconfig, coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'B') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(provider, '')), 'D')",
        "is_active",
    ),
    "idx_manufacturer_search_fts": (
        "cars_manufacturer",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_brand_search_fts": (
        "cars_brand",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_model_search_fts": (
        "cars_model",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_generation_search_fts": (
        "cars_generation",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(code, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_modification_search_fts": (
        "cars_modification",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(source_note, '')), 'C')",
        "is_active",
    ),
    "idx_technology_search_fts": (
        "cars_technology",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(category, '')), 'B') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_platform_search_fts": (
        "cars_platform",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
    "idx_adas_search_fts": (
        "cars_driverassistancesystem",
        "setweight(to_tsvector('russian'::regconfig, coalesce(name, '')), 'A') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(category, '')), 'B') || "
        "setweight(to_tsvector('russian'::regconfig, coalesce(description, '')), 'C')",
        "is_active",
    ),
}

TRIGRAM_INDEXES = {
    "idx_article_title_trgm": ("knowledge_article", "title", "status = 'published'"),
    "idx_video_title_trgm": ("knowledge_videoresource", "title", "is_active"),
    "idx_manufacturer_name_trgm": ("cars_manufacturer", "name", "is_active"),
    "idx_brand_name_trgm": ("cars_brand", "name", "is_active"),
    "idx_model_name_trgm": ("cars_model", "name", "is_active"),
    "idx_generation_name_trgm": ("cars_generation", "name", "is_active"),
    "idx_modification_name_trgm": ("cars_modification", "name", "is_active"),
    "idx_technology_name_trgm": ("cars_technology", "name", "is_active"),
    "idx_platform_name_trgm": ("cars_platform", "name", "is_active"),
    "idx_adas_name_trgm": ("cars_driverassistancesystem", "name", "is_active"),
}


def create_indexes(apps, schema_editor):
    for name, (table, expression, condition) in FTS_INDEXES.items():
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING GIN (({expression})) WHERE {condition}"
        )
    for name, (table, column, condition) in TRIGRAM_INDEXES.items():
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING GIN ({column} gin_trgm_ops) WHERE {condition}"
        )


def drop_indexes(apps, schema_editor):
    for name in (*TRIGRAM_INDEXES, *FTS_INDEXES):
        schema_editor.execute(f"DROP INDEX IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("cars", "0002_battery_ck_battery_gross_nonnegative_and_more"),
        ("knowledge", "0002_initial"),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunPython(create_indexes, drop_indexes),
    ]
