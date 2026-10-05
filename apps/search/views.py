from django.conf import settings
from django.shortcuts import render

from .services import ExternalSearchStatus, QueryValidationError, SearchCoordinator


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
    }
    if "q" in request.GET:
        try:
            response = SearchCoordinator().search(raw_query)
        except QueryValidationError as error:
            context["error"] = str(error)
        else:
            internal = response.internal
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
                }
            )
    return render(request, "search/index.html", context)
