from flask import Blueprint, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .extensiones import db


api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/salud")
def comprobar_salud():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(estado="error", base_de_datos="no disponible"), 503

    return jsonify(estado="ok", base_de_datos="conectada")
