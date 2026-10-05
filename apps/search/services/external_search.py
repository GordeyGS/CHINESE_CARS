import json
import logging
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class ExternalSearchResult:
    title: str
    url: str
    description: str
    source: str
    published_at: datetime | None = None


class ExternalSearchStatus(StrEnum):
    SUCCESS = "success"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass(frozen=True)
class ExternalSearchOutcome:
    results: tuple[ExternalSearchResult, ...]
    status: ExternalSearchStatus


class ExternalSearchError(RuntimeError):
    """A safe, provider-independent external search failure."""


class ExternalSearchTimeout(ExternalSearchError):
    pass


class ExternalSearchRateLimit(ExternalSearchError):
    pass


class ExternalSearchResponseError(ExternalSearchError):
    pass


class ExternalSearchProvider(ABC):
    name = "external"
    is_configured = True

    @abstractmethod
    def search(self, query: str, *, limit: int, language: str) -> list[ExternalSearchResult]:
        raise NotImplementedError


class NullExternalSearchProvider(ExternalSearchProvider):
    name = "none"
    is_configured = False

    def search(self, query: str, *, limit: int, language: str) -> list[ExternalSearchResult]:
        return []


class BraveSearchProvider(ExternalSearchProvider):
    name = "Brave Search"

    def __init__(self, *, api_key: str, endpoint: str, timeout: float, opener=urlopen):
        if not api_key:
            raise ValueError("Brave Search API key is required.")
        if not _is_https_endpoint(endpoint):
            raise ValueError("External search endpoint must be an HTTPS URL.")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.opener = opener

    def search(self, query: str, *, limit: int, language: str) -> list[ExternalSearchResult]:
        request_url = f"{self.endpoint}?{urlencode({'q': query, 'count': limit, 'search_lang': language})}"
        request = Request(
            request_url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "china-auto-kb-course-project/1.0",
            },
        )
        payload = _request_json(request, opener=self.opener, timeout=self.timeout, rate_limit_statuses={429})
        return self._parse_results(payload, limit=limit)

    @staticmethod
    def _parse_results(payload, *, limit: int) -> list[ExternalSearchResult]:
        if not isinstance(payload, dict):
            raise ExternalSearchResponseError("External search response must be an object.")
        web = payload.get("web", {})
        raw_results = web.get("results", []) if isinstance(web, dict) else None
        if not isinstance(raw_results, list):
            raise ExternalSearchResponseError("External search results have an invalid format.")

        results = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            description = item.get("description", "")
            if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
                continue
            if not _is_safe_result_url(url):
                continue
            profile = item.get("profile")
            profile_source = profile.get("long_name") if isinstance(profile, dict) else None
            source = profile_source if isinstance(profile_source, str) and profile_source.strip() else urlsplit(url).hostname
            results.append(
                ExternalSearchResult(
                    title=title.strip(),
                    url=url,
                    description=description.strip() if isinstance(description, str) else "",
                    source=source or "Источник в Интернете",
                )
            )
            if len(results) >= limit:
                break
        return results


class TavilyExternalSearchProvider(ExternalSearchProvider):
    name = "Tavily Search"

    def __init__(self, *, api_key: str, endpoint: str, timeout: float, opener=urlopen):
        if not api_key:
            raise ValueError("Tavily API key is required.")
        if not _is_https_endpoint(endpoint):
            raise ValueError("External search endpoint must be an HTTPS URL.")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.opener = opener

    def search(self, query: str, *, limit: int, language: str) -> list[ExternalSearchResult]:
        body = json.dumps(
            {
                "query": query,
                "search_depth": "basic",
                "max_results": limit,
                "topic": "general",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "language": language,
                "safe_search": True,
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "china-auto-kb-course-project/1.0",
            },
        )
        payload = _request_json(
            request,
            opener=self.opener,
            timeout=self.timeout,
            rate_limit_statuses={429, 432, 433},
        )
        return self._parse_results(payload, limit=limit)

    @staticmethod
    def _parse_results(payload, *, limit: int) -> list[ExternalSearchResult]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results", []), list):
            raise ExternalSearchResponseError("External search results have an invalid format.")
        results = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            content = item.get("content", "")
            if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
                continue
            if not _is_safe_result_url(url):
                continue
            results.append(
                ExternalSearchResult(
                    title=title.strip(),
                    url=url,
                    description=content.strip() if isinstance(content, str) else "",
                    source=urlsplit(url).hostname or "Источник в Интернете",
                )
            )
            if len(results) >= limit:
                break
        return results


def get_external_search_provider() -> ExternalSearchProvider:
    provider_name = settings.EXTERNAL_SEARCH_PROVIDER.strip().casefold()
    if provider_name in {"", "none", "null"}:
        return NullExternalSearchProvider()
    if provider_name == "brave":
        if not settings.EXTERNAL_SEARCH_API_KEY:
            return NullExternalSearchProvider()
        try:
            return BraveSearchProvider(
                api_key=settings.EXTERNAL_SEARCH_API_KEY,
                endpoint=settings.EXTERNAL_SEARCH_ENDPOINT,
                timeout=settings.EXTERNAL_SEARCH_TIMEOUT_SECONDS,
            )
        except ValueError:
            logger.warning("External search configuration is invalid.")
            return NullExternalSearchProvider()
    if provider_name == "tavily":
        if not settings.EXTERNAL_SEARCH_API_KEY:
            return NullExternalSearchProvider()
        try:
            return TavilyExternalSearchProvider(
                api_key=settings.EXTERNAL_SEARCH_API_KEY,
                endpoint=settings.EXTERNAL_SEARCH_ENDPOINT,
                timeout=settings.EXTERNAL_SEARCH_TIMEOUT_SECONDS,
            )
        except ValueError:
            logger.warning("External search configuration is invalid.")
            return NullExternalSearchProvider()
    logger.warning("Unknown external search provider is configured.")
    return NullExternalSearchProvider()


def _is_https_endpoint(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc)


def _is_safe_result_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.netloc) and not parts.username and not parts.password


def _request_json(request, *, opener, timeout: float, rate_limit_statuses: set[int]):
    try:
        with opener(request, timeout=timeout) as response:
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        if error.code in rate_limit_statuses:
            raise ExternalSearchRateLimit("External search quota or rate limit reached.") from error
        raise ExternalSearchError("External search returned an HTTP error.") from error
    except (TimeoutError, socket.timeout) as error:
        raise ExternalSearchTimeout("External search timed out.") from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise ExternalSearchTimeout("External search timed out.") from error
        raise ExternalSearchError("External search connection failed.") from error
    except (HTTPException, OSError) as error:
        raise ExternalSearchError("External search connection failed.") from error

    if len(raw_body) > MAX_RESPONSE_BYTES:
        raise ExternalSearchResponseError("External search response is too large.")
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalSearchResponseError("External search returned invalid JSON.") from error
