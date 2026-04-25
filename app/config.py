import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-production")

    WTF_CSRF_ENABLED = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # DB: MySQL se configurado, SQLite como fallback para dev local
    _db_user = os.environ.get("DB_USER")
    if _db_user:
        _db_password = os.environ.get("DB_PASSWORD", "")
        _db_host = os.environ.get("DB_HOST", "db")
        _db_port = os.environ.get("DB_PORT", "3306")
        _db_name = os.environ.get("DB_NAME", "resumex_db")
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+mysqlconnector://{_db_user}:{_db_password}"
            f"@{_db_host}:{_db_port}/{_db_name}?charset=utf8mb4"
        )
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///resumex.db"

    # ── Groq ──────────────────────────────────────────────────────────────────
    # 3 chaves dedicadas — cada uma com rate limit independente
    GROQ_TRANSCRIPTION_KEY = os.environ.get("GROQ_TRANSCRIPTION_KEY", "")  # Whisper
    GROQ_QWEN_KEY = os.environ.get("GROQ_QWEN_KEY", "")                    # Qwen + Llama
    GROQ_GPTOSS_KEY = os.environ.get("GROQ_GPTOSS_KEY", "")                # GPT-OSS 120B

    # IDs de modelo — verificar nomes exatos em console.groq.com/docs/models
    GROQ_QWEN_MODEL = os.environ.get("GROQ_QWEN_MODEL", "qwen-qwq-32b")
    GROQ_GPTOSS_MODEL = os.environ.get("GROQ_GPTOSS_MODEL", "")  # obrigatório definir no .env

    # ── Gemini ────────────────────────────────────────────────────────────────
    # Pool de 3 chaves (Google AI Studio) — round-robin
    GEMINI_KEYS = [
        k for k in [
            os.environ.get("GEMINI_KEY_1", os.environ.get("GEMINI_API_KEY", "")),
            os.environ.get("GEMINI_KEY_2", ""),
            os.environ.get("GEMINI_KEY_3", ""),
        ]
        if k
    ]

    # ── Mistral ───────────────────────────────────────────────────────────────
    MISTRAL_KEYS = [
        k for k in [
            os.environ.get("MISTRAL_KEY_1", ""),
            os.environ.get("MISTRAL_KEY_2", ""),
            os.environ.get("MISTRAL_KEY_3", ""),
        ]
        if k
    ]

    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")

    FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.environ.get("FLASK_PORT", os.environ.get("PORT", "8765")))
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
