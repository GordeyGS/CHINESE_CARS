from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cars.models import (
    Battery, BodyType, Brand, CombustionEngine, Country, DriveType,
    DriverAssistanceSystem, ElectricMotor, Generation, Manufacturer, Market,
    Model, ModelTechnology, Modification, ModificationADAS,
    ModificationMarket, Platform, Powertrain, PowertrainMotor, Technology,
    Transmission, TrimLevel,
)
from apps.knowledge.models import Article, Category, Source, Tag, VideoResource


ACCESSED_AT = date(2026, 10, 6)

SOURCES = {
    "byd": ("BYD SEAL and SEAL U DM-i", "BYD", "https://www.byd.com/eu/electric-cars/seal"),
    "zeekr": ("ZEEKR 001 and ZEEKR X", "ZEEKR", "https://www.zeekr.eu/models/001"),
    "geely": ("Geely global model range", "Geely Auto", "https://global.geely.com/en/models"),
    "chery": ("TIGGO model range", "Chery International", "https://www.cheryinternational.com/pc/models/"),
    "li-auto": ("Li L6 and Li L7", "Li Auto", "https://www.lixiang.com/en"),
    "nio": ("NIO ET5 and EL6", "NIO", "https://www.nio.com/et5"),
    "xiaomi": ("Xiaomi EV model information", "Xiaomi EV", "https://www.xiaomiev.com/"),
    "hongqi": ("Hongqi H5 and E-HS9", "Hongqi", "https://www.hongqi-auto.com/pages/cartype/cartype_h5.html"),
    "blade": ("Blade Battery", "BYD", "https://www.bydglobal.com/en/Technology.html"),
    "sea": ("Sustainable Experience Architecture", "ZEEKR", "https://www.zeekrglobal.com/technology"),
}

# One generation and two representative configurations per model. Values describe
# the named market/version in the cited manufacturer material; absent facts stay NULL.
VEHICLES = [
    # brand, model, segment, body, platform, start year, source, variants
    ("BYD", "Seal", "D", "sedan", "e-Platform 3.0", 2022, "byd", [
        ("Excellence AWD", "BEV", "AWD", 390, 82.5, 520, "WLTP"),
    ]),
    ("BYD", "Seal U DM-i", "D-SUV", "suv", "DM-i", 2024, "byd", [
        ("Boost FWD", "PHEV", "FWD", 160, 18.3, 80, "WLTP"),
        ("Design AWD", "PHEV", "AWD", 238, 18.3, 70, "WLTP"),
    ]),
    ("Zeekr", "001", "E", "liftback", "SEA", 2021, "zeekr", [
        ("Long Range RWD", "BEV", "RWD", 200, 100, 620, "WLTP"),
    ]),
    ("Zeekr", "X", "C-SUV", "suv", "SEA", 2023, "zeekr", [
        ("Long Range RWD", "BEV", "RWD", 200, 69, 446, "WLTP"),
        ("Privilege AWD", "BEV", "AWD", 315, 69, 425, "WLTP"),
    ]),
    ("Geely", "Monjaro", "D-SUV", "suv", "CMA", 2021, "geely", [
        ("2.0T 2WD", "ICE", "FWD", 160, None, None, ""),
        ("2.0T 4WD", "ICE", "AWD", 175, None, None, ""),
    ]),
    ("Geely", "EX5", "C-SUV", "suv", "GEA", 2024, "geely", [
        ("Pro FWD", "BEV", "FWD", 160, 49.5, 430, "CLTC"),
        ("Max FWD", "BEV", "FWD", 160, 60.2, 530, "CLTC"),
    ]),
    ("Chery", "Tiggo 8 Pro Max", "D-SUV", "suv", "T1X", 2022, "chery", [
        ("2.0T 2WD", "ICE", "FWD", 187, None, None, ""),
        ("2.0T AWD", "ICE", "AWD", 187, None, None, ""),
    ]),
    ("Chery", "Tiggo 7 CSH", "C-SUV", "suv", "T1X", 2025, "chery", [
        ("PHEV FWD", "PHEV", "FWD", 255, 18.3, 90, "WLTP"),
        ("PHEV FWD Long Range", "PHEV", "FWD", 255, 18.3, 93, "WLTP"),
    ]),
    ("Li Auto", "L6", "D-SUV", "suv", "Li Auto EREV", 2024, "li-auto", [
        ("Pro AWD", "EREV", "AWD", 300, 36.8, 212, "CLTC"),
        ("Max AWD", "EREV", "AWD", 300, 36.8, 212, "CLTC"),
    ]),
    ("Li Auto", "L7", "E-SUV", "suv", "Li Auto EREV", 2023, "li-auto", [
        ("Pro AWD", "EREV", "AWD", 330, 42.8, 225, "CLTC"),
        ("Ultra AWD", "EREV", "AWD", 330, 52.3, 286, "CLTC"),
    ]),
    ("NIO", "ET5", "D", "sedan", "NT2.0", 2022, "nio", [
        ("Standard Range AWD", "BEV", "AWD", 360, 75, 456, "WLTP"),
        ("Long Range AWD", "BEV", "AWD", 360, 100, 590, "WLTP"),
    ]),
    ("NIO", "ES6", "D-SUV", "suv", "NT2.0", 2023, "nio", [
        ("Standard Range AWD", "BEV", "AWD", 360, 75, 490, "CLTC"),
        ("Long Range AWD", "BEV", "AWD", 360, 100, 625, "CLTC"),
    ]),
    ("Xiaomi", "SU7", "E", "sedan", "Modena", 2024, "xiaomi", [
        ("Pro RWD", "BEV", "RWD", 220, 94.3, 830, "CLTC"),
        ("Max AWD", "BEV", "AWD", 495, 101, 800, "CLTC"),
    ]),
    ("Xiaomi", "YU7", "D-SUV", "suv", "Modena", 2025, "xiaomi", [
        ("Standard RWD", "BEV", "RWD", 235, 96.3, 835, "CLTC"),
        ("Max AWD", "BEV", "AWD", 508, 101.7, 760, "CLTC"),
    ]),
    ("Hongqi", "H5", "D", "sedan", "Hongqi FMA", 2022, "hongqi", [
        ("1.5T DCT", "ICE", "FWD", 124, None, None, ""),
        ("2.0T AT", "ICE", "FWD", 165, None, None, ""),
    ]),
    ("Hongqi", "E-HS9", "F-SUV", "suv", "Hongqi EV", 2020, "hongqi", [
        ("Executive AWD", "BEV", "AWD", 320, 99, 465, "WLTP"),
        ("President AWD", "BEV", "AWD", 405, 120, 515, "WLTP"),
    ]),
]

BRANDS = {
    "BYD": ("BYD Company", 1995, 2003, "byd"),
    "Zeekr": ("Geely Holding", 1986, 2021, "zeekr"),
    "Geely": ("Geely Holding", 1986, 1997, "geely"),
    "Chery": ("Chery Automobile", 1997, 1997, "chery"),
    "Li Auto": ("Li Auto Inc.", 2015, 2015, "li-auto"),
    "NIO": ("NIO Inc.", 2014, 2014, "nio"),
    "Xiaomi": ("Xiaomi Corporation", 2010, 2021, "xiaomi"),
    "Hongqi": ("FAW Group", 1953, 1958, "hongqi"),
}


class Command(BaseCommand):
    help = "Load the idempotent, source-backed course knowledge-base dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        # Preserve and upgrade the original demonstration scenario on an empty DB.
        # Calling the legacy command again after this richer seed has updated codes
        # would make its code-based generation lookup collide with the stable name.
        if not (Model.objects.filter(brand__name="BYD", name="Seal").exists() and Model.objects.filter(brand__name="Zeekr", name="001").exists()):
            call_command("load_demo_data", verbosity=0)
        self._remove_superseded_course_rows()
        china, _ = Country.objects.update_or_create(iso_code="CN", defaults={"name": "Китай"})
        sources = self._sources()
        brands = {}
        for brand_name, (manufacturer_name, founded, brand_founded, source_key) in BRANDS.items():
            manufacturer, _ = Manufacturer.objects.update_or_create(
                name=manufacturer_name,
                defaults={
                    "slug": self._slug(manufacturer_name), "country": china,
                    "founded_year": founded, "description": f"Китайский производитель, связанный с маркой {brand_name}.",
                    "source_url": SOURCES[source_key][2], "source_note": "Официальный сайт производителя.",
                },
            )
            brand, _ = Brand.objects.update_or_create(
                manufacturer=manufacturer, name=brand_name,
                defaults={
                    "slug": self._slug(brand_name), "origin_country": china,
                    "founded_year": brand_founded, "description": f"Китайская автомобильная марка {brand_name}.",
                    "source_url": SOURCES[source_key][2], "source_note": "Официальный сайт марки.",
                },
            )
            brands[brand_name] = brand

        body_types = {
            code: BodyType.objects.update_or_create(code=code, defaults={"name": name})[0]
            for code, name in (("sedan", "Седан"), ("suv", "Кроссовер / SUV"), ("liftback", "Лифтбэк"))
        }
        drives = {
            code: DriveType.objects.update_or_create(code=code, defaults={"name": name})[0]
            for code, name in (("FWD", "Передний привод"), ("RWD", "Задний привод"), ("AWD", "Полный привод"))
        }
        technologies = self._technologies()
        adas = self._adas()
        china_market, _ = Market.objects.update_or_create(code="CN", defaults={"name": "Китай", "country": china})

        seeded_models = {}
        for brand_name, model_name, segment, body, platform_name, start_year, source_key, variants in VEHICLES:
            brand = brands[brand_name]
            platform, _ = Platform.objects.update_or_create(
                manufacturer=brand.manufacturer, name=platform_name,
                defaults={"slug": self._slug(f"{brand_name}-{platform_name}"), "description": f"Архитектура {platform_name}.", "source_url": SOURCES[source_key][2]},
            )
            model, _ = Model.objects.update_or_create(
                brand=brand, name=model_name,
                defaults={"slug": self._slug(f"{brand_name}-{model_name}"), "segment": segment, "description": f"{brand_name} {model_name}: серийная модель актуального поколения.", "source_url": SOURCES[source_key][2], "source_note": "Рынок и версия указаны на уровне модификации."},
            )
            seeded_models[f"{brand_name} {model_name}"] = model
            generation = model.generations.order_by("start_year").first()
            generation_values = {"code": str(start_year), "platform": platform, "body_type": body_types[body], "start_year": start_year, "description": f"Поколение {model_name}, выпускаемое с {start_year} года.", "source_url": SOURCES[source_key][2]}
            if generation is None:
                generation = Generation.objects.create(model=model, name="Актуальное поколение", **generation_values)
            else:
                for field, value in generation_values.items():
                    setattr(generation, field, value)
                generation.save()
            tech = self._technology_for(platform_name, technologies)
            if tech:
                ModelTechnology.objects.update_or_create(model=model, technology=tech, defaults={"note": f"Связано с архитектурой {platform_name}."})
            for variant in variants:
                self._variant(model, generation, drives, china_market, adas, source_key, *variant)

        self._content(seeded_models, technologies, adas, sources)
        self.stdout.write(self.style.SUCCESS(
            f"Course data ready: {Brand.objects.count()} brands, {Model.objects.count()} models, "
            f"{Modification.objects.count()} modifications, {Article.objects.count()} articles."
        ))

    def _sources(self):
        result = {}
        for key, (name, publisher, url) in SOURCES.items():
            result[key], _ = Source.objects.update_or_create(
                url=url, defaults={"name": name, "publisher": publisher, "accessed_at": ACCESSED_AT, "notes": "Официальный сайт или официальный материал производителя.", "is_active": True},
            )
        return result

    def _remove_superseded_course_rows(self):
        """Remove only obsolete rows created by an earlier revision of this command."""
        slugs = ("byd-seal-design-rwd", "zeekr-001-performance-awd")
        obsolete = list(Modification.objects.filter(slug__in=slugs, source_note__startswith="Конкретная версия"))
        powertrain_ids = [item.powertrain_id for item in obsolete]
        Modification.objects.filter(pk__in=[item.pk for item in obsolete]).delete()
        Powertrain.objects.filter(pk__in=powertrain_ids, modifications__isnull=True, source_note__startswith="course:").delete()

    def _technologies(self):
        rows = [
            ("Blade Battery", "Батареи", "LFP-батарея BYD с ячейками лезвийного формата.", "blade"),
            ("e-Platform 3.0", "Платформы", "Электромобильная платформа BYD.", "byd"),
            ("DM-i Super Hybrid", "Гибриды", "Подключаемая гибридная архитектура BYD.", "byd"),
            ("SEA Architecture", "Платформы", "Масштабируемая электрическая архитектура Geely Holding.", "sea"),
            ("Cell-to-Body", "Батареи", "Интеграция батареи в силовую структуру кузова.", "byd"),
            ("800-volt architecture", "Зарядка", "Высоковольтная архитектура для высокой мощности зарядки.", "xiaomi"),
            ("NIO Battery Swap", "Зарядка", "Система автоматизированной замены тяговой батареи NIO.", "nio"),
            ("Li Auto range extender", "Гибриды", "Последовательная EREV-архитектура Li Auto.", "li-auto"),
            ("Chery Super Hybrid", "Гибриды", "Подключаемая гибридная система семейства Chery CSH.", "chery"),
        ]
        result = {}
        for name, category, description, source_key in rows:
            result[name], _ = Technology.objects.update_or_create(
                name=name, defaults={"slug": self._slug(name), "category": category, "description": description, "source_url": SOURCES[source_key][2], "source_note": "Официальный материал производителя."},
            )
        return result

    def _adas(self):
        rows = [
            ("Адаптивный круиз-контроль", "adaptive-cruise-control", "Продольное управление"),
            ("Ассистент удержания в полосе", "lane-keeping-assist", "Поперечное управление"),
            ("Автоматическое экстренное торможение", "automatic-emergency-braking", "Активная безопасность"),
            ("Контроль слепых зон", "blind-spot-monitoring", "Контроль окружения"),
            ("Парковочный ассистент", "parking-assistance", "Парковка"),
        ]
        result = []
        for name, slug, category in rows:
            item, _ = DriverAssistanceSystem.objects.update_or_create(
                name=name, defaults={"slug": slug, "category": category, "level": "Функция ADAS", "description": f"Типовая функция ADAS: {name.lower()}."},
            )
            result.append(item)
        return result

    def _variant(self, model, generation, drives, market, adas, source_key, name, pt_type, drive, power, capacity, range_km, cycle):
        token = self._slug(f"{model.brand.name}-{model.name}-{name}")
        manufacturer = model.brand.manufacturer
        battery = engine = motor = None
        if pt_type != "ICE":
            battery, _ = Battery.objects.update_or_create(
                manufacturer=manufacturer, name=f"{model.brand.name} {model.name} {capacity} кВт·ч",
                defaults={"chemistry": "", "gross_capacity_kwh": Decimal(str(capacity)), "source_url": SOURCES[source_key][2]},
            )
            motor, _ = ElectricMotor.objects.update_or_create(
                manufacturer=manufacturer, code=f"COURSE-{token[:80]}",
                defaults={"motor_type": "Тяговый электродвигатель", "power_kw": Decimal(str(power)), "source_url": SOURCES[source_key][2]},
            )
        if pt_type in {"ICE", "PHEV", "EREV", "HEV"}:
            engine, _ = CombustionEngine.objects.update_or_create(
                manufacturer=manufacturer, code=f"COURSE-ICE-{self._slug(model.name)[:60]}",
                defaults={"fuel_type": CombustionEngine.FuelType.PETROL, "induction": "Турбонаддув", "source_url": SOURCES[source_key][2]},
            )
        transmission, _ = Transmission.objects.update_or_create(
            manufacturer=manufacturer, name=f"COURSE {model.name} {pt_type}",
            defaults={"transmission_type": "Редуктор" if pt_type == "BEV" else "Автоматическая", "gears": 1 if pt_type == "BEV" else None, "source_url": SOURCES[source_key][2]},
        )
        powertrain, _ = Powertrain.objects.update_or_create(
            source_note=f"course:{token}",
            defaults={"type": pt_type, "combustion_engine": engine, "battery": battery, "transmission": transmission, "drive_type": drives[drive], "system_power_kw": Decimal(str(power)), "source_url": SOURCES[source_key][2]},
        )
        if motor:
            PowertrainMotor.objects.update_or_create(powertrain=powertrain, electric_motor=motor, axle="front" if drive == "FWD" else "rear", defaults={"quantity": 1})
        modification, _ = Modification.objects.update_or_create(
            slug=token,
            defaults={"generation": generation, "name": name, "powertrain": powertrain, "seats": 5, "range_km": range_km, "range_cycle": cycle, "source_url": SOURCES[source_key][2], "source_note": "Конкретная версия из официального модельного ряда; неизвестные поля не заполнены."},
        )
        offer, _ = ModificationMarket.objects.update_or_create(
            modification=modification, market=market,
            defaults={"sales_name": f"{model.brand.name} {model.name} {name}", "available_from": date(generation.start_year, 1, 1)},
        )
        TrimLevel.objects.update_or_create(
            modification_market=offer, name=name,
            defaults={"price_amount": None, "currency_code": "", "valid_from": None, "equipment_summary": "Цена не внесена: она зависит от даты и локального рынка.", "is_active": True},
        )
        # Official equipment differs by market; attach the conservative core set only.
        for system in adas[:3]:
            ModificationADAS.objects.update_or_create(modification=modification, adas=system, defaults={"availability": ModificationADAS.Availability.STANDARD, "note": "Состав следует сверять с локальной комплектацией."})

    def _content(self, models, technologies, adas, sources):
        user, created = get_user_model().objects.get_or_create(username="course_editor", defaults={"email": "course@example.com"})
        if created:
            user.set_unusable_password(); user.save(update_fields=["password"])
        categories = {}
        category_slugs = {"Производители": "manufacturers", "Электромобили": "electric-vehicles", "Гибриды": "hybrids", "Технологии": "technologies", "Безопасность": "safety", "Платформы": "platforms", "Системы помощи водителю": "adas"}
        for name, slug in category_slugs.items():
            categories[name], _ = Category.objects.update_or_create(name=name, defaults={"slug": slug, "description": f"Материалы по теме «{name}»."})
        tags = {}
        for name in ("BYD", "Zeekr", "BEV", "PHEV", "EREV", "Battery", "ADAS", "SEA", "Blade Battery"):
            tags[name], _ = Tag.objects.update_or_create(name=name, defaults={"slug": self._slug(name)})
        articles = [
            ("chinese-auto-industry", "Китайский автопром: структура и направления", "Производители", "Китайский автопром объединяет крупные концерны, самостоятельные марки и технологические компании. База знаний разделяет производителя, бренд, модель, поколение и модификацию, поэтому корпоративные связи не смешиваются с техническими характеристиками. Представленный набор показывает экспортные и внутренние модели без попытки охватить весь рынок.", ["geely", "chery"], [], []),
            ("china-electric-vehicles", "Электромобили Китая", "Электромобили", "Китайские BEV используют разные платформы, батарейные химии и схемы привода. В каталоге представлены городские кроссоверы, седаны и крупные SUV. Запас хода всегда следует читать вместе с циклом измерения: CLTC и WLTP нельзя считать взаимозаменяемыми.", ["byd", "zeekr", "nio", "xiaomi"], ["BYD Seal", "NIO ET5", "Xiaomi SU7"], []),
            ("powertrain-types", "BEV, HEV, PHEV и EREV: в чём различие", "Гибриды", "BEV движется только за счёт электротяги. PHEV допускает внешнюю зарядку и сочетает ДВС с электрической частью. EREV использует электрический привод, а ДВС преимущественно вырабатывает энергию. HEV не требует внешней зарядки. Эти типы хранятся отдельно, чтобы фильтрация и сравнение оставались однозначными.", ["byd", "li-auto"], ["BYD Seal U DM-i", "Li Auto L6"], []),
            ("blade-battery-course", "Blade Battery: назначение и применение", "Технологии", "Blade Battery — фирменная LFP-технология BYD. Длинные ячейки компонуются в батарейный блок с высокой эффективностью использования пространства. В базе технология отделена от конкретной батареи: одна описывает идею, другая — компонент определённой ёмкости.", ["blade", "byd"], ["BYD Seal"], ["Blade Battery"]),
            ("sea-platform-course", "Платформа SEA и автомобили Zeekr", "Платформы", "SEA — масштабируемая электрическая архитектура Geely Holding. Она служит основой для моделей разных классов. Связь платформы с поколением позволяет не приписывать одну архитектуру всем автомобилям бренда автоматически.", ["sea", "zeekr"], ["Zeekr 001", "Zeekr X"], ["SEA Architecture"]),
            ("high-voltage-ev", "Высоковольтные архитектуры электромобилей", "Технологии", "Повышение рабочего напряжения помогает передавать ту же мощность меньшим током и поддерживать быструю зарядку. Реальная скорость зарядки зависит не только от напряжения, но и от батареи, температуры, зарядной станции и программного управления.", ["xiaomi", "byd"], ["Xiaomi SU7"], ["800-volt architecture"]),
            ("adas-china", "Системы ADAS в китайских автомобилях", "Системы помощи водителю", "ADAS объединяет функции контроля дистанции, полосы, препятствий и парковки. Наличие функции не означает автономное вождение. Оснащение необходимо проверять для конкретной комплектации и рынка, поэтому база связывает ADAS с модификацией и указывает доступность.", ["nio", "zeekr"], [], []),
            ("major-chinese-brands", "Восемь марок в демонстрационной базе", "Производители", "Компактная выборка включает BYD, Zeekr, Geely, Chery, Li Auto, NIO, Xiaomi и Hongqi. Вместе они показывают массовые и премиальные марки, классические ДВС, подключаемые гибриды, последовательные гибриды и чистые электромобили.", ["byd", "zeekr", "geely", "chery", "li-auto", "nio", "xiaomi", "hongqi"], [], []),
            ("byd-development", "Развитие BYD: от батарей к автомобилям", "Производители", "Опыт BYD в аккумуляторах стал основой для электрических и гибридных автомобилей марки. В актуальном модельном ряду сосуществуют BEV и DM-i. Структура базы связывает фирменные технологии с моделями, не дублируя характеристики отдельных модификаций в статье.", ["byd", "blade"], ["BYD Seal", "BYD Seal U DM-i"], ["Blade Battery", "DM-i Super Hybrid"]),
            ("geely-zeekr-development", "Geely и Zeekr: концерн, бренд и платформа", "Производители", "Geely Holding выступает корпоративным уровнем, а Geely и Zeekr — отдельными марками. Такое различие важно для базы знаний: общая архитектура может использоваться связанными брендами, но модель всегда принадлежит конкретной марке.", ["geely", "zeekr", "sea"], ["Geely EX5", "Zeekr 001"], ["SEA Architecture"]),
        ]
        created_articles = {}
        published = datetime(2026, 9, 1, 9, 0, tzinfo=dt_timezone.utc)
        for slug, title, category, body, source_keys, model_keys, tech_names in articles:
            article, _ = Article.objects.update_or_create(
                slug=slug, defaults={"category": categories[category], "author": user, "title": title, "summary": body.split(". ")[0] + ".", "body": body, "status": Article.Status.PUBLISHED, "published_at": published},
            )
            article.sources.set([sources[k] for k in source_keys if k in sources])
            article.vehicle_models.set([models[k] for k in model_keys if k in models])
            article.technologies.set([technologies[k] for k in tech_names if k in technologies])
            article.tags.set([tag for name, tag in tags.items() if name.casefold() in (title + " " + body).casefold()])
            if slug == "adas-china": article.adas_systems.set(adas)
            created_articles[slug] = article
        videos = [
            ("BYD Auto Videos", "https://en.byd.com/auto/videos/", "BYD", "blade-battery-course", "BYD Seal", "Blade Battery"),
            ("ZEEKR 001", "https://www.youtube.com/@ZEEKRGlobal", "ZEEKR", "sea-platform-course", "Zeekr 001", "SEA Architecture"),
            ("NIO official videos", "https://www.nio.com/videos", "NIO", "china-electric-vehicles", "NIO ET5", "NIO Battery Swap"),
            ("Xiaomi EV", "https://www.youtube.com/@xiaomi", "Xiaomi", "high-voltage-ev", "Xiaomi SU7", "800-volt architecture"),
            ("Li Auto official videos", "https://www.liauto.com/about.html", "Li Auto", "powertrain-types", "Li Auto L6", "Li Auto range extender"),
        ]
        replaced_video_urls = {
            "https://www.youtube.com/watch?v=7sDqJ8o9h5s": "https://en.byd.com/auto/videos/",
            "https://www.youtube.com/@NIO": "https://www.nio.com/videos",
            "https://www.youtube.com/@LiAutoGlobal": "https://www.liauto.com/about.html",
        }
        for old_url, new_url in replaced_video_urls.items():
            old_video = VideoResource.objects.filter(url=old_url).first()
            if old_video and not VideoResource.objects.filter(url=new_url).exists():
                old_video.url = new_url
                old_video.save(update_fields=["url"])
        demo_video = VideoResource.objects.filter(url="https://example.com/videos/chinese-ev-demo").first()
        if demo_video:
            demo_video.url = "https://www.youtube.com/@cheryinternational"
            demo_video.title = "Chery International"
            demo_video.description = "Официальный видеоканал Chery International."
            demo_video.provider = "Chery International"
            demo_video.save(update_fields=["url", "title", "description", "provider"])
        for title, url, provider, article_slug, model_key, tech_name in videos:
            video, _ = VideoResource.objects.update_or_create(url=url, defaults={"title": title, "description": f"Официальный видеоматериал {provider}.", "provider": provider, "published_at": published, "is_active": True})
            video.articles.set([created_articles[article_slug]])
            if model_key in models: video.vehicle_models.set([models[model_key]])
            if tech_name in technologies: video.technologies.set([technologies[tech_name]])

    @staticmethod
    def _technology_for(platform_name, technologies):
        mapping = {"e-Platform 3.0": "e-Platform 3.0", "DM-i": "DM-i Super Hybrid", "SEA": "SEA Architecture", "Li Auto EREV": "Li Auto range extender"}
        return technologies.get(mapping.get(platform_name))

    @staticmethod
    def _slug(value):
        from django.utils.text import slugify
        return slugify(value, allow_unicode=False) or "course-item"
