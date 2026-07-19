from gyaan.web_search import SearchResult, WebSearchClient


class RealSearchClient(WebSearchClient):
    """Placeholder adapter for Tavily, Brave, SerpAPI, Bing, or another provider."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        raise NotImplementedError(
            "Connect a real search API here when a search key is available."
        )
