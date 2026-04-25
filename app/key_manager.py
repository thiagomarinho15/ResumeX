"""
Seleção de chaves por provider.

Cada provider Groq tem sua própria chave dedicada para rate limits independentes.
Os outros providers (Gemini, DeepSeek) usam round-robin entre as 3 chaves cadastradas.
"""
import threading

from flask import current_app

_counters: dict[str, int] = {}
_lock = threading.Lock()


def _pick(provider: str, keys: list[str]) -> str:
    if not keys:
        return ""
    with _lock:
        idx = _counters.get(provider, 0)
        _counters[provider] = (idx + 1) % len(keys)
    return keys[idx]


# ── Groq — chaves dedicadas por modelo ───────────────────────────────────────

def get_groq_transcription_key() -> str:
    return current_app.config["GROQ_TRANSCRIPTION_KEY"]


def get_groq_qwen_key() -> str:
    """Chave dedicada ao Qwen e ao Llama Standard."""
    return current_app.config["GROQ_QWEN_KEY"]


def get_groq_gptoss_key() -> str:
    """Chave dedicada exclusivamente ao GPT-OSS 120B."""
    return current_app.config["GROQ_GPTOSS_KEY"]


# ── Outros providers — round-robin ────────────────────────────────────────────

def get_gemini_key() -> str:
    return _pick("gemini", current_app.config["GEMINI_KEYS"])


