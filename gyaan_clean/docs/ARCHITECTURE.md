# Architecture

GYAAAN is built as a pipeline.

```text
User question
    |
    v
Router
    |
    +-- optional web search
    |
    v
Specialist model roles
    |
    v
abcdefg final mixer
    |
    v
Final answer
```

## Components

- `router.py`: decides if web search is needed and which model roles should run.
- `web_search.py`: defines the search interface and offline demo search.
- `models.py`: defines model-role calls and demo model outputs.
- `mixer.py`: contains `abcdefg`, the final synthesis layer.
- `pipeline.py`: connects everything end to end.

## Why This Shape

The project separates routing, search, model calls, and final mixing so each part can be replaced independently. Demo providers make the project runnable without secrets, while provider stubs show where real APIs should go.
