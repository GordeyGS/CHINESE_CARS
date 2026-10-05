from functools import reduce
from operator import or_

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import F, FloatField, Q, Value
from django.db.models.functions import Coalesce, Greatest

from .query_parser import ParsedQuery


PHRASE_RANK_WEIGHT = 0.70
TRIGRAM_WEIGHT = 0.25
EXACT_TITLE_BONUS = 1.00
LITERAL_PHRASE_BONUS = 0.40
MULTI_TERM_COVERAGE_WEIGHT = 0.35


def _greatest(expressions):
    expressions = list(expressions)
    if not expressions:
        return Value(0.0, output_field=FloatField())
    if len(expressions) == 1:
        return Coalesce(expressions[0], Value(0.0), output_field=FloatField())
    return Greatest(*expressions, output_field=FloatField())


def annotate_ranked(queryset, *, vector, parsed: ParsedQuery, trigram_expressions):
    config = getattr(settings, "SEARCH_FTS_CONFIG", "russian")
    term_queries = [SearchQuery(term, config=config, search_type="plain") for term in parsed.terms]
    any_term_query = reduce(or_, term_queries)
    combined_query = SearchQuery(parsed.search_text, config=config, search_type="plain")

    queryset = queryset.annotate(_search_vector=vector)
    any_term_rank = SearchRank(F("_search_vector"), any_term_query, cover_density=True)
    coverage_rank = SearchRank(F("_search_vector"), combined_query, cover_density=True)
    phrase_rank = _greatest(
        SearchRank(
            F("_search_vector"),
            SearchQuery(phrase, config=config, search_type="phrase"),
            cover_density=True,
        )
        for phrase in parsed.phrase_candidates
    )

    trigram_candidates = parsed.phrase_candidates or (parsed.normalized,)
    trigram_fields = [expression for expression in trigram_expressions if isinstance(expression, str)]
    trigram_filter = Q()
    for field_name in trigram_fields:
        for candidate in trigram_candidates:
            trigram_filter |= Q(**{f"{field_name}__trigram_similar": candidate})
    trigram_rank = _greatest(
        TrigramSimilarity(expression, candidate)
        for expression in trigram_expressions
        for candidate in trigram_candidates
    )
    queryset = queryset.annotate(
        full_text_rank=Coalesce(
            any_term_rank + coverage_rank * Value(MULTI_TERM_COVERAGE_WEIGHT),
            Value(0.0),
            output_field=FloatField(),
        ),
        phrase_rank=phrase_rank,
        trigram_similarity=trigram_rank,
    )
    # The @@ predicate lets PostgreSQL use the matching GIN expression index;
    # SearchRank is kept for ordering rather than used as the only filter.
    return queryset.filter(Q(_search_vector=any_term_query) | trigram_filter)


def calculate_score(item, parsed: ParsedQuery, title: str, searchable_text: str) -> float:
    folded_title = title.casefold()
    exact_title = folded_title == parsed.normalized.casefold()
    phrase_literal = any(phrase.casefold() in searchable_text.casefold() for phrase in parsed.phrase_candidates)
    score = (
        float(item.full_text_rank or 0.0)
        + PHRASE_RANK_WEIGHT * float(item.phrase_rank or 0.0)
        + TRIGRAM_WEIGHT * float(item.trigram_similarity or 0.0)
        + EXACT_TITLE_BONUS * exact_title
        + LITERAL_PHRASE_BONUS * phrase_literal
    )
    return round(score, 6)
