from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from apps.cars.models import (
    Battery,
    BodyType,
    Brand,
    Country,
    DriveType,
    DriverAssistanceSystem,
    ElectricMotor,
    Generation,
    Manufacturer,
    Model,
    ModelTechnology,
    Modification,
    ModificationADAS,
    ModificationMarket,
    Market,
    Platform,
    Powertrain,
    PowertrainMotor,
    Technology,
    Transmission,
    TrimLevel,
)
from apps.knowledge.models import Article, Category, Source, Tag, VideoResource


class Command(BaseCommand):
    help = "Load a small idempotent demonstration knowledge base."

    def handle(self, *args, **options):
        china, _ = Country.objects.update_or_create(iso_code="CN", defaults={"name": "Китай"})
        byd_group, _ = Manufacturer.objects.get_or_create(
            name="BYD Company", defaults={"slug": "byd-company", "country": china, "founded_year": 1995}
        )
        byd_group.description = "Китайский производитель электромобилей BYD и тяговых батарей."
        byd_group.save(update_fields=["description"])
        geely_group, _ = Manufacturer.objects.get_or_create(
            name="Geely Holding", defaults={"slug": "geely-holding", "country": china, "founded_year": 1986}
        )
        byd, _ = Brand.objects.get_or_create(
            manufacturer=byd_group,
            name="BYD",
            defaults={"slug": "byd", "origin_country": china, "founded_year": 2003},
        )
        byd.description = "Марка электромобилей BYD, использующая технологию Blade Battery."
        byd.save(update_fields=["description"])
        zeekr, _ = Brand.objects.get_or_create(
            manufacturer=geely_group,
            name="Zeekr",
            defaults={"slug": "zeekr", "origin_country": china, "founded_year": 2021},
        )
        zeekr.description = "Китайская премиальная марка электромобилей Zeekr."
        zeekr.save(update_fields=["description"])
        blade, _ = Technology.objects.get_or_create(
            name="Blade Battery",
            defaults={"slug": "blade-battery", "category": "battery", "description": "BYD LFP battery technology."},
        )
        blade.description = "Тяговая LFP-батарея Blade Battery компании BYD для электромобилей."
        blade.category = "Батареи"
        blade.save(update_fields=["description", "category"])
        sea, _ = Technology.objects.get_or_create(
            name="SEA Architecture",
            defaults={"slug": "sea-architecture", "category": "platform", "description": "Geely electric vehicle architecture."},
        )
        sea.description = "Платформа SEA для электромобилей Geely и модели Zeekr 001."
        sea.category = "Платформы"
        sea.save(update_fields=["description", "category"])
        byd_platform, _ = Platform.objects.get_or_create(
            manufacturer=byd_group, name="e-Platform 3.0", defaults={"slug": "e-platform-3"}
        )
        sea_platform, _ = Platform.objects.get_or_create(
            manufacturer=geely_group, name="SEA", defaults={"slug": "sea", "description": "Sustainable Experience Architecture."}
        )
        sea_platform.description = "Модульная архитектура Sustainable Experience Architecture для электромобилей."
        sea_platform.save(update_fields=["description"])
        sedan, _ = BodyType.objects.update_or_create(code="sedan", defaults={"name": "Седан"})
        liftback, _ = BodyType.objects.update_or_create(code="liftback", defaults={"name": "Лифтбэк"})
        rwd, _ = DriveType.objects.update_or_create(code="RWD", defaults={"name": "Задний привод"})
        awd, _ = DriveType.objects.update_or_create(code="AWD", defaults={"name": "Полный привод"})
        blade_battery = Battery.objects.filter(manufacturer=byd_group, technology=blade).first()
        if blade_battery is None:
            blade_battery = Battery.objects.create(manufacturer=byd_group, name="Blade Battery 82,5 кВт·ч")
        zeekr_battery = Battery.objects.filter(manufacturer=geely_group, gross_capacity_kwh=100).first()
        if zeekr_battery is None:
            zeekr_battery = Battery.objects.create(manufacturer=geely_group, name="Батарея Zeekr 100 кВт·ч")
        blade_battery.technology = blade
        blade_battery.chemistry = "LFP"
        blade_battery.gross_capacity_kwh = 82.5
        blade_battery.usable_capacity_kwh = 82.5
        blade_battery.voltage_v = 800
        blade_battery.save(
            update_fields=["technology", "chemistry", "gross_capacity_kwh", "usable_capacity_kwh", "voltage_v"]
        )
        blade_battery.name = "Blade Battery 82,5 кВт·ч"
        blade_battery.save(update_fields=["name"])
        zeekr_battery.chemistry = "NCM"
        zeekr_battery.gross_capacity_kwh = 100
        zeekr_battery.usable_capacity_kwh = 94
        zeekr_battery.voltage_v = 400
        zeekr_battery.save(update_fields=["chemistry", "gross_capacity_kwh", "usable_capacity_kwh", "voltage_v"])
        zeekr_battery.name = "Батарея Zeekr 100 кВт·ч"
        zeekr_battery.save(update_fields=["name"])
        byd_motor, _ = ElectricMotor.objects.get_or_create(
            manufacturer=byd_group, code="BYD-230-R", defaults={"power_kw": 230, "torque_nm": 360}
        )
        zeekr_front, _ = ElectricMotor.objects.get_or_create(
            manufacturer=geely_group, code="ZEEKR-200-F", defaults={"power_kw": 200}
        )
        zeekr_rear, _ = ElectricMotor.objects.get_or_create(
            manufacturer=geely_group, code="ZEEKR-200-R", defaults={"power_kw": 200}
        )
        zeekr_front.power_kw = 200
        zeekr_front.torque_nm = 343
        zeekr_front.save(update_fields=["power_kw", "torque_nm"])
        zeekr_rear.power_kw = 200
        zeekr_rear.torque_nm = 343
        zeekr_rear.save(update_fields=["power_kw", "torque_nm"])
        byd_transmission, _ = Transmission.objects.update_or_create(
            manufacturer=byd_group,
            name="Одноступенчатый редуктор BYD",
            defaults={"transmission_type": "Редуктор", "gears": 1},
        )
        zeekr_transmission, _ = Transmission.objects.update_or_create(
            manufacturer=geely_group,
            name="Одноступенчатый редуктор Zeekr",
            defaults={"transmission_type": "Редуктор", "gears": 1},
        )
        byd_pt, _ = Powertrain.objects.get_or_create(
            type=Powertrain.Type.BEV, battery=blade_battery, drive_type=rwd, defaults={"system_power_kw": 230}
        )
        byd_pt.transmission = byd_transmission
        byd_pt.system_power_kw = 230
        byd_pt.system_torque_nm = 360
        byd_pt.save(update_fields=["transmission", "system_power_kw", "system_torque_nm"])
        PowertrainMotor.objects.get_or_create(powertrain=byd_pt, electric_motor=byd_motor, axle="rear")
        zeekr_pt, _ = Powertrain.objects.get_or_create(
            type=Powertrain.Type.BEV, battery=zeekr_battery, drive_type=awd, defaults={"system_power_kw": 400}
        )
        zeekr_pt.transmission = zeekr_transmission
        zeekr_pt.system_power_kw = 400
        zeekr_pt.system_torque_nm = 686
        zeekr_pt.save(update_fields=["transmission", "system_power_kw", "system_torque_nm"])
        PowertrainMotor.objects.get_or_create(powertrain=zeekr_pt, electric_motor=zeekr_front, axle="front")
        PowertrainMotor.objects.get_or_create(powertrain=zeekr_pt, electric_motor=zeekr_rear, axle="rear")
        seal, _ = Model.objects.get_or_create(brand=byd, name="Seal", defaults={"slug": "byd-seal", "segment": "D"})
        zeekr_001, _ = Model.objects.get_or_create(brand=zeekr, name="001", defaults={"slug": "zeekr-001", "segment": "E"})
        seal.description = "Электромобиль BYD Seal использует тяговую батарею Blade Battery."
        seal.save(update_fields=["description"])
        zeekr_001.description = "Электромобиль Zeekr 001 построен на архитектуре SEA и доступен с полным приводом."
        zeekr_001.save(update_fields=["description"])
        ModelTechnology.objects.get_or_create(model=seal, technology=blade, defaults={"note": "Traction battery technology."})
        ModelTechnology.objects.get_or_create(model=zeekr_001, technology=sea)
        seal_gen, _ = Generation.objects.update_or_create(
            model=seal,
            code="2022",
            defaults={
                "name": "Первое поколение",
                "platform": byd_platform,
                "body_type": sedan,
                "start_year": 2022,
            },
        )
        zeekr_gen, _ = Generation.objects.update_or_create(
            model=zeekr_001,
            code="DC1E",
            defaults={
                "name": "Первое поколение",
                "platform": sea_platform,
                "body_type": liftback,
                "start_year": 2021,
            },
        )
        seal_mod, _ = Modification.objects.update_or_create(
            slug="byd-seal-long-range-rwd",
            defaults={
                "generation": seal_gen,
                "name": "Увеличенный запас хода RWD",
                "powertrain": byd_pt,
                "range_km": 570,
                "range_cycle": "WLTP",
            },
        )
        seal_mod.name = "Увеличенный запас хода RWD"
        seal_mod.powertrain = byd_pt
        seal_mod.length_mm = 4800
        seal_mod.width_mm = 1875
        seal_mod.height_mm = 1460
        seal_mod.wheelbase_mm = 2920
        seal_mod.curb_weight_kg = 2055
        seal_mod.seats = 5
        seal_mod.cargo_l = 400
        seal_mod.acceleration_0_100_s = 5.9
        seal_mod.top_speed_kmh = 180
        seal_mod.energy_consumption_kwh_100km = 16.6
        seal_mod.range_km = 570
        seal_mod.range_cycle = "WLTP"
        seal_mod.source_note = "Электромобиль BYD с технологией Blade Battery и задним приводом."
        seal_mod.save()
        zeekr_mod, _ = Modification.objects.update_or_create(
            slug="zeekr-001-awd-100",
            defaults={
                "generation": zeekr_gen,
                "name": "100 кВт·ч AWD",
                "powertrain": zeekr_pt,
                "range_km": 580,
                "range_cycle": "WLTP",
            },
        )
        zeekr_mod.name = "100 кВт·ч AWD"
        zeekr_mod.powertrain = zeekr_pt
        zeekr_mod.length_mm = 4977
        zeekr_mod.width_mm = 1999
        zeekr_mod.height_mm = 1560
        zeekr_mod.wheelbase_mm = 3005
        zeekr_mod.curb_weight_kg = 2350
        zeekr_mod.seats = 5
        zeekr_mod.cargo_l = 539
        zeekr_mod.acceleration_0_100_s = 3.8
        zeekr_mod.top_speed_kmh = 200
        zeekr_mod.energy_consumption_kwh_100km = 18.5
        zeekr_mod.range_km = 580
        zeekr_mod.range_cycle = "WLTP"
        zeekr_mod.source_note = "Полноприводный электромобиль Zeekr 001 на платформе SEA."
        zeekr_mod.save()

        europe, _ = Market.objects.update_or_create(code="EU", defaults={"name": "Европа", "country": None})
        seal_offer, _ = ModificationMarket.objects.update_or_create(
            modification=seal_mod,
            market=europe,
            defaults={"sales_name": "BYD Seal Design", "available_from": date(2023, 9, 1)},
        )
        zeekr_offer, _ = ModificationMarket.objects.update_or_create(
            modification=zeekr_mod,
            market=europe,
            defaults={"sales_name": "Zeekr 001 Privilege AWD", "available_from": date(2023, 10, 1)},
        )
        TrimLevel.objects.update_or_create(
            modification_market=seal_offer,
            name="Design",
            defaults={
                "price_amount": 46990,
                "currency_code": "EUR",
                "valid_from": date(2024, 1, 1),
                "equipment_summary": "Панорамная крыша, тепловой насос и комплекс систем помощи водителю.",
                "is_active": True,
            },
        )
        TrimLevel.objects.update_or_create(
            modification_market=zeekr_offer,
            name="Privilege AWD",
            defaults={
                "price_amount": 67490,
                "currency_code": "EUR",
                "valid_from": date(2024, 1, 1),
                "equipment_summary": "Двухмоторный полный привод, пневмоподвеска и расширенный ADAS.",
                "is_active": True,
            },
        )
        adaptive_cruise, _ = DriverAssistanceSystem.objects.update_or_create(
            slug="adaptive-cruise-control",
            defaults={
                "name": "Адаптивный круиз-контроль",
                "category": "Продольное управление",
                "description": "Поддерживает заданную скорость и дистанцию до впереди идущего автомобиля.",
                "is_active": True,
            },
        )
        lane_keeping, _ = DriverAssistanceSystem.objects.update_or_create(
            slug="lane-keeping-assist",
            defaults={
                "name": "Ассистент удержания в полосе",
                "category": "Поперечное управление",
                "description": "Помогает удерживать автомобиль в пределах полосы движения.",
                "is_active": True,
            },
        )
        for modification in (seal_mod, zeekr_mod):
            ModificationADAS.objects.update_or_create(
                modification=modification,
                adas=adaptive_cruise,
                defaults={"availability": ModificationADAS.Availability.STANDARD},
            )
            ModificationADAS.objects.update_or_create(
                modification=modification,
                adas=lane_keeping,
                defaults={"availability": ModificationADAS.Availability.STANDARD},
            )

        user, created = get_user_model().objects.get_or_create(username="demo_editor", defaults={"email": "demo@example.com"})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        category, _ = Category.objects.update_or_create(slug="technologies", defaults={"name": "Технологии"})
        ev_tag, _ = Tag.objects.update_or_create(slug="electric-vehicles", defaults={"name": "Электромобили"})
        byd_source, _ = Source.objects.get_or_create(
            url="https://www.bydglobal.com/", defaults={"name": "BYD official website", "publisher": "BYD"}
        )
        zeekr_source, _ = Source.objects.get_or_create(
            url="https://www.zeekrglobal.com/", defaults={"name": "Zeekr official website", "publisher": "Zeekr"}
        )
        byd_source.name = "Официальный сайт BYD"
        byd_source.save(update_fields=["name"])
        zeekr_source.name = "Официальный сайт Zeekr"
        zeekr_source.save(update_fields=["name"])
        blade_article, _ = Article.objects.get_or_create(
            slug="blade-battery-overview",
            defaults={
                "category": category,
                "author": user,
                "title": "Blade Battery: overview",
                "summary": "How BYD's Blade Battery relates to its electric vehicles.",
                "body": "A demonstration knowledge-base article about Blade Battery.",
                "status": Article.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        blade_article.title = "Blade Battery в электромобилях BYD"
        blade_article.summary = "Как тяговая батарея Blade Battery применяется в электромобилях BYD."
        blade_article.body = "Blade Battery — LFP-технология BYD. Электромобиль BYD Seal использует эту тяговую батарею."
        blade_article.status = Article.Status.PUBLISHED
        blade_article.published_at = blade_article.published_at or timezone.now()
        blade_article.save(update_fields=["title", "summary", "body", "status", "published_at"])
        blade_article.tags.add(ev_tag)
        blade_article.sources.add(byd_source)
        blade_article.vehicle_models.add(seal)
        blade_article.technologies.add(blade)
        sea_article, _ = Article.objects.get_or_create(
            slug="sea-platform-overview",
            defaults={
                "category": category,
                "author": user,
                "title": "SEA platform and Zeekr 001",
                "summary": "A demonstration article about the SEA platform.",
                "body": "Zeekr 001 is built on the SEA platform.",
                "status": Article.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        sea_article.summary = "Электромобиль Zeekr 001 и модульная платформа SEA."
        sea_article.title = "Платформа SEA и Zeekr 001"
        sea_article.body = "Zeekr 001 — китайский электромобиль на платформе SEA с полным приводом."
        sea_article.status = Article.Status.PUBLISHED
        sea_article.published_at = sea_article.published_at or timezone.now()
        sea_article.save(update_fields=["title", "summary", "body", "status", "published_at"])
        sea_article.sources.add(zeekr_source)
        sea_article.vehicle_models.add(zeekr_001)
        sea_article.technologies.add(sea)
        video, _ = VideoResource.objects.get_or_create(
            url="https://example.com/videos/chinese-ev-demo",
            defaults={
                "title": "Chinese EV technologies — demo video",
                "description": "Demonstration video metadata for the knowledge base.",
                "provider": "Demo provider",
                "published_at": timezone.now(),
            },
        )
        video.title = "BYD Blade Battery и Zeekr 001 — обзор электромобилей"
        video.description = "Видео о Blade Battery в электромобилях BYD и платформе SEA модели Zeekr 001."
        video.is_active = True
        video.provider = "Демо-провайдер"
        video.save(update_fields=["title", "description", "provider", "is_active"])
        video.articles.add(blade_article, sea_article)
        video.vehicle_models.add(seal, zeekr_001)
        video.technologies.add(blade, sea)
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {seal_mod}; {zeekr_mod}."))
