from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensiones import db
from app.models import (
    Bloqueo,
    Cita,
    DisponibilidadSemanal,
    Paciente,
    Profesional,
    TipoSesion,
)
from app.services.disponibilidad import (
    _instantes_validos,
    obtener_huecos_libres,
)


_MADRID = ZoneInfo("Europe/Madrid")
_AHORA = datetime(2030, 1, 7, 8, 0, tzinfo=_MADRID)
_INICIO = datetime(2030, 1, 8, 10, 0, tzinfo=_MADRID)
_FIN_SEGUIMIENTO = _INICIO + timedelta(minutes=30)


@pytest.fixture
def datos_agenda(contexto_aplicacion):
    profesional = Profesional(
        nombre="Profesional ficticio",
        especialidad="Fisioterapia general",
        activo=True,
    )
    paciente = Paciente(
        nombre="Paciente ficticio",
        email="paciente@example.invalid",
        telefono="600000000",
        email_verificado=False,
    )
    tipo_sesion = db.session.scalar(
        select(TipoSesion).where(TipoSesion.nombre == "seguimiento")
    )
    valoracion = db.session.scalar(
        select(TipoSesion).where(TipoSesion.nombre == "valoración inicial")
    )
    db.session.add_all([profesional, paciente])
    db.session.flush()
    db.session.add(
        DisponibilidadSemanal(
            profesional_id=profesional.id,
            dia_semana=date(2030, 1, 8).weekday(),
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
        )
    )
    db.session.commit()
    return {
        "profesional_id": profesional.id,
        "paciente_id": paciente.id,
        "seguimiento_id": tipo_sesion.id,
        "valoracion_id": valoracion.id,
    }


def _crear_cita(datos, inicio=_INICIO, fin=_FIN_SEGUIMIENTO, estado="confirmada"):
    return Cita(
        profesional_id=datos["profesional_id"],
        paciente_id=datos["paciente_id"],
        tipo_sesion_id=datos["seguimiento_id"],
        inicio=inicio,
        fin=fin,
        modalidad="presencial",
        estado=estado,
        hash_codigo_gestion="hash-ficticio",
    )


def test_base_de_datos_rechaza_citas_solapadas(datos_agenda):
    db.session.add(_crear_cita(datos_agenda))
    db.session.commit()

    db.session.add(
        _crear_cita(
            datos_agenda,
            inicio=_INICIO,
            fin=_INICIO + timedelta(minutes=60),
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_dos_reservas_simultaneas_del_mismo_hueco_una_falla(
    aplicacion, datos_agenda
):
    barrera = Barrier(2)

    def reservar():
        with aplicacion.app_context():
            try:
                db.session.add(_crear_cita(datos_agenda))
                barrera.wait(timeout=10)
                db.session.commit()
                return "confirmada"
            except IntegrityError:
                db.session.rollback()
                return "rechazada"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(lambda _: reservar(), range(2)))

    assert sorted(resultados) == ["confirmada", "rechazada"]


def test_citas_canceladas_no_bloquean_huecos(datos_agenda):
    db.session.add(_crear_cita(datos_agenda, estado="cancelada"))
    db.session.commit()

    huecos = obtener_huecos_libres(
        date(2030, 1, 8),
        datos_agenda["profesional_id"],
        datos_agenda["seguimiento_id"],
        ahora=_AHORA,
    )

    assert (_INICIO, _FIN_SEGUIMIENTO) in huecos


def test_base_de_datos_rechaza_citas_fuera_de_la_franja(datos_agenda):
    db.session.add(
        _crear_cita(
            datos_agenda,
            inicio=_INICIO + timedelta(minutes=15),
            fin=_FIN_SEGUIMIENTO + timedelta(minutes=15),
        )
    )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_bloqueo_elimina_el_hueco(datos_agenda):
    db.session.add(
        Bloqueo(
            profesional_id=datos_agenda["profesional_id"],
            inicio=_INICIO,
            fin=_FIN_SEGUIMIENTO,
            motivo="descanso",
        )
    )
    db.session.commit()

    huecos = obtener_huecos_libres(
        date(2030, 1, 8),
        datos_agenda["profesional_id"],
        datos_agenda["seguimiento_id"],
        ahora=_AHORA,
    )

    assert (_INICIO, _FIN_SEGUIMIENTO) not in huecos


def test_valoracion_necesita_dos_franjas_libres(datos_agenda):
    huecos = obtener_huecos_libres(
        date(2030, 1, 8),
        datos_agenda["profesional_id"],
        datos_agenda["valoracion_id"],
        ahora=_AHORA,
    )

    assert huecos
    assert all(fin - inicio == timedelta(minutes=60) for inicio, fin in huecos)
    assert all(inicio.minute in (0, 30) for inicio, _ in huecos)
    assert all(inicio.date() == fin.date() for inicio, fin in huecos)


def _ultimo_domingo(anio: int, mes: int) -> date:
    if mes == 12:
        primer_dia_mes_siguiente = date(anio + 1, 1, 1)
    else:
        primer_dia_mes_siguiente = date(anio, mes + 1, 1)
    ultimo_dia = primer_dia_mes_siguiente - timedelta(days=1)
    return ultimo_dia - timedelta(days=(ultimo_dia.weekday() - 6) % 7)


@pytest.mark.parametrize(
    ("mes", "esperados"),
    ((3, 0), (10, 2)),
    ids=("salto-de-marzo", "repeticion-de-octubre"),
)
def test_horas_locales_en_cambio_de_hora(mes, esperados):
    fecha = _ultimo_domingo(2026, mes)
    hora_cambio = datetime.combine(fecha, time(2, 0))
    instantes = _instantes_validos(hora_cambio)

    assert len(instantes) == esperados
    if mes == 10:
        assert instantes[1] - instantes[0] == timedelta(hours=1)


@pytest.mark.parametrize(
    ("mes", "esperados"),
    ((3, 0), (10, 4)),
    ids=("agenda-salto-de-marzo", "agenda-repeticion-de-octubre"),
)
def test_huecos_en_dias_de_cambio_de_hora(datos_agenda, mes, esperados):
    fecha = _ultimo_domingo(2026, mes)
    db.session.add(
        DisponibilidadSemanal(
            profesional_id=datos_agenda["profesional_id"],
            dia_semana=fecha.weekday(),
            hora_inicio=time(2, 0),
            hora_fin=time(3, 0),
        )
    )
    db.session.commit()
    ahora = datetime.combine(
        fecha - timedelta(days=20), time(12, 0), tzinfo=_MADRID
    )

    huecos = obtener_huecos_libres(
        fecha,
        datos_agenda["profesional_id"],
        datos_agenda["seguimiento_id"],
        ahora=ahora,
    )

    assert len(huecos) == esperados
    assert all(
        inicio.astimezone(timezone.utc) < fin.astimezone(timezone.utc)
        for inicio, fin in huecos
    )


def test_rechaza_fecha_actual_sin_zona_horaria(datos_agenda):
    with pytest.raises(ValueError, match="zona horaria"):
        obtener_huecos_libres(
            date(2030, 1, 8),
            datos_agenda["profesional_id"],
            datos_agenda["seguimiento_id"],
            ahora=datetime(2030, 1, 7, 8, 0),
        )


def test_conversion_de_inicio_y_fin_usa_zona_madrid():
    hora_local = datetime(2030, 1, 8, 9, 0)
    instantes = _instantes_validos(hora_local)

    assert len(instantes) == 1
    assert instantes[0].tzinfo is timezone.utc
    assert instantes[0].astimezone(_MADRID).replace(tzinfo=None) == hora_local
