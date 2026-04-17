from flask import redirect, url_for
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user


class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_role("admin")

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login"))


def configure_admin(app):
    from . import db
    from .models import Document, Role, User

    admin = Admin(app, name="ResumeX Admin")
    admin.add_view(SecureModelView(User, db.session, name="Usuários"))
    admin.add_view(SecureModelView(Role, db.session, name="Roles"))
    admin.add_view(SecureModelView(Document, db.session, name="Documentos"))
