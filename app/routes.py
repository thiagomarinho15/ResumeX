from flask import Blueprint, Response, current_app, render_template, request

from .groq import proxy_transcription
from .summarizer import (
    OllamaOfflineError,
    RateLimitError,
    stream_summary_gemini,
    stream_summary_groq,
    stream_summary_ollama,
)

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/transcrever")
def transcrever():
    body = request.get_data()
    content_type = request.content_type or ""
    api_key = current_app.config["GROQ_API_KEY"]

    result, status = proxy_transcription(api_key, body, content_type)

    return Response(result, status=status, content_type="text/plain; charset=utf-8")


@bp.post("/resumir")
def resumir():
    data = request.get_json(force=True) or {}
    transcricao = data.get("transcricao", "")
    provider = data.get("provider", "groq")

    _OLLAMA_MODELS = {
        "gemma2": "gemma2:9b",
        "qwen3":  "qwen3:8b",
    }

    try:
        if provider == "gemini":
            gen = stream_summary_gemini(current_app.config["GEMINI_API_KEY"], transcricao)
        elif provider in _OLLAMA_MODELS:
            gen = stream_summary_ollama(_OLLAMA_MODELS[provider], transcricao)
        else:
            gen = stream_summary_groq(current_app.config["GROQ_API_KEY"], transcricao)

        return Response(gen, content_type="text/plain; charset=utf-8")

    except RateLimitError as e:
        return Response(str(e), status=429, content_type="text/plain; charset=utf-8")
    except OllamaOfflineError as e:
        return Response(str(e), status=503, content_type="text/plain; charset=utf-8")
