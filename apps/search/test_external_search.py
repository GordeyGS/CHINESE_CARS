import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.knowledge.models import Article

from .services import (
    BraveSearchProvider,
    ExternalSearchError,
    ExternalSearchProvider,
    ExternalSearchRateLimit,
    ExternalSearchResponseError,
    ExternalSearchResult,
    ExternalSearchStatus,
    ExternalSearchTimeout,
    NullExternalSearchProvider,
    SearchCoordinator,
    TavilyExternalSearchProvider,
    get_external_search_provider,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module", autouse=True)
def demo_external_search_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("load_demo_data", verbosity=0)


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, size):
        return self.body[:size]


class FakeProvider(ExternalSearchProvider):
    name = "Fake"

    def __init__(self, *, results=(), error=None):
        self.results = list(results)
        self.error = error
        self.received_query = None

    def search(self, query, *, limit, language):
        self.received_query = query
        if self.error:
            raise self.error
        return self.results[:limit]


def external_result(**overrides):
    values = {
        "title": "BYD — официальный сайт",
        "url": "https://www.bydglobal.com/",
        "description": "Официальная информация о моделях BYD.",
        "source": "bydglobal.com",
    }
    values.update(overrides)
    return ExternalSearchResult(**values)


def test_brave_response_is_converted_to_external_dto():
    payload = {
        "web": {
            "results": [
                {
                    "title": "BYD Global",
                    "url": "https://www.bydglobal.com/en/",
                    "description": "Electric cars and battery technologies.",
                    "profile": {"long_name": "bydglobal.com"},
                },
                {"title": "Unsafe", "url": "javascript:alert(1)", "description": "Ignored"},
            ]
        }
    }
    provider = BraveSearchProvider(
        api_key="test-key",
        endpoint="https://api.search.brave.com/res/v1/web/search",
        timeout=1,
        opener=lambda request, timeout: FakeResponse(payload),
    )
    assert provider.search("BYD", limit=5, language="ru") == [
        ExternalSearchResult(
            title="BYD Global",
            url="https://www.bydglobal.com/en/",
            description="Electric cars and battery technologies.",
            source="bydglobal.com",
        )
    ]


def test_brave_request_uses_original_query_and_configuration():
    captured = {}

    def opener(request, timeout):
        captured.update(request=request, timeout=timeout)
        return FakeResponse({"web": {"results": []}})

    provider = BraveSearchProvider(
        api_key="secret-test-key",
        endpoint="https://api.search.brave.com/res/v1/web/search",
        timeout=2.5,
        opener=opener,
    )
    provider.search("Какие электромобили BYD?", limit=4, language="ru")
    query = parse_qs(urlsplit(captured["request"].full_url).query)
    assert query == {"q": ["Какие электромобили BYD?"], "count": ["4"], "search_lang": ["ru"]}
    assert captured["request"].get_header("X-subscription-token") == "secret-test-key"
    assert captured["timeout"] == 2.5


@override_settings(
    EXTERNAL_SEARCH_PROVIDER="tavily",
    EXTERNAL_SEARCH_API_KEY="test-key",
    EXTERNAL_SEARCH_ENDPOINT="https://api.tavily.com/search",
)
def test_tavily_provider_is_selected_from_configuration():
    assert isinstance(get_external_search_provider(), TavilyExternalSearchProvider)


def test_tavily_response_is_converted_to_external_dto():
    payload = {
        "results": [
            {
                "title": "BYD Global",
                "url": "https://www.bydglobal.com/en/",
                "content": "Official information about BYD electric vehicles.",
                "score": 0.91,
            },
            {"title": "Unsafe", "url": "data:text/html,bad", "content": "Ignored"},
        ]
    }
    provider = TavilyExternalSearchProvider(
        api_key="test-key",
        endpoint="https://api.tavily.com/search",
        timeout=1,
        opener=lambda request, timeout: FakeResponse(payload),
    )
    assert provider.search("BYD", limit=5, language="ru") == [
        ExternalSearchResult(
            title="BYD Global",
            url="https://www.bydglobal.com/en/",
            description="Official information about BYD electric vehicles.",
            source="www.bydglobal.com",
        )
    ]


def test_tavily_request_uses_post_json_and_bearer_header():
    captured = {}

    def opener(request, timeout):
        captured.update(request=request, timeout=timeout)
        return FakeResponse({"results": []})

    provider = TavilyExternalSearchProvider(
        api_key="secret-test-key",
        endpoint="https://api.tavily.com/search",
        timeout=2,
        opener=opener,
    )
    provider.search("Какие электромобили BYD?", limit=3, language="ru")
    body = json.loads(captured["request"].data.decode())
    assert captured["request"].method == "POST"
    assert captured["request"].get_header("Authorization") == "Bearer secret-test-key"
    assert body["query"] == "Какие электромобили BYD?"
    assert body["max_results"] == 3
    assert body["search_depth"] == "basic"
    assert body["include_answer"] is False


@override_settings(EXTERNAL_SEARCH_PROVIDER="brave", EXTERNAL_SEARCH_API_KEY="")
def test_missing_api_key_selects_null_provider():
    assert isinstance(get_external_search_provider(), NullExternalSearchProvider)


@override_settings(EXTERNAL_SEARCH_PROVIDER="tavily", EXTERNAL_SEARCH_API_KEY="")
def test_missing_tavily_api_key_selects_null_provider():
    assert isinstance(get_external_search_provider(), NullExternalSearchProvider)


def test_timeout_does_not_remove_internal_results():
    provider = FakeProvider(error=ExternalSearchTimeout("timeout"))
    response = SearchCoordinator(external_provider=provider).search("BYD")
    assert response.external.status is ExternalSearchStatus.ERROR
    assert response.internal.groups["Articles"]
    assert response.internal.groups["Cars"]


def test_tavily_timeout_does_not_remove_internal_results():
    provider = TavilyExternalSearchProvider(
        api_key="test",
        endpoint="https://api.tavily.com/search",
        timeout=1,
        opener=lambda request, timeout: (_ for _ in ()).throw(URLError(socket.timeout())),
    )
    response = SearchCoordinator(external_provider=provider).search("BYD")
    assert response.external.status is ExternalSearchStatus.ERROR
    assert response.internal.groups["Articles"]
    assert response.internal.groups["Cars"]


def test_provider_error_does_not_raise_500(client, monkeypatch):
    provider = FakeProvider(error=ExternalSearchError("provider unavailable"))
    monkeypatch.setattr("apps.search.services.coordinator.get_external_search_provider", lambda: provider)
    response = client.get(reverse("search:index"), {"q": "BYD"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Внешний поиск временно недоступен" in content
    assert "Автомобили" in content


def test_tavily_http_error_does_not_raise_500(client, monkeypatch):
    provider = TavilyExternalSearchProvider(
        api_key="test",
        endpoint="https://api.tavily.com/search",
        timeout=1,
        opener=lambda request, timeout: (_ for _ in ()).throw(
            HTTPError(request.full_url, 500, "Server Error", {}, None)
        ),
    )
    monkeypatch.setattr("apps.search.services.coordinator.get_external_search_provider", lambda: provider)
    response = client.get(reverse("search:index"), {"q": "BYD"})
    assert response.status_code == 200
    assert "Внешний поиск временно недоступен" in response.content.decode()


def test_external_results_are_displayed_and_escaped(client, monkeypatch):
    provider = FakeProvider(results=[external_result(title="<script>BYD</script>")])
    monkeypatch.setattr("apps.search.services.coordinator.get_external_search_provider", lambda: provider)
    response = client.get(reverse("search:index"), {"q": "BYD"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Результаты из Интернета" in content
    assert "bydglobal.com" in content
    assert "Официальная информация" in content
    assert "&lt;script&gt;BYD&lt;/script&gt;" in content
    assert "<script>BYD</script>" not in content


def test_empty_external_results_are_allowed():
    response = SearchCoordinator(external_provider=FakeProvider()).search("BYD")
    assert response.external.status is ExternalSearchStatus.SUCCESS
    assert response.external.results == ()
    assert response.internal.total > 0


def test_original_query_is_forwarded_to_external_provider():
    provider = FakeProvider()
    SearchCoordinator(external_provider=provider).search("  BYD  ")
    assert provider.received_query == "  BYD  "


def test_external_result_is_not_persisted():
    before = Article.objects.count()
    response = SearchCoordinator(external_provider=FakeProvider(results=[external_result()])).search("BYD")
    assert response.external.results
    assert Article.objects.count() == before
    assert not hasattr(response.external.results[0], "save")


def test_brave_provider_maps_timeout_and_rate_limit():
    timeout_provider = BraveSearchProvider(
        api_key="test",
        endpoint="https://api.search.brave.com/res/v1/web/search",
        timeout=1,
        opener=lambda request, timeout: (_ for _ in ()).throw(URLError(socket.timeout())),
    )
    with pytest.raises(ExternalSearchTimeout):
        timeout_provider.search("BYD", limit=1, language="ru")

    rate_limit_provider = BraveSearchProvider(
        api_key="test",
        endpoint="https://api.search.brave.com/res/v1/web/search",
        timeout=1,
        opener=lambda request, timeout: (_ for _ in ()).throw(
            HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
        ),
    )
    with pytest.raises(ExternalSearchRateLimit):
        rate_limit_provider.search("BYD", limit=1, language="ru")


def test_invalid_json_and_shape_are_rejected():
    class InvalidResponse(FakeResponse):
        def __init__(self):
            self.body = b"not-json"

    provider = BraveSearchProvider(
        api_key="test",
        endpoint="https://api.search.brave.com/res/v1/web/search",
        timeout=1,
        opener=lambda request, timeout: InvalidResponse(),
    )
    with pytest.raises(ExternalSearchResponseError):
        provider.search("BYD", limit=1, language="ru")
