import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PORT: int = int(os.getenv("PORT", "8765"))
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
