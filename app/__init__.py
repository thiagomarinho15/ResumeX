from flask import Flask

from .config import Config
from .routes import bp


def create_app(config_class: type = Config) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)
    app.register_blueprint(bp)
    return app
