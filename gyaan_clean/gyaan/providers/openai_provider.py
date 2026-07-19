from gyaan.models import ModelClient, ModelResponse
from gyaan.web_search import SearchResult


class OpenAIModelClient(ModelClient):
    """Placeholder adapter showing where a real OpenAI client would go."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def complete(
        self,
        *,
        model_name: str,
        role: str,
        question: str,
        search_results: list[SearchResult],
    ) -> ModelResponse:
        raise NotImplementedError(
            "Connect the official OpenAI SDK here when API keys are available."
        )
