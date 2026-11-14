import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from flask_migrate import upgrade
from sqlalchemy import delete

from app import create_app
from app.extensiones import db
from app.models import Bloqueo, Cita, DisponibilidadSemanal, Paciente, Profesional


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


@pytest.fixture(scope="session")
def aplicacion():
    aplicacion = create_app(pruebas=True)
    with aplicacion.app_context():
        ruta_migraciones = Path(aplicacion.root_path).parent / "migrations"
        upgrade(directory=str(ruta_migraciones))
        yield aplicacion
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def contexto_aplicacion(aplicacion):
    with aplicacion.app_context():
        yield
        db.session.remove()


@pytest.fixture(autouse=True)
def limpiar_datos(contexto_aplicacion):
    if "TEST_DATABASE_URL" not in os.environ:
        pytest.fail("Define TEST_DATABASE_URL para ejecutar las pruebas.")

    for modelo in (Cita, Bloqueo, DisponibilidadSemanal, Paciente, Profesional):
        db.session.execute(delete(modelo))
    db.session.commit()
