import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app


config = context.config
fileConfig(config.config_file_name)


def _obtener_motor():
    return current_app.extensions["migrate"].db.engine


def _obtener_metadatos():
    base_datos = current_app.extensions["migrate"].db
    if hasattr(base_datos, "metadatas"):
        return base_datos.metadatas[None]
    return base_datos.metadata


def _migrar_sin_conexion():
    context.configure(
        url=_obtener_motor().url,
        target_metadata=_obtener_metadatos(),
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _migrar_con_conexion():
    motor = _obtener_motor()
    argumentos = current_app.extensions["migrate"].configure_args

    def omitir_revision_vacia(contexto, revision, directivas):
        if getattr(config.cmd_opts, "autogenerate", False):
            if directivas[0].upgrade_ops.is_empty():
                directivas.clear()
                logging.getLogger("alembic.env").info(
                    "No se detectaron cambios en el esquema."
                )

    if argumentos.get("process_revision_directives") is None:
        argumentos["process_revision_directives"] = omitir_revision_vacia

    with motor.connect() as conexion:
        context.configure(
            connection=conexion,
            target_metadata=_obtener_metadatos(),
            **argumentos,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    _migrar_sin_conexion()
else:
    _migrar_con_conexion()
