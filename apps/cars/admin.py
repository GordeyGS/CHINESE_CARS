from django.contrib import admin

from . import models


@admin.register(models.Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "founded_year", "is_active")
    search_fields = ("name", "description")
    list_filter = ("country", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "manufacturer", "origin_country", "is_active")
    search_fields = ("name", "manufacturer__name")
    list_filter = ("manufacturer", "origin_country", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.Model)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "segment", "production_status", "is_active")
    search_fields = ("name", "brand__name", "description")
    list_filter = ("brand", "production_status", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.Generation)
class GenerationAdmin(admin.ModelAdmin):
    list_display = ("name", "model", "platform", "body_type", "start_year", "end_year", "is_active")
    search_fields = ("name", "code", "model__name", "model__brand__name")
    list_filter = ("body_type", "start_year", "is_active")


@admin.register(models.Modification)
class ModificationAdmin(admin.ModelAdmin):
    list_display = ("name", "generation", "powertrain", "range_km", "is_active")
    search_fields = ("name", "generation__model__name", "generation__model__brand__name")
    list_filter = ("powertrain__type", "powertrain__drive_type", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    search_fields = ("name", "description")
    list_filter = ("category", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.Powertrain)
class PowertrainAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "drive_type", "system_power_kw", "battery", "combustion_engine")
    list_filter = ("type", "drive_type")


admin.site.register([
    models.Country, models.Platform, models.BodyType, models.CombustionEngine,
    models.ElectricMotor, models.Battery, models.Transmission, models.DriveType,
    models.PowertrainMotor, models.Market, models.ModificationMarket,
    models.TrimLevel, models.ModelTechnology, models.GenerationTechnology,
    models.DriverAssistanceSystem, models.ModificationADAS,
])
