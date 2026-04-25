from datetime import datetime, timezone

from flask_login import UserMixin

from . import db

roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    tier = db.Column(db.String(20), nullable=False, default="standard")
    roles = db.relationship("Role", secondary="roles_users", backref="users")
    documents = db.relationship("Document", backref="author", lazy=True)

    def has_role(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    titulo = db.Column(db.String(255))
    transcricao = db.Column(db.Text)
    resumo = db.Column(db.Text)
    provider_usado = db.Column(db.String(50))
    criado_em = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
