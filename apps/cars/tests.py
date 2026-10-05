import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import (
    Battery, BodyType, Brand, Country, DriveType, ElectricMotor, Generation, Manufacturer,
    Model, ModelTechnology, Modification, Platform, Powertrain, Technology,
    PowertrainMotor,
)


@pytest.fixture
def vehicle_data(db):
    country = Country.objects.create(name="China", iso_code="CN")
    manufacturer = Manufacturer.objects.create(name="Geely Holding", slug="geely", country=country)
    brand = Brand.objects.create(manufacturer=manufacturer, origin_country=country, name="Zeekr", slug="zeekr")
    platform = Platform.objects.create(manufacturer=manufacturer, name="SEA", slug="sea")
    body = BodyType.objects.create(code="liftback", name="Liftback")
    vehicle_model = Model.objects.create(brand=brand, name="001", slug="zeekr-001")
    generation = Generation.objects.create(
        model=vehicle_model, platform=platform, body_type=body, name="First generation", start_year=2021
    )
    battery = Battery.objects.create(manufacturer=manufacturer, name="100 kWh", gross_capacity_kwh=100)
    drive = DriveType.objects.create(code="AWD", name="All-wheel drive")
    powertrain = Powertrain.objects.create(type=Powertrain.Type.BEV, battery=battery, drive_type=drive)
    modification = Modification.objects.create(
        generation=generation, powertrain=powertrain, name="AWD", slug="zeekr-001-awd"
    )
    return locals()


@pytest.mark.django_db
def test_vehicle_hierarchy(vehicle_data):
    data = vehicle_data
    assert data["manufacturer"].brands.get() == data["brand"]
    assert data["brand"].models.get() == data["vehicle_model"]
    assert data["vehicle_model"].generations.get() == data["generation"]
    assert data["generation"].modifications.get() == data["modification"]


@pytest.mark.django_db
def test_brand_name_is_unique_per_manufacturer(vehicle_data):
    with pytest.raises(IntegrityError), transaction.atomic():
        Brand.objects.create(
            manufacturer=vehicle_data["manufacturer"],
            origin_country=vehicle_data["country"],
            name="Zeekr",
            slug="zeekr-copy",
        )


@pytest.mark.django_db
def test_model_technology_relation(vehicle_data):
    technology = Technology.objects.create(name="SEA Architecture", slug="sea-architecture")
    ModelTechnology.objects.create(model=vehicle_data["vehicle_model"], technology=technology)
    assert list(vehicle_data["vehicle_model"].technologies.all()) == [technology]


@pytest.mark.django_db
def test_battery_usable_capacity_cannot_exceed_gross(vehicle_data):
    with pytest.raises(IntegrityError), transaction.atomic():
        Battery.objects.create(
            manufacturer=vehicle_data["manufacturer"],
            name="Invalid battery",
            gross_capacity_kwh=50,
            usable_capacity_kwh=60,
        )


@pytest.mark.django_db
def test_powertrain_component_validation(vehicle_data):
    invalid = Powertrain(type=Powertrain.Type.BEV, drive_type=vehicle_data["drive"])
    with pytest.raises(ValidationError):
        invalid.full_clean()


@pytest.mark.django_db
def test_electrified_powertrain_requires_motor(vehicle_data):
    powertrain = vehicle_data["powertrain"]
    with pytest.raises(ValidationError):
        powertrain.validate_motor_configuration()
    motor = ElectricMotor.objects.create(manufacturer=vehicle_data["manufacturer"], code="MOTOR-1")
    PowertrainMotor.objects.create(powertrain=powertrain, electric_motor=motor, axle="rear")
    powertrain.validate_motor_configuration()


@pytest.mark.django_db
def test_generation_year_constraint(vehicle_data):
    with pytest.raises(IntegrityError), transaction.atomic():
        Generation.objects.create(
            model=vehicle_data["vehicle_model"],
            platform=vehicle_data["platform"],
            body_type=vehicle_data["body"],
            name="Invalid years",
            start_year=2025,
            end_year=2020,
        )
