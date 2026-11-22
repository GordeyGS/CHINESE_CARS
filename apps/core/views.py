from django.db.models import Count, Q
from django.shortcuts import render

from apps.cars.models import Brand, Model, Modification, Powertrain, Technology
from apps.cars.units import format_power
from apps.knowledge.models import Article, Source


POWERTRAIN_EXPLANATIONS = {
    Powertrain.Type.ICE: ("Internal Combustion Engine", "Движение обеспечивает только двигатель внутреннего сгорания; тяговой батареи нет."),
    Powertrain.Type.BEV: ("Battery Electric Vehicle", "Электромобиль: только электродвигатели и тяговая батарея, ДВС отсутствует."),
    Powertrain.Type.HEV: ("Hybrid Electric Vehicle", "Гибрид без внешней зарядки: батарея заряжается от ДВС и рекуперации."),
    Powertrain.Type.PHEV: ("Plug-in Hybrid Electric Vehicle", "Подключаемый гибрид: ДВС, батарея и электромотор, батарею можно заряжать от сети."),
    Powertrain.Type.EREV: ("Extended-Range Electric Vehicle", "Электромобиль с увеличенным запасом хода: колёса вращает электромотор, ДВС в основном работает генератором."),
}

HIERARCHY_TERMS = (
    ("Производитель", "Концерн или компания, владеющая марками, например Geely Holding."),
    ("Марка", "Коммерческий бренд производителя, например Zeekr."),
    ("Модель", "Семейство автомобилей под устойчивым названием, например Zeekr 001."),
    ("Поколение", "Этап развития модели с определённой платформой, кузовом и годами выпуска."),
    ("Модификация", "Конкретное техническое исполнение: силовая установка, привод, мощность, запас хода."),
    ("Комплектация", "Набор оснащения модификации для рынка с ценой, валютой и периодом актуальности."),
)


HERO_MODEL_SLUGS = ("xiaomi-su7", "zeekr-001", "byd-seal")
HOME_QUERIES = ("Blade Battery", "Zeekr 001", "электромобиль", "Какие электромобили BYD используют Blade Battery?")


def _hero_model():
    """Pick a showcase model with a photo; the order is fixed so the page is predictable."""
    with_photo = Model.objects.filter(is_active=True).exclude(image_url="").select_related("brand")
    for slug in HERO_MODEL_SLUGS:
        vehicle = with_photo.filter(slug=slug).first()
        if vehicle:
            return vehicle
    return with_photo.first()


def _showcase_models(limit):
    """Models with photos first, then the rest, so the grid is never empty."""
    active = Model.objects.filter(is_active=True).select_related("brand").order_by("brand__name", "name")
    models = list(active.exclude(image_url="")[:limit])
    if len(models) < limit:
        models += list(active.filter(image_url="")[: limit - len(models)])
    return models


def home(request):
    hero_model = _hero_model()
    hero_specs = []
    if hero_model:
        modification = (
            Modification.objects.filter(generation__model=hero_model, is_active=True)
            .select_related("powertrain__drive_type")
            .order_by("-powertrain__system_power_kw")
            .first()
        )
        if modification:
            hero_specs = [modification.powertrain.type, modification.powertrain.drive_type.code]
            if modification.powertrain.system_power_kw:
                hero_specs.append(format_power(modification.powertrain.system_power_kw))
            if modification.range_km:
                hero_specs.append(f"{modification.range_km} км")
    context = {
        "hero_model": hero_model,
        "hero_specs": hero_specs,
        "home_queries": HOME_QUERIES,
        "stats": {
            "brands": Brand.objects.filter(is_active=True).count(),
            "models": Model.objects.filter(is_active=True).count(),
            "modifications": Modification.objects.filter(is_active=True).count(),
            "articles": Article.objects.filter(status=Article.Status.PUBLISHED).count(),
        },
        "brands": Brand.objects.filter(is_active=True)
        .annotate(model_count=Count("models", filter=Q(models__is_active=True)))
        .order_by("name"),
        "popular_models": _showcase_models(limit=8),
        "articles": Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")[:3],
        "technologies": Technology.objects.filter(is_active=True).order_by("name")[:5],
    }
    return render(request, "core/home.html", context)


def guide(request):
    """General knowledge page: terms, conventions and how to use the knowledge base."""
    counts = dict(
        Modification.objects.filter(is_active=True, generation__model__is_active=True)
        .values_list("powertrain__type")
        .annotate(total=Count("id"))
    )
    powertrain_types = [
        {
            "code": value,
            "full_name": POWERTRAIN_EXPLANATIONS[value][0],
            "description": POWERTRAIN_EXPLANATIONS[value][1],
            "count": counts.get(value, 0),
        }
        for value in Powertrain.Type.values
    ]
    context = {
        "powertrain_types": powertrain_types,
        "hierarchy_terms": HIERARCHY_TERMS,
        "stats": {
            "brands": Brand.objects.filter(is_active=True).count(),
            "models": Model.objects.filter(is_active=True).count(),
            "modifications": sum(counts.values()),
            "articles": Article.objects.filter(status=Article.Status.PUBLISHED).count(),
            "sources": Source.objects.filter(is_active=True).count(),
        },
    }
    return render(request, "core/guide.html", context)
