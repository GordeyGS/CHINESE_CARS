from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SourcedModel(TimeStampedModel):
    source_url = models.URLField(blank=True)
    source_note = models.TextField(blank=True)

    class Meta:
        abstract = True


class Country(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    iso_code = models.CharField(max_length=2, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name


class Manufacturer(SourcedModel):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="manufacturers")
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(SourcedModel):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="brands")
    origin_country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="brands")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    discontinued_year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, help_text="Ссылка на логотип марки у внешнего источника; файл не хранится в БД.")
    image_credit = models.CharField(max_length=200, blank=True, help_text="Автор или источник изображения и лицензия.")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["manufacturer", "name"], name="uq_brand_manufacturer_name"),
            models.CheckConstraint(
                condition=models.Q(discontinued_year__isnull=True)
                | models.Q(founded_year__isnull=True)
                | models.Q(discontinued_year__gte=models.F("founded_year")),
                name="ck_brand_year_order",
            ),
        ]

    def __str__(self):
        return self.name


class Technology(SourcedModel):
    name = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "technologies"

    def __str__(self):
        return self.name


class Platform(SourcedModel):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="platforms")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["manufacturer", "name"], name="uq_platform_mfr_name")]

    def __str__(self):
        return self.name


class BodyType(TimeStampedModel):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Model(SourcedModel):
    class ProductionStatus(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        IN_PRODUCTION = "production", "In production"
        DISCONTINUED = "discontinued", "Discontinued"

    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=200, unique=True)
    segment = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    production_status = models.CharField(
        max_length=20, choices=ProductionStatus.choices, default=ProductionStatus.IN_PRODUCTION, db_index=True
    )
    image_url = models.URLField(blank=True, help_text="Ссылка на изображение модели у внешнего источника; файл не хранится в БД.")
    image_credit = models.CharField(max_length=200, blank=True, help_text="Автор или источник изображения и лицензия.")
    is_active = models.BooleanField(default=True, db_index=True)
    technologies = models.ManyToManyField(Technology, through="ModelTechnology", related_name="models", blank=True)

    class Meta:
        ordering = ["brand__name", "name"]
        constraints = [models.UniqueConstraint(fields=["brand", "name"], name="uq_model_brand_name")]
        indexes = [models.Index(fields=["brand", "production_status"], name="idx_model_brand_status")]

    def __str__(self):
        return f"{self.brand.name} {self.name}"

    def get_production_status_display(self):
        labels = {
            self.ProductionStatus.UPCOMING: "Ожидается",
            self.ProductionStatus.IN_PRODUCTION: "В производстве",
            self.ProductionStatus.DISCONTINUED: "Производство завершено",
        }
        return labels.get(self.production_status, self.production_status)


class Generation(SourcedModel):
    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name="generations")
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="generations")
    body_type = models.ForeignKey(BodyType, on_delete=models.PROTECT, related_name="generations")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=80, blank=True)
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    technologies = models.ManyToManyField(Technology, through="GenerationTechnology", related_name="generations", blank=True)

    class Meta:
        ordering = ["model", "-start_year"]
        constraints = [
            models.UniqueConstraint(fields=["model", "name"], name="uq_generation_model_name"),
            models.CheckConstraint(
                condition=models.Q(end_year__isnull=True) | models.Q(end_year__gte=models.F("start_year")),
                name="ck_generation_year_order",
            ),
        ]

    def __str__(self):
        return f"{self.model} — {self.name}"


class CombustionEngine(SourcedModel):
    class FuelType(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        OTHER = "other", "Other"

    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="combustion_engines")
    code = models.CharField(max_length=100)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices)
    displacement_cc = models.PositiveIntegerField(null=True, blank=True)
    cylinders = models.PositiveSmallIntegerField(null=True, blank=True)
    induction = models.CharField(max_length=80, blank=True)
    power_kw = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    torque_nm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["manufacturer", "code"], name="uq_engine_mfr_code"),
            models.CheckConstraint(condition=models.Q(power_kw__isnull=True) | models.Q(power_kw__gte=0), name="ck_engine_power_nonnegative"),
            models.CheckConstraint(condition=models.Q(torque_nm__isnull=True) | models.Q(torque_nm__gte=0), name="ck_engine_torque_nonnegative"),
        ]

    def __str__(self):
        return self.code


class ElectricMotor(SourcedModel):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="electric_motors")
    code = models.CharField(max_length=100)
    motor_type = models.CharField(max_length=100, blank=True)
    power_kw = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    torque_nm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["manufacturer", "code"], name="uq_motor_mfr_code"),
            models.CheckConstraint(condition=models.Q(power_kw__isnull=True) | models.Q(power_kw__gte=0), name="ck_motor_power_nonnegative"),
            models.CheckConstraint(condition=models.Q(torque_nm__isnull=True) | models.Q(torque_nm__gte=0), name="ck_motor_torque_nonnegative"),
        ]

    def __str__(self):
        return self.code


class Battery(SourcedModel):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="batteries")
    technology = models.ForeignKey(Technology, on_delete=models.PROTECT, related_name="batteries", null=True, blank=True)
    name = models.CharField(max_length=160)
    chemistry = models.CharField(max_length=80, blank=True)
    gross_capacity_kwh = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    usable_capacity_kwh = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    voltage_v = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["manufacturer", "name"], name="uq_battery_mfr_name"),
            models.CheckConstraint(
                condition=models.Q(gross_capacity_kwh__isnull=True)
                | models.Q(usable_capacity_kwh__isnull=True)
                | models.Q(usable_capacity_kwh__lte=models.F("gross_capacity_kwh")),
                name="ck_battery_usable_lte_gross",
            ),
            models.CheckConstraint(condition=models.Q(gross_capacity_kwh__isnull=True) | models.Q(gross_capacity_kwh__gte=0), name="ck_battery_gross_nonnegative"),
            models.CheckConstraint(condition=models.Q(usable_capacity_kwh__isnull=True) | models.Q(usable_capacity_kwh__gte=0), name="ck_battery_usable_nonnegative"),
        ]

    def __str__(self):
        return self.name


class Transmission(SourcedModel):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="transmissions")
    name = models.CharField(max_length=160)
    transmission_type = models.CharField(max_length=80)
    gears = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["manufacturer", "name"], name="uq_transmission_mfr_name")]

    def __str__(self):
        return self.name


class DriveType(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Powertrain(SourcedModel):
    class Type(models.TextChoices):
        ICE = "ICE", "ICE"
        BEV = "BEV", "BEV"
        HEV = "HEV", "HEV"
        PHEV = "PHEV", "PHEV"
        EREV = "EREV", "EREV"

    type = models.CharField(max_length=5, choices=Type.choices, db_index=True)
    combustion_engine = models.ForeignKey(CombustionEngine, on_delete=models.PROTECT, related_name="powertrains", null=True, blank=True)
    battery = models.ForeignKey(Battery, on_delete=models.PROTECT, related_name="powertrains", null=True, blank=True)
    transmission = models.ForeignKey(Transmission, on_delete=models.PROTECT, related_name="powertrains", null=True, blank=True)
    drive_type = models.ForeignKey(DriveType, on_delete=models.PROTECT, related_name="powertrains")
    system_power_kw = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    system_torque_nm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    electric_motors = models.ManyToManyField(ElectricMotor, through="PowertrainMotor", related_name="powertrains")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(type="ICE", combustion_engine__isnull=False, battery__isnull=True)
                | models.Q(type="BEV", combustion_engine__isnull=True, battery__isnull=False)
                | models.Q(type__in=["HEV", "PHEV", "EREV"], combustion_engine__isnull=False, battery__isnull=False),
                name="ck_powertrain_component_set",
            ),
            models.CheckConstraint(condition=models.Q(system_power_kw__isnull=True) | models.Q(system_power_kw__gte=0), name="ck_powertrain_power_nonnegative"),
            models.CheckConstraint(condition=models.Q(system_torque_nm__isnull=True) | models.Q(system_torque_nm__gte=0), name="ck_powertrain_torque_nonnegative"),
        ]

    def clean(self):
        super().clean()
        valid = {
            self.Type.ICE: self.combustion_engine_id is not None and self.battery_id is None,
            self.Type.BEV: self.combustion_engine_id is None and self.battery_id is not None,
            self.Type.HEV: self.combustion_engine_id is not None and self.battery_id is not None,
            self.Type.PHEV: self.combustion_engine_id is not None and self.battery_id is not None,
            self.Type.EREV: self.combustion_engine_id is not None and self.battery_id is not None,
        }
        if self.type and not valid.get(self.type, False):
            raise ValidationError("Powertrain components do not match its type.")

    def __str__(self):
        return f"{self.type} {self.drive_type.code} {self.system_power_kw or ''}".strip()

    def validate_motor_configuration(self):
        motor_count = sum(link.quantity for link in self.motor_links.all())
        if self.type == self.Type.ICE and motor_count:
            raise ValidationError("ICE powertrains cannot contain traction electric motors.")
        if self.type != self.Type.ICE and motor_count == 0:
            raise ValidationError("Electrified powertrains require at least one electric motor.")


class PowertrainMotor(TimeStampedModel):
    class Axle(models.TextChoices):
        FRONT = "front", "Front"
        REAR = "rear", "Rear"
        CENTRAL = "central", "Central"

    powertrain = models.ForeignKey(Powertrain, on_delete=models.CASCADE, related_name="motor_links")
    electric_motor = models.ForeignKey(ElectricMotor, on_delete=models.PROTECT, related_name="powertrain_links")
    axle = models.CharField(max_length=10, choices=Axle.choices)
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["powertrain", "electric_motor", "axle"], name="uq_powertrain_motor_axle")]

    def clean(self):
        super().clean()
        if self.powertrain_id and self.powertrain.type == Powertrain.Type.ICE:
            raise ValidationError("ICE powertrains cannot contain traction electric motors.")


class Modification(SourcedModel):
    generation = models.ForeignKey(Generation, on_delete=models.PROTECT, related_name="modifications")
    powertrain = models.ForeignKey(Powertrain, on_delete=models.PROTECT, related_name="modifications")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True)
    length_mm = models.PositiveIntegerField(null=True, blank=True)
    width_mm = models.PositiveIntegerField(null=True, blank=True)
    height_mm = models.PositiveIntegerField(null=True, blank=True)
    wheelbase_mm = models.PositiveIntegerField(null=True, blank=True)
    curb_weight_kg = models.PositiveIntegerField(null=True, blank=True)
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    cargo_l = models.PositiveIntegerField(null=True, blank=True)
    acceleration_0_100_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    top_speed_kmh = models.PositiveSmallIntegerField(null=True, blank=True)
    fuel_consumption_l_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    energy_consumption_kwh_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    range_km = models.PositiveIntegerField(null=True, blank=True)
    range_cycle = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    adas_systems = models.ManyToManyField("DriverAssistanceSystem", through="ModificationADAS", related_name="modifications", blank=True)

    class Meta:
        ordering = ["generation", "name"]
        constraints = [
            models.UniqueConstraint(fields=["generation", "name"], name="uq_mod_generation_name"),
            models.CheckConstraint(condition=models.Q(acceleration_0_100_s__isnull=True) | models.Q(acceleration_0_100_s__gte=0), name="ck_mod_acceleration_nonnegative"),
            models.CheckConstraint(condition=models.Q(fuel_consumption_l_100km__isnull=True) | models.Q(fuel_consumption_l_100km__gte=0), name="ck_mod_fuel_consumption_nonnegative"),
            models.CheckConstraint(condition=models.Q(energy_consumption_kwh_100km__isnull=True) | models.Q(energy_consumption_kwh_100km__gte=0), name="ck_mod_energy_consumption_nonnegative"),
        ]
        indexes = [models.Index(fields=["generation", "is_active"], name="idx_mod_generation_active")]

    def __str__(self):
        return f"{self.generation.model} {self.name}"


class Market(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="markets", null=True, blank=True)

    def __str__(self):
        return self.name


class ModificationMarket(TimeStampedModel):
    modification = models.ForeignKey(Modification, on_delete=models.CASCADE, related_name="market_offers")
    market = models.ForeignKey(Market, on_delete=models.PROTECT, related_name="modification_offers")
    sales_name = models.CharField(max_length=180, blank=True)
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["modification", "market"], name="uq_modification_market"),
            models.CheckConstraint(
                condition=models.Q(available_to__isnull=True) | models.Q(available_from__isnull=True) | models.Q(available_to__gte=models.F("available_from")),
                name="ck_mod_market_date_order",
            ),
        ]
        indexes = [models.Index(fields=["market", "modification"], name="idx_market_modification")]

    def __str__(self):
        return f"{self.modification} — {self.market}"


class TrimLevel(TimeStampedModel):
    modification_market = models.ForeignKey(ModificationMarket, on_delete=models.CASCADE, related_name="trim_levels")
    name = models.CharField(max_length=160)
    price_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    equipment_summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["modification_market", "name"], name="uq_trim_offer_name"),
            models.CheckConstraint(condition=models.Q(price_amount__isnull=True) | models.Q(price_amount__gte=0), name="ck_trim_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_from__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")),
                name="ck_trim_date_order",
            ),
        ]

    def __str__(self):
        return f"{self.modification_market}: {self.name}"


class ModelTechnology(TimeStampedModel):
    model = models.ForeignKey(Model, on_delete=models.CASCADE, related_name="technology_links")
    technology = models.ForeignKey(Technology, on_delete=models.PROTECT, related_name="model_links")
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["model", "technology"], name="uq_model_technology")]


class GenerationTechnology(TimeStampedModel):
    generation = models.ForeignKey(Generation, on_delete=models.CASCADE, related_name="technology_links")
    technology = models.ForeignKey(Technology, on_delete=models.PROTECT, related_name="generation_links")
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["generation", "technology"], name="uq_generation_technology")]


class DriverAssistanceSystem(SourcedModel):
    name = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ModificationADAS(TimeStampedModel):
    class Availability(models.TextChoices):
        STANDARD = "standard", "Standard"
        OPTIONAL = "optional", "Optional"
        UNAVAILABLE = "unavailable", "Unavailable"

    modification = models.ForeignKey(Modification, on_delete=models.CASCADE, related_name="adas_links")
    adas = models.ForeignKey(DriverAssistanceSystem, on_delete=models.PROTECT, related_name="modification_links")
    availability = models.CharField(max_length=20, choices=Availability.choices)
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["modification", "adas"], name="uq_modification_adas")]
