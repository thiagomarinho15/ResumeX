# plano_acao.md — Profissionalização do ResumeX

> **Referência arquitetural:** [SynthesAIzer](https://github.com/thiagomarinho15/SynthesAIzer) branch `SynthesAIzer_claude`  
> **Objetivo:** Transformar o ResumeX em uma aplicação Flask profissional, modularizada, com autenticação, banco de dados, Docker multi-serviço e painel admin.

---

## Estado atual vs. estado alvo

| Aspecto | Hoje | Após este plano |
|---|---|---|
| Estrutura Flask | `app/routes.py` único | `app/views.py` único (idêntico ao SynthesAIzer) |
| Autenticação | Nenhuma | Flask-Security + Flask-Login + Argon2 |
| Banco de dados | Nenhum (stateless) | SQLAlchemy + Flask-Migrate + MySQL |
| Templates | `index.html` único | `base.html` + login + register + dashboard |
| Docker | Flask single-container | Flask + MySQL com healthcheck |
| Admin | Nenhum | Flask-Admin protegido por role |
| Segurança | Básica | CSRF, headers HTTP, rate limit no login |

---

## Estrutura de pastas alvo

Idêntica ao SynthesAIzer — flat, sem blueprints, sem subpastas de rotas:

```
resumex/
├── app/
│   ├── __init__.py          # Factory pattern (create_app)
│   ├── config.py            # Config por ambiente
│   ├── extensions.py        # Instâncias de db, migrate, login_manager, security
│   ├── models.py            # User, Role, Document
│   ├── forms.py             # LoginForm, RegisterForm (WTForms)
│   ├── security.py          # SQLAlchemyUserDatastore
│   ├── views.py             # Todas as rotas: auth + tool (idêntico ao views.py do SynthesAIzer)
│   ├── adm.py               # Flask-Admin views (mesmo nome do SynthesAIzer)
│   ├── groq.py              # (sem alteração)
│   ├── summarizer.py        # (sem alteração)
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── cadastro.html
│   │   ├── dashboard.html   # Tool atual (transcrição + resumo)
│   │   └── _flash_messages.html
│   └── static/              # (sem alteração)
│       ├── css/
│       └── js/
├── migrations/              # Flask-Migrate (Alembic)
├── main.py                  # Entrypoint (substitui run.py)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Etapa 1 — Dependências e configuração

### 1.1 Atualizar `requirements.txt`

Adicionar ao `requirements.txt` atual:

```
Flask-SQLAlchemy>=3.1
Flask-Migrate>=4.0
Flask-Login>=0.6
Flask-Security-Too>=5.5
Flask-WTF>=1.2
WTForms>=3.1
argon2-cffi>=23.1
Flask-Admin>=1.6
mysql-connector-python>=9.0
python-dotenv>=1.0
```

Manter as dependências já existentes (`requests`, `gunicorn`).

### 1.2 Criar `.env.example`

```env
# Flask
SECRET_KEY=troque-por-uma-chave-segura
SECURITY_PASSWORD_SALT=troque-por-um-salt-seguro
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=8765

# Banco de dados
DB_USER=resumex_user
DB_PASSWORD=resumex_pass
DB_HOST=db
DB_PORT=3306
DB_NAME=resumex_db

# APIs externas (já existem)
GROQ_API_KEY=
GEMINI_API_KEY=
```

---

## Etapa 2 — Modularização do Flask

### 2.1 `app/extensions.py`

Centralizar instâncias para evitar imports circulares (padrão do SynthesAIzer):

```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_security import Security

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
security = Security()
```

### 2.2 `app/config.py`

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    SECURITY_PASSWORD_SALT = os.environ["SECURITY_PASSWORD_SALT"]
    SECURITY_PASSWORD_HASH = "argon2"
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_USER = os.environ["DB_USER"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]
    DB_HOST = os.environ.get("DB_HOST", "db")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ["DB_NAME"]
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

    GROQ_API_KEY = os.environ["GROQ_API_KEY"]
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
```

### 2.3 `app/__init__.py` — Factory pattern

Seguir o `__init__.py` do SynthesAIzer: inicializa extensões, registra views diretamente no app (sem blueprints), configura admin e security headers:

```python
from flask import Flask
from .config import Config
from .extensions import db, migrate, login_manager, security
from .security import create_user_datastore
from .adm import configure_admin

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "login"   # nome da função em views.py, sem prefixo de blueprint

    user_datastore = create_user_datastore(db)
    security.init_app(app, user_datastore)

    configure_admin(app)

    from . import views  # registra todas as rotas no app

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src fonts.gstatic.com;"
        )
        return response

    return app
```

---

## Etapa 3 — Models e banco de dados

### 3.1 `app/models.py`

Três models, seguindo o padrão do SynthesAIzer:

**User** — campos obrigatórios para Flask-Security:
```python
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)     # hash Argon2
    active = db.Column(db.Boolean, default=True)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False)
    roles = db.relationship("Role", secondary="roles_users", backref="users")
```

**Role**:
```python
class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
```

**Document** — para histórico futuro (Fase 3 do PLAN.md):
```python
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    titulo = db.Column(db.String(255))
    transcricao = db.Column(db.Text)
    resumo = db.Column(db.Text)
    provider_usado = db.Column(db.String(50))
    criado_em = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

### 3.2 Inicializar migrations

Após criar os models, executar uma única vez:

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

---

## Etapa 4 — Autenticação

### 4.1 `app/forms.py`

```python
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")

class RegisterForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(2, 100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(8, 128)])
    confirmar_senha = PasswordField("Confirmar Senha", validators=[EqualTo("senha")])
    submit = SubmitField("Criar conta")
```

### 4.2 `app/views.py` — todas as rotas num único arquivo

Seguir o padrão do SynthesAIzer: `views.py` importa o `app` de `__init__.py` e registra todas as rotas com `@app.route`. Rate limit em memória, máximo 5 tentativas por 60s por IP, mensagem de erro unificada:

```python
from flask import current_app as app, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .extensions import db
from .models import User
from .forms import LoginForm, RegisterForm
import time

_tentativas: dict[str, list] = {}

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr
    agora = time.time()
    _tentativas[ip] = [t for t in _tentativas.get(ip, []) if agora - t < 60]
    if len(_tentativas[ip]) >= 5:
        flash("Muitas tentativas. Aguarde 1 minuto.", "warning")
        return redirect(url_for("login"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and verificar_senha(user.senha, form.senha.data):
            login_user(user)
            return redirect(url_for("dashboard"))
        _tentativas.setdefault(ip, []).append(agora)
        flash("Email ou senha incorretos.", "danger")
    return render_template("login.html", form=form)

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    ...

@app.route("/sair")
@login_required
def sair():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/transcrever", methods=["POST"])
@login_required
def transcrever():
    ...  # lógica atual de app/routes.py

@app.route("/resumir", methods=["POST"])
@login_required
def resumir():
    ...  # lógica atual de app/routes.py
```

### 4.3 Proteção automática

A rota `/` e as rotas de API já têm `@login_required`. O `login_manager.login_view = "login"` em `__init__.py` garante o redirect automático.

---

## Etapa 5 — Templates

Sem subpastas — todos os templates direto em `app/templates/`, igual ao SynthesAIzer.

### 5.1 `base.html` — Navbar com estado de autenticação

```html
<nav>
  <a href="{{ url_for('dashboard') }}">ResumeX</a>
  {% if current_user.is_authenticated %}
    <span>{{ current_user.nome }}</span>
    <a href="{{ url_for('sair') }}">Sair</a>
  {% else %}
    <a href="{{ url_for('login') }}">Entrar</a>
  {% endif %}
</nav>
{% include '_flash_messages.html' %}
{% block content %}{% endblock %}
```

### 5.2 `login.html` e `cadastro.html`

- Estender `base.html`
- Renderizar campos do WTForms com `{{ form.hidden_tag() }}` (CSRF token)
- Reutilizar classes CSS já existentes em `style.css`

### 5.3 `dashboard.html`

Mover o conteúdo atual de `index.html` para cá, estendendo `base.html`. A lógica de `app.js` não muda.

---

## Etapa 6 — Docker multi-serviço

### 6.1 `Dockerfile` atualizado

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["gunicorn", "--bind", "0.0.0.0:8765", "--workers", "2", "--timeout", "180", "main:app"]
```

### 6.2 `docker-compose.yml` com MySQL e healthcheck

Seguir exatamente o padrão do SynthesAIzer: Flask só sobe depois que o MySQL responde ao healthcheck:

```yaml
services:
  web:
    build: .
    ports: ["8765:8765"]
    env_file: ["./.env"]
    depends_on:
      db:
        condition: service_healthy
    volumes: [".:/app"]

  db:
    image: mysql:8.0
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
    volumes: ["resumex_mysql:/var/lib/mysql"]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u${DB_USER}", "-p${DB_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

volumes:
  resumex_mysql:
```

### 6.3 `main.py` — entrypoint limpo

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", 8765)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
```

---

## Etapa 7 — Painel admin

Arquivo `app/adm.py` (mesmo nome do SynthesAIzer), padrão `SecureModelView`:

```python
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for

class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_role("admin")
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login"))

def configure_admin(app):
    from .extensions import db
    from .models import User, Role, Document
    admin = Admin(app, name="ResumeX Admin", template_mode="bootstrap4")
    admin.add_view(SecureModelView(User, db.session))
    admin.add_view(SecureModelView(Role, db.session))
    admin.add_view(SecureModelView(Document, db.session))
```

---

## Sequência de implementação

Execute nesta ordem — cada etapa tem entrega verificável antes de partir para a próxima:

| # | Etapa | Entrega verificável |
|---|---|---|
| 1 | Dependências + `.env.example` | `pip install` sem erros |
| 2 | `extensions.py` + `config.py` + `models.py` | `flask shell` → `db.create_all()` sem erro |
| 3 | Factory `create_app` + `views.py` vazio | `flask run` sobe sem erro |
| 4 | Forms + rotas de auth (login/register/logout) | Login funciona, sessão persiste |
| 5 | `@login_required` em `/transcrever` e `/resumir` | Redirect para login se não autenticado |
| 6 | Templates (`base.html`, login, register, dashboard) | UI completa acessível pelo browser |
| 7 | Flask-Migrate + `flask db upgrade` | Tabelas criadas no MySQL |
| 8 | Docker-compose com MySQL + healthcheck | `docker-compose up` sobe tudo |
| 9 | Flask-Admin com roles | `/admin` acessível só com role admin |
| 10 | Security headers via `after_request` | Headers verificados no DevTools |

---

## O que NÃO muda

- `app/groq.py` — sem alteração
- `app/summarizer.py` — sem alteração
- `static/css/style.css` — sem alteração
- `static/js/app.js` — sem alteração
- A lógica de transcrição e resumo no frontend — sem alteração

A profissionalização é puramente na camada de infraestrutura Flask + auth + DB + Docker. O core do produto (audio → transcrição → resumo) não é tocado.

---

*Criado em 17/04/2026*
