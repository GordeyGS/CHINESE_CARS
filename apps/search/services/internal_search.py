from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.functions import Concat
from django.urls import reverse

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
from apps.knowledge.models import Article, VideoResource

from .query_parser import ParsedQuery, QueryParser
from .ranking import annotate_ranked, calculate_score


@dataclass(frozen=True)
class SearchResult:
    result_type: str
    title: str
    description: str
    url: str
    score: float
    object_id: int
    source: str


@dataclass(frozen=True)
class SearchResponse:
    query: ParsedQuery
    groups: dict[str, list[SearchResult]]

    @property
    def total(self) -> int:
        return sum(len(results) for results in self.groups.values())


def _vector(*weighted_fields):
    config = getattr(settings, "SEARCH_FTS_CONFIG", "russian")
    result = None
    for field_name, weight in weighted_fields:
        current = SearchVector(field_name, weight=weight, config=config)
        result = current if result is None else result + current
    return result


def _snippet(text: str, fallback: str) -> str:
    compact = " ".join((text or fallback).split())
    return compact if len(compact) <= 220 else f"{compact[:217].rstrip()}…"


class InternalSearchService:
    def __init__(self, *, parser=None, group_limit=12):
        self.parser = parser or QueryParser()
        self.group_limit = group_limit

    def search(self, raw_query: str) -> SearchResponse:
        parsed = self.parser.parse(raw_query)
        groups = {
            "Articles": self._articles(parsed),
            "Cars": self._cars(parsed),
            "Technologies": self._technologies(parsed),
            "Videos": self._videos(parsed),
        }
        return SearchResponse(query=parsed, groups=groups)

    def _ranked_results(self, queryset, *, vector, parsed, trigram_expressions, factory):
        ranked = annotate_ranked(
            queryset,
            vector=vector,
            parsed=parsed,
            trigram_expressions=trigram_expressions,
        ).order_by("-full_text_rank", "-phrase_rank", "-trigram_similarity")[: self.group_limit * 2]
        results = []
        for item in ranked:
            result, searchable_text = factory(item)
            results.append(
                SearchResult(
                    result_type=result.result_type,
                    title=result.title,
                    description=result.description,
                    url=result.url,
                    score=calculate_score(item, parsed, result.title, searchable_text),
                    object_id=result.object_id,
                    source=result.source,
                )
            )
        return results

    @staticmethod
    def _draft_result(*, result_type, title, description, object_id, source, url=""):
        return SearchResult(result_type, title, description, url, 0.0, object_id, source)

    @staticmethod
    def _technology_url(item):
        if isinstance(item, Technology):
            return reverse("cars:technology-detail", args=[item.slug])
        prefix = "platform" if isinstance(item, Platform) else "adas"
        return reverse("cars:technology-list") + f"#{prefix}-{item.slug}"

    def _articles(self, parsed):
        results = self._ranked_results(
            Article.objects.filter(status=Article.Status.PUBLISHED).select_related("category"),
            vector=_vector(("title", "A"), ("summary", "B"), ("body", "C")),
            parsed=parsed,
            trigram_expressions=("title",),
            factory=lambda item: (
                self._draft_result(
                    result_type="Article",
                    title=item.title,
                    description=_snippet(item.summary or item.body, "Статья базы знаний"),
                    object_id=item.pk,
                    source=f"knowledge.Article:{item.pk}",
                    url=reverse("knowledge:article-detail", args=[item.slug]),
                ),
                " ".join((item.title, item.summary, item.body)),
            ),
        )
        return self._finish(results)

    def _cars(self, parsed):
        results = []
        results += self._ranked_results(
            Manufacturer.objects.filter(is_active=True),
            vector=_vector(("name", "A"), ("description", "C")),
            parsed=parsed,
            trigram_expressions=("name",),
            factory=lambda item: (
                self._draft_result(
                    result_type="Manufacturer",
                    title=item.name,
                    description=_snippet(item.description, "Производитель автомобилей"),
                    object_id=item.pk,
                    source=f"cars.Manufacturer:{item.pk}",
                    url=reverse("cars:brand-list") + f"?manufacturer={item.pk}",
                ),
                f"{item.name} {item.description}",
            ),
        )
        results += self._ranked_results(
            Brand.objects.filter(is_active=True).select_related("manufacturer"),
            vector=_vector(("name", "A"), ("description", "C")),
            parsed=parsed,
            trigram_expressions=("name",),
            factory=lambda item: (
                self._draft_result(
                    result_type="Brand",
                    title=item.name,
                    description=_snippet(item.description, f"Марка производителя {item.manufacturer.name}"),
                    object_id=item.pk,
                    source=f"cars.Brand:{item.pk}",
                    url=reverse("cars:brand-detail", args=[item.slug]),
                ),
                f"{item.name} {item.manufacturer.name} {item.description}",
            ),
        )
        model_title = Concat("brand__name", Value(" "), "name")
        results += self._ranked_results(
            VehicleModel.objects.filter(is_active=True).select_related("brand", "brand__manufacturer"),
            vector=_vector(
                ("name", "A"),
                ("description", "C"),
            ),
            parsed=parsed,
            trigram_expressions=(model_title, "name", "brand__name"),
            factory=lambda item: (
                self._draft_result(
                    result_type="Model",
                    title=f"{item.brand.name} {item.name}",
                    description=_snippet(item.description, "Модель автомобиля"),
                    object_id=item.pk,
                    source=f"cars.Model:{item.pk}",
                    url=reverse("cars:model-detail", args=[item.slug]),
                ),
                f"{item.brand.name} {item.name} {item.brand.manufacturer.name} {item.description}",
            ),
        )
        results += self._ranked_results(
            Generation.objects.filter(is_active=True).select_related("model", "model__brand", "platform"),
            vector=_vector(
                ("name", "A"),
                ("code", "A"),
                ("description", "C"),
            ),
            parsed=parsed,
            trigram_expressions=("name", "code", "model__name", "model__brand__name"),
            factory=lambda item: (
                self._draft_result(
                    result_type="Generation",
                    title=f"{item.model} — {item.name}",
                    description=_snippet(item.description, f"Поколение с {item.start_year} года"),
                    object_id=item.pk,
                    source=f"cars.Generation:{item.pk}",
                    url=reverse("cars:model-detail", args=[item.model.slug]) + f"#generation-{item.pk}",
                ),
                f"{item.model} {item.name} {item.code} {item.platform.name} {item.description}",
            ),
        )
        results += self._ranked_results(
            Modification.objects.filter(is_active=True).select_related(
                "generation__model__brand", "powertrain__battery"
            ),
            vector=_vector(
                ("name", "A"),
                ("source_note", "C"),
            ),
            parsed=parsed,
            trigram_expressions=("name", "generation__model__name", "generation__model__brand__name"),
            factory=lambda item: (
                self._draft_result(
                    result_type="Modification",
                    title=f"{item.generation.model} {item.name}",
                    description=_snippet(
                        item.source_note,
                        f"{item.powertrain.type}; запас хода {item.range_km or 'не указан'} км",
                    ),
                    object_id=item.pk,
                    source=f"cars.Modification:{item.pk}",
                    url=reverse("cars:modification-detail", args=[item.slug]),
                ),
                f"{item.generation.model} {item.name} {item.powertrain.type} "
                f"{item.powertrain.battery or ''} {item.source_note}",
            ),
        )
        return self._finish(results)

    def _technologies(self, parsed):
        results = []
        for model, kind in (
            (Technology, "Technology"),
            (Platform, "Platform"),
            (DriverAssistanceSystem, "Driver assistance system"),
        ):
            queryset = model.objects.filter(is_active=True)
            fields = [("name", "A"), ("description", "C")]
            if hasattr(model, "category"):
                fields.insert(1, ("category", "B"))
            results += self._ranked_results(
                queryset,
                vector=_vector(*fields),
                parsed=parsed,
                trigram_expressions=("name",),
                factory=lambda item, kind=kind: (
                    self._draft_result(
                        result_type=kind,
                        title=item.name,
                        description=_snippet(item.description, kind),
                        object_id=item.pk,
                        source=f"{item._meta.label}:{item.pk}",
                        url=self._technology_url(item),
                    ),
                    f"{item.name} {getattr(item, 'category', '')} {item.description}",
                ),
            )
        return self._finish(results)

    def _videos(self, parsed):
        results = self._ranked_results(
            VideoResource.objects.filter(is_active=True),
            vector=_vector(("title", "A"), ("description", "B"), ("provider", "D")),
            parsed=parsed,
            trigram_expressions=("title",),
            factory=lambda item: (
                SearchResult(
                    result_type="Video",
                    title=item.title,
                    description=_snippet(item.description, f"Видео от {item.provider}"),
                    url=item.url,
                    score=0.0,
                    object_id=item.pk,
                    source=f"knowledge.VideoResource:{item.pk}",
                ),
                f"{item.title} {item.description} {item.provider}",
            ),
        )
        return self._finish(results)

    def _finish(self, results):
        deduplicated = {}
        for result in results:
            current = deduplicated.get(result.source)
            if current is None or result.score > current.score:
                deduplicated[result.source] = result
        return sorted(deduplicated.values(), key=lambda item: (-item.score, item.title.casefold()))[
            : self.group_limit
        ]
