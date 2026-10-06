from dataclasses import asdict, dataclass

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Value
from django.db.models.functions import Concat

from apps.cars.models import Brand, Model as VehicleModel, Technology
from apps.knowledge.models import Article


MIN_SUGGESTION_LENGTH = 2
MAX_SUGGESTION_QUERY_LENGTH = 100
SUGGESTION_LIMIT = 7
WEAK_RESULT_SCORE = 0.08
FUZZY_SIMILARITY_THRESHOLD = 0.24

POPULAR_QUERIES = (
    "BYD",
    "Blade Battery",
    "Zeekr 001",
    "электромобиль",
    "Какие электромобили BYD используют Blade Battery?",
)


@dataclass(frozen=True)
class SearchSuggestion:
    label: str
    type: str
    value: str

    def as_dict(self):
        return asdict(self)


class SearchAssistanceService:
    def __init__(self, *, limit=SUGGESTION_LIMIT):
        self.limit = min(max(limit, 1), SUGGESTION_LIMIT)

    def autocomplete(self, raw_query):
        query = " ".join((raw_query or "").split())
        if len(query) < MIN_SUGGESTION_LENGTH or len(query) > MAX_SUGGESTION_QUERY_LENGTH:
            return []

        suggestions = []
        sources = (
            (
                Brand.objects.filter(is_active=True, name__istartswith=query).values_list("name", flat=True),
                "brand",
            ),
            (
                VehicleModel.objects.filter(is_active=True)
                .annotate(label=Concat("brand__name", Value(" "), "name"))
                .filter(label__istartswith=query)
                .values_list("label", flat=True),
                "model",
            ),
            (
                Technology.objects.filter(is_active=True, name__istartswith=query).values_list("name", flat=True),
                "technology",
            ),
            (
                Article.objects.filter(status=Article.Status.PUBLISHED, title__istartswith=query).values_list(
                    "title", flat=True
                ),
                "article",
            ),
        )
        seen = set()
        for queryset, suggestion_type in sources:
            for label in queryset.order_by()[: self.limit]:
                key = label.casefold()
                if key not in seen:
                    suggestions.append(SearchSuggestion(label, suggestion_type, label))
                    seen.add(key)
        suggestions.sort(key=lambda item: (len(item.label), item.label.casefold()))
        return suggestions[: self.limit]

    def fuzzy(self, raw_query, *, limit=3):
        query = " ".join((raw_query or "").split())
        if len(query) < MIN_SUGGESTION_LENGTH or len(query) > MAX_SUGGESTION_QUERY_LENGTH:
            return []

        candidates = []
        sources = (
            (
                Brand.objects.filter(is_active=True)
                .annotate(similarity=TrigramSimilarity("name", query))
                .filter(similarity__gte=FUZZY_SIMILARITY_THRESHOLD)
                .values_list("name", "similarity"),
                "brand",
            ),
            (
                VehicleModel.objects.filter(is_active=True)
                .annotate(
                    label=Concat("brand__name", Value(" "), "name"),
                    similarity=TrigramSimilarity(Concat("brand__name", Value(" "), "name"), query),
                )
                .filter(similarity__gte=FUZZY_SIMILARITY_THRESHOLD)
                .values_list("label", "similarity"),
                "model",
            ),
            (
                Technology.objects.filter(is_active=True)
                .annotate(similarity=TrigramSimilarity("name", query))
                .filter(similarity__gte=FUZZY_SIMILARITY_THRESHOLD)
                .values_list("name", "similarity"),
                "technology",
            ),
            (
                Article.objects.filter(status=Article.Status.PUBLISHED)
                .annotate(similarity=TrigramSimilarity("title", query))
                .filter(similarity__gte=FUZZY_SIMILARITY_THRESHOLD)
                .values_list("title", "similarity"),
                "article",
            ),
        )
        for queryset, suggestion_type in sources:
            for label, similarity in queryset.order_by("-similarity")[:limit]:
                if label.casefold() != query.casefold():
                    candidates.append((float(similarity), SearchSuggestion(label, suggestion_type, label)))

        unique = {}
        for similarity, suggestion in sorted(candidates, key=lambda item: (-item[0], item[1].label.casefold())):
            unique.setdefault(suggestion.label.casefold(), suggestion)
        return list(unique.values())[:limit]

    @staticmethod
    def has_exact_term(raw_query):
        query = " ".join((raw_query or "").split())
        if len(query) < MIN_SUGGESTION_LENGTH or len(query) > MAX_SUGGESTION_QUERY_LENGTH:
            return False
        return (
            Brand.objects.filter(is_active=True, name__iexact=query).exists()
            or Technology.objects.filter(is_active=True, name__iexact=query).exists()
            or Article.objects.filter(status=Article.Status.PUBLISHED, title__iexact=query).exists()
            or VehicleModel.objects.filter(is_active=True)
            .annotate(label=Concat("brand__name", Value(" "), "name"))
            .filter(label__iexact=query)
            .exists()
        )

    @staticmethod
    def is_weak(search_response):
        scores = [result.score for results in search_response.groups.values() for result in results]
        return not scores or max(scores) < WEAK_RESULT_SCORE
