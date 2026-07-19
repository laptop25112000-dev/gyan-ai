from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearchClient:
    """Small interface around web search so the provider can be changed later."""

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        raise NotImplementedError


class DemoWebSearchClient(WebSearchClient):
    """Offline search client for demos without API keys or internet access."""

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        safe_query = query.strip() or "general question"
        results = [
            SearchResult(
                title="Live-source placeholder",
                url="https://example.com/search-provider",
                snippet=(
                    "In production this slot is filled by a real web-search API. "
                    f"The query sent by GYAAAN was: {safe_query!r}."
                ),
            ),
            SearchResult(
                title="Source quality check",
                url="https://example.com/source-quality",
                snippet="GYAAAN keeps source titles, URLs, and snippets for final citation.",
            ),
            SearchResult(
                title="Freshness signal",
                url="https://example.com/freshness",
                snippet="Fresh or time-sensitive questions are routed through search first.",
            ),
        ]
        return results[:limit]
