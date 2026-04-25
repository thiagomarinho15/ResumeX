"""
Teste in-place de todos os endpoints e providers do ResumeX.
Roda dentro do container onde as dependências já estão instaladas.
"""
import sys
import time
import requests
from pathlib import Path

BASE = "http://localhost:8765"
AUDIO = Path("/app/example/audio.ogg")
LOGIN = {"email": "admin@resumex.com", "senha": "admin123"}

PROVIDERS = [
    ("groq",        "Groq · Llama 3.3 70B  [Standard]"),
    ("gemini",      "Gemini · Flash 2.5    [Standard]"),
    ("groq-qwen",   "Qwen3 32B · Groq      [Pro]"),
    ("groq-gptoss", "GPT-OSS 120B · Groq   [Max]"),
]

PASS = "✓"
FAIL = "✗"
SKIP = "⚠"


def separator(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
        print("─" * 60)


def login(session):
    r = session.get(f"{BASE}/login")
    from html.parser import HTMLParser

    class TokenParser(HTMLParser):
        token = ""
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("name") == "csrf_token":
                self.token = attrs.get("value", "")

    p = TokenParser()
    p.feed(r.text)

    r2 = session.post(f"{BASE}/login", data={
        "email": LOGIN["email"],
        "senha": LOGIN["senha"],
        "csrf_token": p.token,
    }, allow_redirects=True)

    ok = "dashboard" in r2.url or r2.url.endswith("/")
    return ok


def test_transcription(session):
    separator("1. TRANSCRIÇÃO (Groq Whisper)")

    if not AUDIO.exists():
        print(f"  {FAIL} Arquivo não encontrado: {AUDIO}")
        return None

    print(f"  Arquivo : {AUDIO.name} ({AUDIO.stat().st_size / 1024:.1f} KB)")
    print("  Enviando para /transcrever ...")

    with open(AUDIO, "rb") as f:
        r = session.post(
            f"{BASE}/transcrever",
            files={"file": (AUDIO.name, f, "audio/ogg")},
            data={
                "model": "whisper-large-v3",
                "language": "pt",
                "response_format": "text",
            },
            timeout=120,
        )

    if r.status_code == 200:
        text = r.text.strip()
        words = len(text.split())
        print(f"  {PASS} Transcrição OK — {words} palavras")
        print(f"  Prévia: \"{text[:120]}...\"" if len(text) > 120 else f"  Texto : \"{text}\"")
        return text
    else:
        print(f"  {FAIL} Erro {r.status_code}: {r.text[:200]}")
        return None


def test_summary(session, transcription, provider_id, provider_label):
    print(f"\n  [{provider_label}]")
    t0 = time.time()

    r = session.post(
        f"{BASE}/resumir",
        json={"transcricao": transcription, "provider": provider_id},
        stream=True,
        timeout=120,
    )

    if r.status_code == 403:
        print(f"    {SKIP} Bloqueado (tier insuficiente): {r.text.strip()}")
        return
    if r.status_code == 429:
        print(f"    {SKIP} Rate limit atingido: {r.text.strip()}")
        return
    if r.status_code == 503:
        print(f"    {FAIL} Provider indisponível: {r.text.strip()}")
        return
    if r.status_code != 200:
        print(f"    {FAIL} Erro {r.status_code}: {r.text[:200]}")
        return

    chunks = []
    for chunk in r.iter_content(chunk_size=None):
        if chunk:
            chunks.append(chunk.decode("utf-8", errors="replace"))

    elapsed = time.time() - t0
    full = "".join(chunks)
    words = len(full.split())
    print(f"    {PASS} OK — {words} palavras em {elapsed:.1f}s")
    print(f"    Prévia: \"{full[:100].strip()}...\"")


def main():
    separator("RESUMEX — TESTE COMPLETO DE PROVIDERS")
    print(f"  Base URL : {BASE}")
    print(f"  Usuário  : {LOGIN['email']} (tier: max)")

    session = requests.Session()

    # Login
    separator("0. AUTENTICAÇÃO")
    print("  Fazendo login...")
    if not login(session):
        print(f"  {FAIL} Login falhou. Verifique se o admin existe (rode seed.py).")
        sys.exit(1)
    print(f"  {PASS} Login OK")

    # Transcrição
    transcription = test_transcription(session)
    if not transcription:
        print("\n  Abortando testes de resumo — sem transcrição.")
        sys.exit(1)

    # Resumos
    separator("2. RESUMOS — TODOS OS PROVIDERS")
    for provider_id, label in PROVIDERS:
        test_summary(session, transcription, provider_id, label)

    separator("TESTE CONCLUÍDO")
    print()


if __name__ == "__main__":
    main()
