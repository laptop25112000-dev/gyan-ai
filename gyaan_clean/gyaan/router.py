from dataclasses import dataclass


FRESHNESS_WORDS = {
    "today",
    "latest",
    "current",
    "recent",
    "news",
    "price",
    "score",
    "weather",
    "2025",
    "2026",
}


@dataclass(frozen=True)
class RouteDecision:
    needs_web: bool
    reason: str
    model_roles: tuple[str, ...]


def route_question(question: str) -> RouteDecision:
    """Choose whether GYAAAN should search the web and which model roles to run."""
    lowered = question.lower()
    needs_web = any(word in lowered for word in FRESHNESS_WORDS)

    roles = ["reasoner", "summarizer"]
    if needs_web:
        roles.append("source_checker")
    if any(word in lowered for word in ("code", "python", "bug", "api", "error")):
        roles.append("coder")

    reason = (
        "Question may depend on fresh information, so web search is enabled."
        if needs_web
        else "Question looks answerable from model knowledge and reasoning."
    )

    return RouteDecision(
        needs_web=needs_web,
        reason=reason,
        model_roles=tuple(dict.fromkeys(roles)),
    )
