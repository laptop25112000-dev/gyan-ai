from dataclasses import dataclass

from .prompts import ROLE_PROMPTS
from .web_search import SearchResult


@dataclass(frozen=True)
class ModelResponse:
    model_name: str
    role: str
    content: str


class ModelClient:
    """Interface for model providers such as OpenAI, Claude, Gemini, or local LLMs."""

    def complete(
        self,
        *,
        model_name: str,
        role: str,
        question: str,
        search_results: list[SearchResult],
    ) -> ModelResponse:
        raise NotImplementedError


class DemoModelClient(ModelClient):
    """Deterministic model simulator that makes the orchestration easy to inspect."""

    def complete(
        self,
        *,
        model_name: str,
        role: str,
        question: str,
        search_results: list[SearchResult],
    ) -> ModelResponse:
        role_prompt = ROLE_PROMPTS.get(role, "General assistant role.")
        source_count = len(search_results)
        if role == "reasoner":
            content = (
                f"{role_prompt} "
                "Break the problem into intent, constraints, and answer. "
                f"The user asked: {question!r}. "
                f"Search context available: {source_count} sources."
            )
        elif role == "summarizer":
            content = (
                f"{role_prompt} "
                "Compress the useful facts into a short answer and remove repetition. "
                "Prefer clear wording over long explanation."
            )
        elif role == "source_checker":
            titles = ", ".join(result.title for result in search_results) or "none"
            content = (
                f"{role_prompt} "
                "Check that claims supported by web context mention sources. "
                f"Available source titles: {titles}."
            )
        elif role == "coder":
            content = (
                f"{role_prompt} "
                "Look for implementation details, edge cases, and runnable commands. "
                "Keep code suggestions practical."
            )
        else:
            content = "General assistant role completed."

        return ModelResponse(model_name=model_name, role=role, content=content)


def model_name_for_role(role: str) -> str:
    """Map roles to pretend underlying models for the demo."""
    return {
        "reasoner": "logic-pro-1",
        "summarizer": "brief-gpt",
        "source_checker": "search-verifier",
        "coder": "code-specialist",
    }.get(role, "general-model")
