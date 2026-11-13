from datetime import time

from sqlalchemy import select

from app import create_app
from app.extensiones import db
from app.models import DisponibilidadSemanal, Profesional, TipoSesion


_NOMBRE_PROFESIONAL = "Profesional de prueba"
_ESPECIALIDAD = "Fisioterapia general"
_TIPOS_SESION = (
    ("valoración inicial", 60),
    ("seguimiento", 30),
)
_HORARIOS_LABORALES = (
    (time(9, 0), time(14, 0)),
    (time(16, 0), time(20, 0)),
)


def cargar_datos_prueba() -> tuple[str, int, int]:
    with db.session.begin():
        profesional = db.session.execute(
            select(Profesional).where(
                Profesional.nombre == _NOMBRE_PROFESIONAL,
                Profesional.especialidad == _ESPECIALIDAD,
            )
        ).scalar_one_or_none()

        if profesional is None:
            profesional = Profesional(
                nombre=_NOMBRE_PROFESIONAL,
                especialidad=_ESPECIALIDAD,
                activo=True,
            )
            db.session.add(profesional)
            db.session.flush()

        for nombre, duracion_minutos in _TIPOS_SESION:
            tipo_sesion = db.session.execute(
                select(TipoSesion).where(TipoSesion.nombre == nombre)
            ).scalar_one_or_none()
            if tipo_sesion is None:
                db.session.add(
                    TipoSesion(
                        nombre=nombre,
                        duracion_minutos=duracion_minutos,
                        activo=True,
                    )
                )
            elif tipo_sesion.duracion_minutos != duracion_minutos:
                raise ValueError(
                    f"La duración configurada para «{nombre}» no coincide "
                    f"con los {duracion_minutos} minutos esperados."
                )

        disponibilidades = db.session.scalars(
            select(DisponibilidadSemanal).where(
                DisponibilidadSemanal.profesional_id == profesional.id,
                DisponibilidadSemanal.dia_semana.between(0, 4),
            )
        ).all()
        horarios_existentes = {
            (
                disponibilidad.dia_semana,
                disponibilidad.hora_inicio,
                disponibilidad.hora_fin,
            )
            for disponibilidad in disponibilidades
        }

        disponibilidades_creadas = 0
        for dia_semana in range(5):
            for hora_inicio, hora_fin in _HORARIOS_LABORALES:
                horario = (dia_semana, hora_inicio, hora_fin)
                if horario in horarios_existentes:
                    continue
                db.session.add(
                    DisponibilidadSemanal(
                        profesional_id=profesional.id,
                        dia_semana=dia_semana,
                        hora_inicio=hora_inicio,
                        hora_fin=hora_fin,
                    )
                )
                disponibilidades_creadas += 1

        nombre_profesional = profesional.nombre
        id_profesional = profesional.id

    return nombre_profesional, id_profesional, disponibilidades_creadas


def main() -> None:
    aplicacion = create_app()
    with aplicacion.app_context():
        nombre, profesional_id, disponibilidades_creadas = cargar_datos_prueba()
        print(
            f"Datos de prueba listos para {nombre} (id {profesional_id}); "
            f"franjas nuevas: {disponibilidades_creadas}."
        )


if __name__ == "__main__":
    main()
