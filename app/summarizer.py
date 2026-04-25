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


class ProviderUnavailableError(Exception):
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stream_openai_compat(base_url: str, api_key: str, model: str, transcription: str):
    """Streaming SSE para qualquer provider com API compatível com OpenAI."""
    if not api_key:
        raise ProviderUnavailableError(f"Chave de API não configurada para o modelo '{model}'.")

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
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
        raise RateLimitError(f"Limite de requisições atingido ({model}).")

    if response.status_code in (402, 401, 403):
        raise ProviderUnavailableError(f"Acesso negado pelo provider ({model}). Verifique saldo ou chave de API.")

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


# ── Groq (Standard) ───────────────────────────────────────────────────────────

def stream_summary_groq(api_key: str, transcription: str):
    """Llama 3.3 70B via Groq — tier Standard."""
    return _stream_openai_compat(
        "https://api.groq.com/openai/v1",
        api_key,
        "llama-3.3-70b-versatile",
        transcription,
    )


# ── Groq (Pro) ────────────────────────────────────────────────────────────────

def stream_summary_groq_qwen(api_key: str, transcription: str, model: str):
    """Qwen via Groq — tier Pro. Model ID configurável via GROQ_QWEN_MODEL."""
    if not model:
        raise ProviderUnavailableError("GROQ_QWEN_MODEL não definido no .env.")
    return _stream_openai_compat(
        "https://api.groq.com/openai/v1",
        api_key,
        model,
        transcription,
    )


# ── Groq (Max) ────────────────────────────────────────────────────────────────

def stream_summary_groq_gptoss(api_key: str, transcription: str, model: str):
    """GPT-OSS 120B via Groq — tier Max. Model ID configurável via GROQ_GPTOSS_MODEL."""
    if not model:
        raise ProviderUnavailableError(
            "GROQ_GPTOSS_MODEL não definido no .env. "
            "Verifique o ID do modelo em console.groq.com/docs/models."
        )
    return _stream_openai_compat(
        "https://api.groq.com/openai/v1",
        api_key,
        model,
        transcription,
    )


# ── Mistral ───────────────────────────────────────────────────────────────────

def stream_summary_mistral(api_key: str, transcription: str, model: str):
    """Mistral via La Plateforme — Small (Pro) ou Large (Max)."""
    return _stream_openai_compat(
        "https://api.mistral.ai/v1",
        api_key,
        model,
        transcription,
    )


# ── Ollama (local) ────────────────────────────────────────────────────────────

def stream_summary_ollama(model: str, transcription: str, host: str = "localhost"):
    """Modelo local via Ollama (Gemma 2 ou Qwen3) — tier Standard."""
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


# ── Gemini ────────────────────────────────────────────────────────────────────

def stream_summary_gemini(api_key: str, transcription: str):
    """Gemini 2.5 Flash via Google AI Studio — tier Standard."""
    if not api_key:
        raise ProviderUnavailableError("Chave Gemini não configurada.")

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
