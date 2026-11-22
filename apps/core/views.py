from django.db.models import Count, Q
from django.shortcuts import render

from apps.cars.models import Brand, Model, Modification, Powertrain, Technology
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


def home(request):
    context = {
        "popular_brands": Brand.objects.filter(is_active=True)
        .select_related("manufacturer")
        .annotate(model_count=Count("models", filter=Q(models__is_active=True)))
        .order_by("-model_count", "name")[:4],
        "popular_models": Model.objects.filter(is_active=True)
        .select_related("brand")
        .prefetch_related("technologies")[:4],
        "articles": Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("tags")[:3],
        "technologies": Technology.objects.filter(is_active=True).order_by("name")[:4],
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
