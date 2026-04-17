from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")


class RegisterForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(2, 100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(8, 128)])
    confirmar_senha = PasswordField(
        "Confirmar Senha",
        validators=[DataRequired(), EqualTo("senha", message="As senhas não coincidem.")],
    )
    submit = SubmitField("Criar conta")

    def validate_email(self, field):
        from .models import User
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("Este email já está cadastrado.")
