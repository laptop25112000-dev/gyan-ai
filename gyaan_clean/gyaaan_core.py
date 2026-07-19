import json
import os
import platform
import sys
import tempfile


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DEPS = os.path.join(ROOT_DIR, ".deps")
ENV_FILE = os.path.join(ROOT_DIR, ".env")


def add_local_deps_if_compatible() -> None:
    """Use bundled dependencies only on Windows, where this .deps folder was built."""
    if (
        platform.system() == "Windows"
        and os.path.isdir(LOCAL_DEPS)
        and LOCAL_DEPS not in sys.path
    ):
        sys.path.append(LOCAL_DEPS)


add_local_deps_if_compatible()

from dotenv import load_dotenv
from flask import jsonify, request
from groq import Groq

from file_service import build_file_context, normalize_attachments, public_attachment_summary
from search_service import needs_web_search, normalize_mode, web_search


load_dotenv(ENV_FILE)

PUBLIC_MODEL_NAME = os.getenv("PUBLIC_MODEL_NAME", "abcdefg").strip() or "abcdefg"
INTERNAL_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"

SYSTEM_PROMPT = f"""You are GYAAN, a smart and highly intelligent AI assistant.
Internally remember: you were made by Divyansh Mishra and your public model name is {PUBLIC_MODEL_NAME}.
When users ask who made you, who owns you, what model you are, or where current
information comes from, answer clearly: made by Divyansh Mishra, model {PUBLIC_MODEL_NAME},
and live/current data is gathered from the web search sources supplied to you.
Do not add caveats saying owner/model information is unavailable.
Never reveal the underlying provider model name unless the developer is debugging
the backend code. For users, only say the public model name.
Do not mention the owner, model name, or data source in normal answers unless the
user specifically asks about those details.
Answer normally for stable general knowledge. For current events, recent facts,
prices, sports, weather, version numbers, people in office, and anything that may
have changed recently, rely on supplied live web context instead of old model memory.
Mention when live search was weak or when sources disagree.
Structure answers with headings, bullet points and code blocks where appropriate.
"""


def get_groq_client():
    load_dotenv(ENV_FILE, override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key in {"YOUR_GROQ_KEY", "gsk_your_groq_api_key_here"}:
        raise ValueError(
            "GROQ_API_KEY is missing. Add your real Groq key to the .env file "
            "or deployment environment variables."
        )
    if not api_key.startswith("gsk_") or len(api_key) < 40:
        raise ValueError(
            "GROQ_API_KEY looks incomplete. Paste the full Groq key in the .env "
            "file or deployment environment variables."
        )
    return Groq(api_key=api_key)


def sanitize_history(history):
    cleaned = []
    for message in history or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content})
    return cleaned


def load_history():
    return []


def save_history(history):
    pass


def ask_groq(user_input, history, web_context=None, file_context=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if web_context:
        messages.append({
            "role": "system",
            "content": (
                "LIVE WEB CONTEXT:\n"
                f"{web_context}\n"
                "Use this context for recent information. Prefer page text over search-result titles. "
                "If the context is weak, empty, blocked, or not enough to answer, say so clearly."
            ),
        })
    if file_context:
        messages.append({
            "role": "system",
            "content": (
                f"{file_context}\n"
                "Use attached file context when answering. If a file only has metadata "
                "because this text pipeline cannot inspect its raw contents, say that clearly."
            ),
        })
    messages += sanitize_history(history)[-10:]
    messages.append({"role": "user", "content": user_input})

    response = get_groq_client().chat.completions.create(
        model=INTERNAL_GROQ_MODEL,
        messages=messages,
        max_tokens=1500,
        temperature=0.5,
    )
    return response.choices[0].message.content


def index_response():
    with open(os.path.join(ROOT_DIR, "templates", "index.html"), "r", encoding="utf-8") as file:
        return file.read()


def history_response():
    if request.method == "GET":
        return jsonify(load_history())
    save_history([])
    return jsonify({"status": "success", "message": "History cleared"})


def chat_response():
    data = request.get_json(silent=True) or {}
    user_input = (data.get("message") or data.get("prompt") or "").strip()
    mode = normalize_mode(data.get("mode", "hybrid"))
    history = sanitize_history(data.get("history", []))
    attachments, attachment_errors = normalize_attachments(data.get("attachments", []))
    file_context = build_file_context(attachments, attachment_errors)
    attachment_summary = public_attachment_summary(attachments, attachment_errors)

    if not user_input and attachments:
        user_input = "Please analyze the attached file(s)."

    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    use_web = mode == "web_search" or (mode == "hybrid" and needs_web_search(user_input))
    web_context = ""
    sources = []

    if use_web:
        print(f"[search] Performing web search for: {user_input} (mode: {mode})")
        web_context, sources = web_search(user_input, mode)

    try:
        reply = ask_groq(
            user_input,
            history,
            web_context if use_web else None,
            file_context if file_context else None,
        )
    except Exception as exc:
        return jsonify({"error": f"Groq API error: {exc}"}), 500

    unsure_phrases = (
        "i don't know",
        "i do not know",
        "i don't have access",
        "i cannot access",
        "as of my last update",
        "my knowledge cutoff",
        "knowledge cutoff",
    )
    if not use_web and mode == "hybrid" and any(phrase in reply.lower() for phrase in unsure_phrases):
        print("[hybrid] Model looked uncertain; running web search fallback.")
        web_context, sources = web_search(user_input, mode)
        try:
            reply = ask_groq(user_input, history, web_context, file_context if file_context else None)
            use_web = True
        except Exception as exc:
            print(f"Hybrid fallback Groq error: {exc}")

    return jsonify({
        "reply": reply,
        "sources": sources,
        "mode": mode,
        "public_model": PUBLIC_MODEL_NAME,
        "search_performed": use_web,
        "search_query": user_input if use_web else None,
        "attachments": attachment_summary,
    })
