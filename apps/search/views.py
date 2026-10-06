from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from .services import (
    POPULAR_QUERIES,
    ExternalSearchStatus,
    QueryValidationError,
    SearchAssistanceService,
    SearchCoordinator,
)


GROUP_LABELS = {
    "Articles": "Статьи",
    "Cars": "Автомобили",
    "Technologies": "Технологии",
    "Videos": "Видео",
}


def search_page(request):
    raw_query = request.GET.get("q", "")
    context = {
        "query": raw_query,
        "submitted": "q" in request.GET,
        "show_scores": settings.DEBUG,
        "total": 0,
        "group_sections": [],
        "popular_queries": POPULAR_QUERIES,
    }
    if "q" in request.GET:
        try:
            response = SearchCoordinator().search(raw_query)
        except QueryValidationError as error:
            context["error"] = str(error)
        else:
            internal = response.internal
            assistance = SearchAssistanceService()
            show_similar = assistance.is_weak(internal) or not assistance.has_exact_term(raw_query)
            external_message = ""
            if response.external.status is ExternalSearchStatus.ERROR:
                external_message = "Внешний поиск временно недоступен. Внутренние результаты показаны полностью."
            elif response.external.status is ExternalSearchStatus.NOT_CONFIGURED and settings.DEBUG:
                external_message = "Внешний поиск не настроен."
            context.update(
                {
                    "query": internal.query.normalized,
                    "original_query": internal.query.original.strip(),
                    "query_type": internal.query.query_type.value,
                    "terms": internal.query.terms,
                    "total": response.total,
                    "group_sections": [
                        {
                            "key": key,
                            "label": GROUP_LABELS[key],
                            "results": internal.groups[key],
                        }
                        for key in GROUP_LABELS
                    ],
                    "external_results": response.external.results,
                    "external_message": external_message,
                    "similar_suggestions": assistance.fuzzy(raw_query) if show_similar else [],
                }
            )
    return render(request, "search/index.html", context)


def suggest(request):
    suggestions = SearchAssistanceService().autocomplete(request.GET.get("q", ""))
    return JsonResponse({"suggestions": [item.as_dict() for item in suggestions]})
