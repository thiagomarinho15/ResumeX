import json

import requests

_SYSTEM_PROMPT = (
    "Você é um assistente especializado em criar resumos detalhados e estruturados. "
    "Analise a transcrição fornecida e produza um resumo completo em português, "
    "organizado com tópicos principais, pontos-chave e conclusões relevantes. "
    "Use formatação clara com seções bem definidas."
)

_USER_PROMPT = "Faça um resumo detalhado da seguinte transcrição:\n\n{transcription}"


class RateLimitError(Exception):
    pass


class OllamaOfflineError(Exception):
    pass


def stream_summary_groq(api_key: str, transcription: str):
    """Summarize using Groq (llama-3.3-70b-versatile) via streaming SSE.

    Makes the HTTP request eagerly so RateLimitError is raised before Flask
    starts streaming, allowing the route to return a proper 429 response.
    """
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _USER_PROMPT.format(transcription=transcription)},
            ],
            "stream": True,
            "max_tokens": 4096,
        },
        stream=True,
        timeout=120,
    )

    if response.status_code == 429:
        raise RateLimitError("Limite de requisições do Groq atingido.")

    response.raise_for_status()

    def _gen():
        for line in response.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if not text.startswith("data: "):
                continue
            payload = text[6:]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    return _gen()


def stream_summary_ollama(model: str, transcription: str, host: str = "localhost"):
    """Summarize using a local Ollama model (Gemma 2 or Qwen3) via streaming.

    Uses Ollama's native /api/chat endpoint (NDJSON streaming).
    Raises OllamaOfflineError if Ollama isn't running.
    """
    try:
        response = requests.post(
            f"http://{host}:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _USER_PROMPT.format(transcription=transcription)},
                ],
                "stream": True,
            },
            stream=True,
            timeout=300,
        )
    except requests.exceptions.ConnectionError:
        raise OllamaOfflineError("Ollama não está rodando. Inicie com: ollama serve")

    if response.status_code == 404:
        raise OllamaOfflineError(f"Modelo '{model}' não encontrado. Baixe com: ollama pull {model}")

    response.raise_for_status()

    def _gen():
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError):
                continue

    return _gen()


def stream_summary_gemini(api_key: str, transcription: str):
    """Summarize using Gemini 2.0 Flash (free tier) via streaming SSE.

    Same eager-request pattern as the Groq function.
    """
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent",
        params={"key": api_key, "alt": "sse"},
        json={
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{
                "role": "user",
                "parts": [{"text": _USER_PROMPT.format(transcription=transcription)}],
            }],
            "generationConfig": {"maxOutputTokens": 4096},
        },
        stream=True,
        timeout=120,
    )

    if response.status_code == 429:
        raise RateLimitError("Limite de requisições do Gemini atingido.")

    response.raise_for_status()

    def _gen():
        for line in response.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if not text.startswith("data: "):
                continue
            try:
                chunk = json.loads(text[6:])
                for candidate in chunk.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        content = part.get("text", "")
                        if content:
                            yield content
            except (json.JSONDecodeError, KeyError):
                continue

    return _gen()
