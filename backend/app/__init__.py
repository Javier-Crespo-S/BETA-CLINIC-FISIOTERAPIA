import os
from pathlib import Path

from flask import Flask
from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url
from dotenv import load_dotenv

from .extensiones import db, migraciones
from . import models
from .rutas import api


def _configuracion_de_pruebas() -> dict:
    url_pruebas = os.environ.get("TEST_DATABASE_URL")
    if not url_pruebas:
        raise RuntimeError("Define TEST_DATABASE_URL para ejecutar las pruebas.")

    try:
        url = make_url(url_pruebas)
        from .config import Config

        url_desarrollo = make_url(Config.SQLALCHEMY_DATABASE_URI)
    except (ArgumentError, ValueError) as error:
        raise RuntimeError(
            "TEST_DATABASE_URL o DATABASE_URL no es una URL válida."
        ) from error

    if url.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_DATABASE_URL debe apuntar a PostgreSQL.")

    nombre_base = url.database or ""
    if not nombre_base.endswith("_test") or nombre_base == "beta_clinic_dev":
        raise RuntimeError(
            "El nombre de la base de pruebas debe terminar en «_test»."
        )
    if nombre_base == url_desarrollo.database:
        raise RuntimeError(
            "TEST_DATABASE_URL debe apuntar a una base distinta de DATABASE_URL."
        )

    return {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": url_pruebas,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    }


def create_app(pruebas: bool = False):
    aplicacion = Flask(__name__)
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

    if pruebas:
        aplicacion.config.update(_configuracion_de_pruebas())
    else:
        from .config import Config

        aplicacion.config.from_object(Config)

    db.init_app(aplicacion)
    migraciones.init_app(aplicacion, db)
    aplicacion.register_blueprint(api)

    return aplicacion
