from flask import Blueprint, Response, current_app, render_template, request

from .groq import proxy_transcription

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
