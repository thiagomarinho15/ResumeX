from __future__ import annotations

import requests

_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_USER_AGENT = "groq-python/0.22.0"


def proxy_transcription(
    api_key: str, body: bytes, content_type: str
) -> tuple[bytes, int]:
    """Forward a multipart audio request to the Groq transcription API.

    Returns the raw response body and HTTP status code so the Flask
    route can pass them back to the browser unchanged.
    """
    response = requests.post(
        _TRANSCRIPTION_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": _USER_AGENT,
        },
        timeout=120,
    )
    return response.content, response.status_code
