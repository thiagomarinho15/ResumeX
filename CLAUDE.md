# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ResumeX** is a Flask web app that transcribes audio/video files and generates structured summaries using multiple LLM providers (Groq, Gemini, Ollama). Audio is processed entirely in the browser before being sent to the backend.

## Commands

```bash
# Run dev server
python run.py

# Install dependencies
pip install -r requirements.txt

# Docker
docker-compose up
docker-compose down
```

There are no automated tests, linters, or type checkers configured.

## Architecture

### Backend

- **`run.py`** — entry point; starts Flask on `0.0.0.0:PORT` (default 8765)
- **`app/__init__.py`** — Flask factory; registers the single blueprint from `routes.py`
- **`app/config.py`** — loads `.env` keys: `GROQ_API_KEY`, `GEMINI_API_KEY`, `PORT`, `FLASK_DEBUG`
- **`app/routes.py`** — three endpoints:
  - `GET /` → serves `index.html`
  - `POST /transcrever` → proxies multipart audio to `app/groq.py`
  - `POST /resumir` → dispatches to the selected summarizer in `app/summarizer.py`
- **`app/groq.py`** — thin proxy to Groq Whisper API for transcription
- **`app/summarizer.py`** — three streaming generators:
  - `stream_summary_groq()` — Llama 3.3 70B via Groq
  - `stream_summary_ollama()` — local Ollama (Gemma 2 9B or Qwen3 8B at `localhost:11434`)
  - `stream_summary_gemini()` — Gemini 2.5 Flash via Google Cloud
  - Flask returns `Response(generator)` so text streams to the browser in real time
  - Custom errors: `RateLimitError`, `OllamaOfflineError`

### Frontend

- **`templates/index.html`** — single-page UI: file drop zone, progress log, transcript view, provider selector, summary panel, PDF export
- **`static/js/app.js`** — all browser logic:
  - Decodes audio with Web Audio API and resamples to mono 16 kHz
  - Encodes PCM 16-bit WAV in-browser
  - Chunks files at 24 MB to respect Groq's API limit
  - Reads SSE/NDJSON stream from `/resumir` and renders markdown via `marked.js` (CDN)
  - PDF export uses `window.open()` with a styled print document
- **`static/css/style.css`** — CSS variables theme, responsive grid, `animate-up` scroll animations

### Data flow

```
User uploads file
  → browser resamples → WAV chunks → POST /transcrever → Groq Whisper
  → transcript displayed
  → user picks provider → POST /resumir → streaming LLM response
  → summary rendered as Markdown → optional PDF export
```

The app is **stateless** — no database; transcripts and summaries live only in the browser session.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | Whisper transcription + Groq LLM |
| `GEMINI_API_KEY` | No | Gemini 2.5 Flash summarization |
| `PORT` | No | Server port (default 8765) |
| `FLASK_DEBUG` | No | Enable Flask debug mode |

## System Prompt

All summaries are generated in **Portuguese**. The system prompt in `app/summarizer.py` instructs the model to produce structured output with main topics, key points, and conclusions.

## Deployment

Single-container Docker deployment via `docker-compose.yml`. Gunicorn runs with 2 workers and a 180s timeout. No volume mounts — all config via environment variables.
