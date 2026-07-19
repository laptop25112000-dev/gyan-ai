# GYAAAN

GYAAAN is a small demo of a multi-model assistant with optional web search.

The important idea is orchestration:

1. The router checks whether the question needs fresh web information.
2. The web-search layer collects sources when needed.
3. Different model roles handle reasoning, summarizing, source checking, and coding.
4. The final mixer, `abcdefg`, combines those outputs into one answer.

This repo runs in offline demo mode by default, so it does not need API keys. The code is structured so real search/model APIs can be plugged into `gyaan/web_search.py` and `gyaan/models.py`.

## Run

```bash
python3 app.py "What is the latest news about AI models?" --trace
```

Example without web search:

```bash
python3 app.py "Explain binary search in simple words" --trace
```

Example with the coding role:

```bash
python3 app.py "Write Python code for a simple calculator" --trace
```

## File Uploads

The web chat UI supports attaching files with the paperclip button. Text-like files
such as `.txt`, `.csv`, `.json`, `.md`, `.html`, and source code are extracted into
model context. Archives such as `.zip` and `.docx` get a contents/text preview.
Images, audio, video, PDFs, and other binary files are accepted with metadata, but
this Groq text pipeline cannot inspect their pixels, frames, audio, or PDF layout
without adding a dedicated parser or vision/transcription provider.

Limits: up to 8 files per request, 8 MB per file.

## Free Web Search

For more reliable live search than HTML scraping, create a free Tavily API key and
add it to `.env`:

```env
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=tvly_your_tavily_api_key_here
```

When `TAVILY_API_KEY` is present, GYAAAN uses Tavily first. If Tavily is not
configured or fails, the app falls back to the built-in Google, Bing, and
DuckDuckGo scraping paths.

## Project Structure

```text
gyaan/
├─ app.py
├─ gyaan/
│  ├─ config.py       # environment-backed settings
│  ├─ router.py       # decides web/no-web and model roles
│  ├─ web_search.py   # search interface + offline demo client
│  ├─ models.py       # model interface + demo specialist roles
│  ├─ mixer.py        # abcdefg final mixing layer
│  ├─ pipeline.py     # end-to-end orchestration
│  └─ providers/      # placeholders for real API adapters
├─ prompts/           # editable prompt files
├─ config/            # default project config
├─ examples/          # sample user questions
├─ tests/             # unit tests
├─ scripts/           # local run/check helpers
├─ docs/              # architecture and roadmap
├─ .env.example
├─ requirements.txt
└─ README.md
```

## What To Show In Code

- `gyaan/router.py`: proves the app routes fresh/current questions to search.
- `gyaan/models.py`: shows different model roles.
- `gyaan/mixer.py`: shows `abcdefg`, the final model-mixing layer.
- `gyaan/pipeline.py`: shows the full flow from question to final answer.

## Production Upgrade Points

Replace:

- `DemoWebSearchClient` with a real provider such as Tavily, SerpAPI, Brave Search, or Bing.
- `DemoModelClient` with real model calls such as OpenAI, Gemini, Claude, or a local model.

Keep the same pipeline shape so the architecture stays understandable.
