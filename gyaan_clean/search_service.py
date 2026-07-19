import asyncio
import os
import platform
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, urlencode, unquote, urljoin, urlparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DEPS = os.path.join(ROOT_DIR, ".deps")
if platform.system() == "Windows" and os.path.isdir(LOCAL_DEPS) and LOCAL_DEPS not in sys.path:
    sys.path.append(LOCAL_DEPS)

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv(os.path.join(ROOT_DIR, ".env"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

REALTIME_KEYWORDS = [
    "search", "find", "look up", "current", "today", "latest", "news",
    "weather", "price", "stock", "score", "trending", "google",
    "breaking", "recent", "right now", "this week", "this month",
    "who is", "what is happening", "update", "live", "2024", "2025", "2026",
]

MAX_RESULT_PAGES = 3
MAX_PAGE_CHARS = 2200
REQUEST_TIMEOUT = 6
BROWSER_TIMEOUT_MS = 12000
TAVILY_API_URL = "https://api.tavily.com/search"


def normalize_mode(mode: str) -> str:
    value = (mode or "hybrid").strip().lower().replace("-", "_")
    aliases = {
        "auto": "hybrid",
        "search": "web_search",
        "force_search": "web_search",
        "web": "web_search",
        "direct": "no_search",
        "none": "no_search",
        "no": "no_search",
    }
    if value in {"hybrid", "web_search", "no_search"}:
        return value
    return aliases.get(value, "hybrid")


def needs_web_search(prompt: str) -> bool:
    pattern = re.compile("|".join(re.escape(word) for word in REALTIME_KEYWORDS), re.IGNORECASE)
    return bool(pattern.search(prompt or ""))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_google_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/url?"):
        url = "https://www.google.com" + url

    parsed = urlparse(url)
    if "google." in parsed.netloc and parsed.path == "/url":
        target = parse_qs(parsed.query).get("q", [""])[0]
        return unquote(target) if target else ""
    return url


def _normalize_duckduckgo_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin("https://duckduckgo.com", url)

    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else ""
    return url


def _normalize_bing_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/"):
        url = urljoin("https://www.bing.com", url)
    return url


def _allowed_result_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False

    host = urlparse(url).netloc.lower()
    blocked_hosts = (
        "google.",
        "accounts.google.",
        "support.google.",
        "policies.google.",
        "webcache.googleusercontent.",
        "bing.com",
        "microsoft.com",
    )
    return not any(blocked in host for blocked in blocked_hosts)


def _requests_google_search(query: str, num_results: int = 5) -> list:
    params = urlencode({"q": query, "num": num_results, "hl": "en"})
    response = requests.get(
        f"https://www.google.com/search?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    seen = set()

    for anchor in soup.select("a"):
        href = _normalize_google_url(anchor.get("href", ""))
        title_node = anchor.find("h3")
        title = _clean_text(title_node.get_text(" ", strip=True) if title_node else anchor.get_text(" ", strip=True))

        if not title or not _allowed_result_url(href) or href in seen:
            continue

        seen.add(href)
        results.append({"title": title, "url": href, "provider": "Google", "browser": "requests"})
        if len(results) >= num_results:
            break

    return results


def _requests_duckduckgo_search(query: str, num_results: int = 5) -> list:
    params = urlencode({"q": query})
    response = requests.get(
        f"https://html.duckduckgo.com/html/?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    seen = set()

    for result in soup.select(".result"):
        anchor = result.select_one(".result__a")
        if not anchor:
            continue

        href = _normalize_duckduckgo_url(anchor.get("href", ""))
        title = _clean_text(anchor.get_text(" ", strip=True))
        snippet_node = result.select_one(".result__snippet")
        snippet = _clean_text(snippet_node.get_text(" ", strip=True) if snippet_node else "")

        if not title or not _allowed_result_url(href) or href in seen:
            continue

        seen.add(href)
        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
            "provider": "DuckDuckGo",
            "browser": "requests",
        })
        if len(results) >= num_results:
            break

    return results


def _requests_bing_search(query: str, num_results: int = 5) -> list:
    params = urlencode({"q": query, "count": num_results, "setlang": "en"})
    response = requests.get(
        f"https://www.bing.com/search?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    seen = set()

    for item in soup.select("li.b_algo"):
        anchor = item.select_one("h2 a[href]")
        if not anchor:
            continue

        href = _normalize_bing_url(anchor.get("href", ""))
        title = _clean_text(anchor.get_text(" ", strip=True))
        snippet_node = item.select_one(".b_caption p")
        snippet = _clean_text(snippet_node.get_text(" ", strip=True) if snippet_node else "")

        if not title or not _allowed_result_url(href) or href in seen:
            continue

        seen.add(href)
        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
            "provider": "Bing",
            "browser": "requests",
        })
        if len(results) >= num_results:
            break
    return results


def _tavily_search(query: str, num_results: int = 5) -> list:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    response = requests.post(
        TAVILY_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": num_results,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    seen = set()
    for item in payload.get("results", []):
        href = item.get("url", "")
        title = _clean_text(item.get("title", ""))
        snippet = _clean_text(item.get("content", ""))

        if not title or not _allowed_result_url(href) or href in seen:
            continue

        seen.add(href)
        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
            "provider": "Tavily",
            "browser": "api",
        })
        if len(results) >= num_results:
            break

    return results


def _candidate_browser_executables() -> list:
    candidates = []
    explicit_path = os.getenv("GYAAN_BROWSER_PATH", "").strip()
    if explicit_path:
        candidates.append(("custom", explicit_path))

    if platform.system() == "Windows":
        local_app_data = os.getenv("LOCALAPPDATA", "")
        program_files = os.getenv("PROGRAMFILES", r"C:\Program Files")
        program_files_x86 = os.getenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidates.extend([
            ("edge", os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe")),
            ("edge", os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe")),
            ("chrome", os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe")),
            ("chrome", os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe")),
            ("chrome", os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe")),
            ("firefox", os.path.join(program_files, "Mozilla Firefox", "firefox.exe")),
            ("firefox", os.path.join(program_files_x86, "Mozilla Firefox", "firefox.exe")),
        ])
    else:
        candidates.extend([
            ("chrome", "/usr/bin/google-chrome"),
            ("chrome", "/usr/bin/chromium"),
            ("chrome", "/usr/bin/chromium-browser"),
            ("edge", "/usr/bin/microsoft-edge"),
            ("firefox", "/usr/bin/firefox"),
        ])

    seen = set()
    existing = []
    for name, path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            existing.append((name, path))
    return existing


async def _launch_browser(playwright):
    from playwright.async_api import Error as PlaywrightError

    errors = []
    for name, path in _candidate_browser_executables():
        browser_type = playwright.firefox if name == "firefox" else playwright.chromium
        try:
            return await browser_type.launch(
                executable_path=path,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"] if name != "firefox" else None,
            ), f"installed-{name}"
        except PlaywrightError as exc:
            errors.append(f"{name} at {path}: {exc}")

    for name, browser_type in (("chromium", playwright.chromium), ("firefox", playwright.firefox)):
        try:
            return await browser_type.launch(headless=True), f"playwright-{name}"
        except PlaywrightError as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError("No usable browser found. " + " | ".join(errors))


async def _playwright_search(query: str, num_results: int = 5, engine: str = "google") -> list:
    from playwright.async_api import async_playwright, Error as PlaywrightError

    if engine == "duckduckgo":
        url = f"https://duckduckgo.com/?{urlencode({'q': query})}"
    else:
        url = f"https://www.google.com/search?{urlencode({'q': query, 'num': num_results, 'hl': 'en'})}"

    async with async_playwright() as p:
        browser, browser_label = await _launch_browser(p)
        try:
            page = await browser.new_page(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except PlaywrightError:
                pass

            if engine == "duckduckgo":
                raw_results = await page.eval_on_selector_all(
                    "article, .react-results--main article, [data-testid='result']",
                    """
                    elements => elements.map((result) => {
                        const anchor = result.querySelector("a[href]");
                        const title = (anchor ? anchor.innerText : "").trim();
                        const snippetNode = result.querySelector("[data-result='snippet'], .result__snippet, span");
                        const snippet = (snippetNode ? snippetNode.innerText : "").trim();
                        return { title, href: anchor ? anchor.href : "", snippet };
                    }).filter((item) => item.title && item.href)
                    """,
                )
            else:
                raw_results = await page.eval_on_selector_all(
                    "a",
                    """
                    elements => elements.map((anchor) => {
                        const heading = anchor.querySelector("h3");
                        const title = (heading ? heading.innerText : "").trim();
                        const container = anchor.closest("div");
                        const snippetNode = container ? container.querySelector("span") : null;
                        const snippet = (snippetNode ? snippetNode.innerText : "").trim();
                        return { title, href: anchor.href, snippet };
                    }).filter((item) => item.title && item.href)
                    """,
                )
        finally:
            await browser.close()

    results = []
    seen = set()
    for item in raw_results:
        href = item.get("href", "")
        href = _normalize_duckduckgo_url(href) if engine == "duckduckgo" else _normalize_google_url(href)
        title = _clean_text(item.get("title", ""))
        snippet = _clean_text(item.get("snippet", ""))
        if not title or not _allowed_result_url(href) or href in seen:
            continue
        seen.add(href)
        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
            "provider": "DuckDuckGo" if engine == "duckduckgo" else "Google",
            "browser": browser_label,
        })
        if len(results) >= num_results:
            break
    return results


def _format_results(results: list) -> str:
    if not results:
        return "No useful web results found."
    lines = ["Live Web Search Results:"]
    for index, result in enumerate(results, 1):
        snippet = result.get("snippet")
        line = f"{index}. {result['title']} - {result['url']}"
        if snippet:
            line += f"\n   Summary: {snippet}"
        page_text = result.get("page_text")
        if page_text:
            line += f"\n   Page text: {page_text}"
        lines.append(line)
    return "\n".join(lines)


def _extract_page_text(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"]):
        tag.decompose()

    candidates = []
    for selector in ("article", "main", "[role='main']", ".content", "#content", "body"):
        for node in soup.select(selector):
            text = _clean_text(node.get_text(" ", strip=True))
            if len(text) > 280:
                candidates.append(text)

    if not candidates:
        candidates = [_clean_text(soup.get_text(" ", strip=True))]

    best = max(candidates, key=len, default="")
    return best[:MAX_PAGE_CHARS]


def _enrich_results_with_page_text(results: list) -> list:
    if not results:
        return results

    enriched = [dict(result) for result in results]
    indexes = list(range(min(MAX_RESULT_PAGES, len(enriched))))

    with ThreadPoolExecutor(max_workers=min(3, len(indexes))) as executor:
        future_to_index = {
            executor.submit(_extract_page_text, enriched[index]["url"]): index
            for index in indexes
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                text = future.result()
            except Exception as exc:
                enriched[index]["read_error"] = str(exc)
                continue
            if text:
                enriched[index]["page_text"] = text
    return enriched


def _safe_log(message: str) -> None:
    try:
        print(message.encode("ascii", errors="backslashreplace").decode("ascii"))
    except Exception:
        pass


def web_search(query: str, mode: str = "hybrid"):
    normalized_mode = normalize_mode(mode)
    if normalized_mode == "no_search" or not (query or "").strip():
        return "", []

    errors = []
    preferred_provider = os.getenv("SEARCH_PROVIDER", "").strip().lower()
    should_try_tavily = preferred_provider in {"", "tavily"} and bool(os.getenv("TAVILY_API_KEY", "").strip())

    if should_try_tavily:
        try:
            results = _tavily_search(query)
        except Exception as exc:
            errors.append(f"Tavily API search failed: {exc}")
            results = []
    else:
        results = []

    if not results:
        try:
            results = _requests_google_search(query)
        except Exception as exc:
            errors.append(f"Google requests search failed: {exc}")
            results = []

    if not results:
        try:
            results = _requests_bing_search(query)
        except Exception as exc:
            errors.append(f"Bing requests search failed: {exc}")

    if not results:
        try:
            results = _requests_duckduckgo_search(query)
        except Exception as exc:
            errors.append(f"DuckDuckGo requests search failed: {exc}")

    if not results:
        try:
            results = asyncio.run(_playwright_search(query, engine="google"))
        except Exception as exc:
            errors.append(f"Browser Google search failed: {exc}")

    if not results:
        try:
            results = asyncio.run(_playwright_search(query, engine="duckduckgo"))
        except Exception as exc:
            errors.append(f"Browser DuckDuckGo search failed: {exc}")

    if not results and errors:
        _safe_log("Search warnings: " + " | ".join(str(error) for error in errors))

    if results:
        results = _enrich_results_with_page_text(results)

    return _format_results(results), results


async def get_search_context(user_prompt: str, mode: str = "hybrid"):
    if normalize_mode(mode) == "no_search" or not needs_web_search(user_prompt):
        return ""
    formatted, _ = web_search(user_prompt, mode)
    return formatted
