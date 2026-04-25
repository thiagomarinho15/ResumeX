import time

from flask import Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import app, db
from .forms import LoginForm, RegisterForm
from .groq import proxy_transcription
from .key_manager import get_gemini_key, get_groq_gptoss_key, get_groq_qwen_key, get_groq_transcription_key
from .models import Role, User
from .security import hash_password, verify_password
from .summarizer import (
    OllamaOfflineError,
    ProviderUnavailableError,
    RateLimitError,
    stream_summary_gemini,
    stream_summary_groq,
    stream_summary_groq_gptoss,
    stream_summary_groq_qwen,
    stream_summary_ollama,
)

_tentativas: dict[str, list] = {}

# Providers disponíveis por tier (cada tier inclui os do tier anterior)
_TIER_PERMISSIONS: dict[str, set[str]] = {
    "standard": {"groq", "gemini", "gemma2", "qwen3"},
    "pro":      {"groq", "gemini", "gemma2", "qwen3", "groq-qwen"},
    "max":      {"groq", "gemini", "gemma2", "qwen3", "groq-qwen", "groq-gptoss"},
}
_PRO_ONLY = _TIER_PERMISSIONS["pro"] - _TIER_PERMISSIONS["standard"]
_MAX_ONLY = _TIER_PERMISSIONS["max"] - _TIER_PERMISSIONS["pro"]

_OLLAMA_MODELS = {"gemma2": "gemma2:9b", "qwen3": "qwen3:8b"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    ip = request.remote_addr
    agora = time.time()
    _tentativas[ip] = [t for t in _tentativas.get(ip, []) if agora - t < 60]
    if len(_tentativas[ip]) >= 5:
        flash("Muitas tentativas. Aguarde 1 minuto.", "warning")
        return redirect(url_for("login"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and verify_password(form.senha.data, user.senha):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        _tentativas.setdefault(ip, []).append(agora)
        flash("Email ou senha incorretos.", "danger")

    return render_template("login.html", form=form)


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        role_usuario = Role.query.filter_by(name="usuario").first()
        user = User(
            nome=form.nome.data.strip(),
            email=form.email.data.lower().strip(),
            senha=hash_password(form.senha.data),
        )
        if role_usuario:
            user.roles.append(role_usuario)
        db.session.add(user)
        db.session.commit()
        flash("Conta criada com sucesso! Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("cadastro.html", form=form)


@app.route("/sair")
@login_required
def sair():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", user_tier=current_user.tier or "standard")


@app.route("/transcrever", methods=["POST"])
@login_required
def transcrever():
    body = request.get_data()
    content_type = request.content_type or ""
    api_key = get_groq_transcription_key()
    result, status = proxy_transcription(api_key, body, content_type)
    return Response(result, status=status, content_type="text/plain; charset=utf-8")


@app.route("/resumir", methods=["POST"])
@login_required
def resumir():
    data = request.get_json(force=True) or {}
    transcricao = data.get("transcricao", "")
    provider = data.get("provider", "groq")
    user_tier = current_user.tier or "standard"

    allowed = _TIER_PERMISSIONS.get(user_tier, _TIER_PERMISSIONS["standard"])
    if provider not in allowed:
        tier_required = "Max" if provider in _MAX_ONLY else "Pro"
        return Response(
            f"Este modelo requer o plano {tier_required}. Peça ao administrador para atualizar seu plano.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )

    try:
        if provider == "gemini":
            gen = stream_summary_gemini(get_gemini_key(), transcricao)
        elif provider in _OLLAMA_MODELS:
            gen = stream_summary_ollama(_OLLAMA_MODELS[provider], transcricao, current_app.config["OLLAMA_HOST"])
        elif provider == "groq-qwen":
            gen = stream_summary_groq_qwen(get_groq_qwen_key(), transcricao, current_app.config["GROQ_QWEN_MODEL"])
        elif provider == "groq-gptoss":
            gen = stream_summary_groq_gptoss(get_groq_gptoss_key(), transcricao, current_app.config["GROQ_GPTOSS_MODEL"])
        else:  # groq llama — padrão
            gen = stream_summary_groq(get_groq_qwen_key(), transcricao)

        return Response(gen, content_type="text/plain; charset=utf-8")

    except RateLimitError as e:
        return Response(str(e), status=429, content_type="text/plain; charset=utf-8")
    except OllamaOfflineError as e:
        return Response(str(e), status=503, content_type="text/plain; charset=utf-8")
    except ProviderUnavailableError as e:
        return Response(str(e), status=503, content_type="text/plain; charset=utf-8")
