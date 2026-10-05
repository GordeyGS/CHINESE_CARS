import logging
from dataclasses import dataclass

from django.conf import settings

from .external_search import (
    ExternalSearchError,
    ExternalSearchOutcome,
    ExternalSearchProvider,
    ExternalSearchStatus,
    get_external_search_provider,
)
from .internal_search import InternalSearchService, SearchResponse


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchPageResponse:
    internal: SearchResponse
    external: ExternalSearchOutcome

    @property
    def total(self) -> int:
        return self.internal.total + len(self.external.results)


class SearchCoordinator:
    def __init__(
        self,
        *,
        internal_service: InternalSearchService | None = None,
        external_provider: ExternalSearchProvider | None = None,
    ):
        self.internal_service = internal_service or InternalSearchService()
        self.external_provider = external_provider or get_external_search_provider()

    def search(self, raw_query: str) -> SearchPageResponse:
        internal = self.internal_service.search(raw_query)
        if not self.external_provider.is_configured:
            external = ExternalSearchOutcome((), ExternalSearchStatus.NOT_CONFIGURED)
        else:
            try:
                results = self.external_provider.search(
                    internal.query.original,
                    limit=settings.EXTERNAL_SEARCH_LIMIT,
                    language=settings.EXTERNAL_SEARCH_LANGUAGE,
                )
            except ExternalSearchError as error:
                logger.warning("External search failed: %s", type(error).__name__)
                external = ExternalSearchOutcome((), ExternalSearchStatus.ERROR)
            except Exception:
                logger.exception("Unexpected external search provider failure.")
                external = ExternalSearchOutcome((), ExternalSearchStatus.ERROR)
            else:
                external = ExternalSearchOutcome(tuple(results), ExternalSearchStatus.SUCCESS)
        return SearchPageResponse(internal=internal, external=external)
