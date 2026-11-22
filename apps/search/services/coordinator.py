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
from .assistance import SearchAssistanceService
from .correction import QueryCorrection, QueryCorrector
from .fact_questions import FactAnswer, FactQuestionService
from .internal_search import InternalSearchService, SearchResponse


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchPageResponse:
    internal: SearchResponse
    external: ExternalSearchOutcome
    # Direct answer from structured data for questions like «самый большой запас хода».
    fact_answer: FactAnswer | None = None
    # Spelling correction of the query: shown as "Возможно, вы имели в виду" or, when
    # applied, the page shows results for the corrected query (like Google).
    correction: QueryCorrection | None = None
    correction_applied: bool = False

    @property
    def total(self) -> int:
        return self.internal.total + len(self.external.results)


class SearchCoordinator:
    def __init__(
        self,
        *,
        internal_service: InternalSearchService | None = None,
        external_provider: ExternalSearchProvider | None = None,
        fact_service: FactQuestionService | None = None,
        corrector: QueryCorrector | None = None,
    ):
        self.internal_service = internal_service or InternalSearchService()
        self.fact_service = fact_service or FactQuestionService()
        self.external_provider = external_provider or get_external_search_provider()
        self._corrector = corrector

    @property
    def corrector(self) -> QueryCorrector:
        if self._corrector is None:
            self._corrector = QueryCorrector()
        return self._corrector

    def _apply_correction(self, internal: SearchResponse, allow_correction: bool):
        """Return (internal response to show, correction, applied).

        A correction from the fixed spelling table or the keyboard layout is certain and is
        applied at once. A typo correction is applied only when the original query found
        (almost) nothing and the corrected one finds more; otherwise it is only suggested.
        """
        correction = self.corrector.correct(internal.query.original)
        if correction is None or not allow_correction:
            return internal, correction, False
        certain = all(change.reason in CERTAIN_REASONS for change in correction.changes)
        if not certain and not SearchAssistanceService.is_weak(internal):
            return internal, correction, False
        corrected = self.internal_service.search(correction.corrected)
        if not certain and _best_score(corrected) <= _best_score(internal):
            return internal, correction, False
        return corrected, correction, True

    def search(self, raw_query: str, *, allow_correction: bool = True) -> SearchPageResponse:
        internal = self.internal_service.search(raw_query)
        internal, correction, applied = self._apply_correction(internal, allow_correction)
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
        fact_answer = self.fact_service.answer(internal.query.normalized)
        return SearchPageResponse(
            internal=internal, external=external, fact_answer=fact_answer,
            correction=correction, correction_applied=applied,
        )


CERTAIN_REASONS = {"русское написание", "неверная раскладка"}


def _best_score(response: SearchResponse) -> float:
    return max((result.score for results in response.groups.values() for result in results), default=0.0)
