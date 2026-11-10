from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

from .extensiones import db, migraciones
from .rutas import api


def create_app():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

    from .config import Config

    aplicacion = Flask(__name__)
    aplicacion.config.from_object(Config)

    db.init_app(aplicacion)
    migraciones.init_app(aplicacion, db)
    aplicacion.register_blueprint(api)

    return aplicacion
