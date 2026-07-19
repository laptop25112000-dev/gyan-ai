from dataclasses import dataclass

from .config import Settings, load_settings
from .mixer import MixedAnswer, VivekMixer
from .models import DemoModelClient, ModelClient, model_name_for_role
from .router import RouteDecision, route_question
from .web_search import DemoWebSearchClient, SearchResult, WebSearchClient


@dataclass(frozen=True)
class GyaanRun:
    question: str
    route: RouteDecision
    search_results: list[SearchResult]
    final: MixedAnswer


class GyaanPipeline:
    def __init__(
        self,
        *,
        search_client: WebSearchClient | None = None,
        model_client: ModelClient | None = None,
        mixer: VivekMixer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.search_client = search_client or DemoWebSearchClient()
        self.model_client = model_client or DemoModelClient()
        self.mixer = mixer or VivekMixer()

    def ask(self, question: str) -> GyaanRun:
        route = route_question(question)
        search_results = (
            self.search_client.search(question, limit=self.settings.max_sources)
            if route.needs_web
            else []
        )

        model_responses = [
            self.model_client.complete(
                model_name=model_name_for_role(role),
                role=role,
                question=question,
                search_results=search_results,
            )
            for role in route.model_roles
        ]

        final = self.mixer.mix(
            question=question,
            route=route,
            search_results=search_results,
            model_responses=model_responses,
        )
        return GyaanRun(
            question=question,
            route=route,
            search_results=search_results,
            final=final,
        )
