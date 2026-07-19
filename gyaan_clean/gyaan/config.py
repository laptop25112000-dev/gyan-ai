import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mixer_model: str = "abcdefg"
    search_provider: str = "demo"
    model_provider: str = "demo"
    max_sources: int = 3
    show_debug_trace: bool = False


def load_settings() -> Settings:
    return Settings(
        mixer_model=os.getenv("GYAAN_MIXER_MODEL", "abcdefg"),
        search_provider=os.getenv("GYAAN_SEARCH_PROVIDER", "demo"),
        model_provider=os.getenv("GYAAN_MODEL_PROVIDER", "demo"),
        max_sources=int(os.getenv("GYAAN_MAX_SOURCES", "3")),
        show_debug_trace=os.getenv("GYAAN_DEBUG", "0") == "1",
    )
