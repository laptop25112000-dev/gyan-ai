from dataclasses import dataclass

from .models import ModelResponse
from .prompts import MIXER_PROMPT
from .router import RouteDecision
from .web_search import SearchResult


@dataclass(frozen=True)
class MixedAnswer:
    mixer_model: str
    answer: str
    trace: str


class VivekMixer:
    """The final model-mixing layer. Public demo name: abcdefg."""

    model_name = "abcdefg"

    def mix(
        self,
        *,
        question: str,
        route: RouteDecision,
        search_results: list[SearchResult],
        model_responses: list[ModelResponse],
    ) -> MixedAnswer:
        source_lines = [
            f"- {result.title}: {result.url}" for result in search_results
        ]
        response_lines = [
            f"- {response.role} via {response.model_name}: {response.content}"
            for response in model_responses
        ]

        answer_parts = [
            f"GYAAAN answer mixed by {self.model_name}",
            "",
            f"Question: {question}",
            "",
            "Final answer:",
            self._final_text(question, route, search_results),
        ]

        if search_results:
            answer_parts.extend(["", "Sources:", *source_lines])

        trace = "\n".join(
            [
                f"Mixer prompt: {MIXER_PROMPT.splitlines()[0]}",
                f"Router: {route.reason}",
                f"Roles: {', '.join(route.model_roles)}",
                "Model outputs:",
                *response_lines,
            ]
        )

        return MixedAnswer(
            mixer_model=self.model_name,
            answer="\n".join(answer_parts),
            trace=trace,
        )

    def _final_text(
        self,
        question: str,
        route: RouteDecision,
        search_results: list[SearchResult],
    ) -> str:
        if route.needs_web:
            return (
                "This question was routed through web search first, then checked by "
                "specialist model roles before being combined. Replace the demo search "
                "client with a real search API to make the citations live."
            )

        if "code" in question.lower() or "python" in question.lower():
            return (
                "The coding role was included, so the final response should focus on "
                "working implementation details, commands, and edge cases."
            )

        return (
            "This was handled without web search. The reasoner and summarizer roles "
            "produced separate views, and abcdefg merged them into one answer."
        )
