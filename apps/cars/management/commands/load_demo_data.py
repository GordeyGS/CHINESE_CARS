from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cars.models import (
    Battery,
    BodyType,
    Brand,
    Country,
    DriveType,
    ElectricMotor,
    Generation,
    Manufacturer,
    Model,
    ModelTechnology,
    Modification,
    Platform,
    Powertrain,
    PowertrainMotor,
    Technology,
)
from apps.knowledge.models import Article, Category, Source, Tag, VideoResource


class Command(BaseCommand):
    help = "Load a small idempotent demonstration knowledge base."

    def handle(self, *args, **options):
        china, _ = Country.objects.get_or_create(name="China", iso_code="CN")
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
        blade.save(update_fields=["description"])
        sea, _ = Technology.objects.get_or_create(
            name="SEA Architecture",
            defaults={"slug": "sea-architecture", "category": "platform", "description": "Geely electric vehicle architecture."},
        )
        sea.description = "Платформа SEA для электромобилей Geely и модели Zeekr 001."
        sea.save(update_fields=["description"])
        byd_platform, _ = Platform.objects.get_or_create(
            manufacturer=byd_group, name="e-Platform 3.0", defaults={"slug": "e-platform-3"}
        )
        sea_platform, _ = Platform.objects.get_or_create(
            manufacturer=geely_group, name="SEA", defaults={"slug": "sea", "description": "Sustainable Experience Architecture."}
        )
        sedan, _ = BodyType.objects.get_or_create(code="sedan", defaults={"name": "Sedan"})
        liftback, _ = BodyType.objects.get_or_create(code="liftback", defaults={"name": "Liftback"})
        rwd, _ = DriveType.objects.get_or_create(code="RWD", defaults={"name": "Rear-wheel drive"})
        awd, _ = DriveType.objects.get_or_create(code="AWD", defaults={"name": "All-wheel drive"})
        blade_battery, _ = Battery.objects.get_or_create(
            manufacturer=byd_group,
            name="Blade Battery 82.5 kWh",
            defaults={"technology": blade, "chemistry": "LFP", "gross_capacity_kwh": 82.5},
        )
        zeekr_battery, _ = Battery.objects.get_or_create(
            manufacturer=geely_group,
            name="Zeekr 100 kWh battery",
            defaults={"chemistry": "NCM", "gross_capacity_kwh": 100},
        )
        byd_motor, _ = ElectricMotor.objects.get_or_create(
            manufacturer=byd_group, code="BYD-230-R", defaults={"power_kw": 230, "torque_nm": 360}
        )
        zeekr_front, _ = ElectricMotor.objects.get_or_create(
            manufacturer=geely_group, code="ZEEKR-200-F", defaults={"power_kw": 200}
        )
        zeekr_rear, _ = ElectricMotor.objects.get_or_create(
            manufacturer=geely_group, code="ZEEKR-200-R", defaults={"power_kw": 200}
        )
        byd_pt, _ = Powertrain.objects.get_or_create(
            type=Powertrain.Type.BEV, battery=blade_battery, drive_type=rwd, defaults={"system_power_kw": 230}
        )
        PowertrainMotor.objects.get_or_create(powertrain=byd_pt, electric_motor=byd_motor, axle="rear")
        zeekr_pt, _ = Powertrain.objects.get_or_create(
            type=Powertrain.Type.BEV, battery=zeekr_battery, drive_type=awd, defaults={"system_power_kw": 400}
        )
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
        seal_gen, _ = Generation.objects.get_or_create(
            model=seal,
            name="First generation",
            defaults={"platform": byd_platform, "body_type": sedan, "start_year": 2022, "code": "2022"},
        )
        zeekr_gen, _ = Generation.objects.get_or_create(
            model=zeekr_001,
            name="First generation",
            defaults={"platform": sea_platform, "body_type": liftback, "start_year": 2021, "code": "DC1E"},
        )
        seal_mod, _ = Modification.objects.get_or_create(
            generation=seal_gen,
            name="Long Range RWD",
            defaults={"slug": "byd-seal-long-range-rwd", "powertrain": byd_pt, "range_km": 570, "range_cycle": "WLTP"},
        )
        seal_mod.source_note = "Электромобиль BYD с технологией Blade Battery и задним приводом."
        seal_mod.save(update_fields=["source_note"])
        zeekr_mod, _ = Modification.objects.get_or_create(
            generation=zeekr_gen,
            name="AWD 100 kWh",
            defaults={"slug": "zeekr-001-awd-100", "powertrain": zeekr_pt, "range_km": 580, "range_cycle": "WLTP"},
        )
        zeekr_mod.source_note = "Полноприводный электромобиль Zeekr 001 на платформе SEA."
        zeekr_mod.save(update_fields=["source_note"])

        user, created = get_user_model().objects.get_or_create(username="demo_editor", defaults={"email": "demo@example.com"})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        category, _ = Category.objects.get_or_create(name="Technologies", defaults={"slug": "technologies"})
        ev_tag, _ = Tag.objects.get_or_create(name="Electric vehicles", defaults={"slug": "electric-vehicles"})
        byd_source, _ = Source.objects.get_or_create(
            url="https://www.bydglobal.com/", defaults={"name": "BYD official website", "publisher": "BYD"}
        )
        zeekr_source, _ = Source.objects.get_or_create(
            url="https://www.zeekrglobal.com/", defaults={"name": "Zeekr official website", "publisher": "Zeekr"}
        )
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
        sea_article.body = "Zeekr 001 — китайский электромобиль на платформе SEA с полным приводом."
        sea_article.status = Article.Status.PUBLISHED
        sea_article.published_at = sea_article.published_at or timezone.now()
        sea_article.save(update_fields=["summary", "body", "status", "published_at"])
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
        video.save(update_fields=["title", "description", "is_active"])
        video.articles.add(blade_article, sea_article)
        video.vehicle_models.add(seal, zeekr_001)
        video.technologies.add(blade, sea)
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {seal_mod}; {zeekr_mod}."))
