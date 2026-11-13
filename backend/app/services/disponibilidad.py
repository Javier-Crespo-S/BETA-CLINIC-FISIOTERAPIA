from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..extensiones import db
from ..models import Bloqueo, Cita, DisponibilidadSemanal, Profesional, TipoSesion


_ZONA_MADRID = ZoneInfo("Europe/Madrid")
_FRANJA = timedelta(minutes=30)
_ANTELACION_MINIMA = timedelta(hours=12)
_LIMITE_RESERVA = timedelta(days=60)


def _instantes_validos(hora_local: datetime) -> list[datetime]:
    """Convierte una hora local en sus instantes UTC válidos, si existen."""
    instantes = set()
    for pliegue in (0, 1):
        hora_aware = hora_local.replace(tzinfo=_ZONA_MADRID, fold=pliegue)
        instante = hora_aware.astimezone(timezone.utc)
        if instante.astimezone(_ZONA_MADRID).replace(tzinfo=None) == hora_local:
            instantes.add(instante)
    return sorted(instantes)


def obtener_huecos_libres(
    fecha: date,
    profesional_id: int,
    tipo_sesion_id: int,
    ahora: datetime | None = None,
) -> list[tuple[datetime, datetime]]:
    """Devuelve pares inicio/fin disponibles, con zona Europe/Madrid."""
    if isinstance(fecha, datetime) or not isinstance(fecha, date):
        raise ValueError("La fecha debe ser un objeto date sin hora.")

    profesional = db.session.get(Profesional, profesional_id)
    if profesional is None:
        raise ValueError("No existe el profesional indicado.")
    if not profesional.activo:
        return []

    tipo_sesion = db.session.get(TipoSesion, tipo_sesion_id)
    if tipo_sesion is None:
        raise ValueError("No existe el tipo de sesión indicado.")
    if not tipo_sesion.activo:
        return []

    duracion_minutos = tipo_sesion.duracion_minutos
    if duracion_minutos <= 0 or duracion_minutos % 30 != 0:
        raise ValueError("La duración de la sesión debe ser múltiplo de 30 minutos.")

    if ahora is None:
        ahora_utc = datetime.now(timezone.utc)
    elif ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("La fecha y hora actual debe incluir zona horaria.")
    else:
        ahora_utc = ahora.astimezone(timezone.utc)

    duracion = timedelta(minutes=duracion_minutos)
    limite_inferior = ahora_utc + _ANTELACION_MINIMA
    limite_superior = ahora_utc + _LIMITE_RESERVA

    disponibilidades = db.session.scalars(
        select(DisponibilidadSemanal).where(
            DisponibilidadSemanal.profesional_id == profesional_id,
            DisponibilidadSemanal.dia_semana == fecha.weekday(),
        )
    ).all()
    if not disponibilidades:
        return []

    candidatos_utc: set[tuple[datetime, datetime]] = set()
    for disponibilidad in disponibilidades:
        inicio_franja = datetime.combine(fecha, disponibilidad.hora_inicio)
        fin_franja = datetime.combine(fecha, disponibilidad.hora_fin)
        hora_local = inicio_franja

        while hora_local < fin_franja:
            for inicio_utc in _instantes_validos(hora_local):
                fin_utc = inicio_utc + duracion
                fin_local = fin_utc.astimezone(_ZONA_MADRID).replace(tzinfo=None)
                if fin_local.date() != fecha or fin_local > fin_franja:
                    continue
                if limite_inferior <= inicio_utc <= limite_superior:
                    candidatos_utc.add((inicio_utc, fin_utc))
            hora_local += _FRANJA

    if not candidatos_utc:
        return []

    inicio_busqueda = min(inicio for inicio, _ in candidatos_utc)
    fin_busqueda = max(fin for _, fin in candidatos_utc)

    bloqueos = db.session.execute(
        select(Bloqueo.inicio, Bloqueo.fin).where(
            Bloqueo.profesional_id == profesional_id,
            Bloqueo.inicio < fin_busqueda,
            Bloqueo.fin > inicio_busqueda,
        )
    ).all()
    citas_activas = db.session.execute(
        select(Cita.inicio, Cita.fin).where(
            Cita.profesional_id == profesional_id,
            Cita.estado != "cancelada",
            Cita.inicio < fin_busqueda,
            Cita.fin > inicio_busqueda,
        )
    ).all()
    ocupados = [*bloqueos, *citas_activas]

    huecos_utc = [
        (inicio, fin)
        for inicio, fin in sorted(candidatos_utc)
        if not any(
            ocupado_inicio < fin and ocupado_fin > inicio
            for ocupado_inicio, ocupado_fin in ocupados
        )
    ]
    return [
        (inicio.astimezone(_ZONA_MADRID), fin.astimezone(_ZONA_MADRID))
        for inicio, fin in huecos_utc
    ]
