from flask import Flask

from .config import Config
from .extensiones import db, migraciones
from .rutas import api


def create_app():
    aplicacion = Flask(__name__)
    aplicacion.config.from_object(Config)

    db.init_app(aplicacion)
    migraciones.init_app(aplicacion, db)
    aplicacion.register_blueprint(api)

    return aplicacion
