from flask import Flask, Blueprint

client_provider_bp = Blueprint("client_provider_bp", __name__)
from .routes import *


def create_app(config_class):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.register_blueprint(client_provider_bp)
    return app
