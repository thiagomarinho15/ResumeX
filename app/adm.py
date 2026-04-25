from flask import redirect, url_for
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from wtforms import SelectField
from wtforms.validators import DataRequired


class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_role("admin")

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login"))


class UserAdminView(SecureModelView):
    column_list = ("id", "nome", "email", "tier", "active", "roles")
    column_editable_list = ("tier", "active")
    column_searchable_list = ("nome", "email")
    column_filters = ("tier", "active")
    column_labels = {"nome": "Nome", "tier": "Plano", "active": "Ativo"}

    form_extra_fields = {
        "tier": SelectField(
            "Plano",
            choices=[
                ("standard", "Standard"),
                ("pro", "Pro"),
                ("max", "Max"),
            ],
            validators=[DataRequired()],
        )
    }
    form_excluded_columns = ("senha", "documents")


def configure_admin(app):
    from . import db
    from .models import Document, Role, User

    admin = Admin(app, name="ResumeX Admin")
    admin.add_view(UserAdminView(User, db.session, name="Usuários"))
    admin.add_view(SecureModelView(Role, db.session, name="Roles"))
    admin.add_view(SecureModelView(Document, db.session, name="Documentos"))
