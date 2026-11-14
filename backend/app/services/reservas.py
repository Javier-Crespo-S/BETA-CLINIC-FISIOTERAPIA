import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..extensiones import db
from ..models import Cita, Paciente, Profesional, TipoSesion
from .disponibilidad import obtener_huecos_libres


_ZONA_MADRID = ZoneInfo("Europe/Madrid")
_DURACION_CODIGO_BYTES = 32
_LONGITUD_MAXIMA_CODIGO = 256
_HASH_SOLAPAMIENTO = "ex_cita_profesional_horario_activo"
_MENSAJE_HUECO_NO_DISPONIBLE = "El hueco ya no está disponible."
_MENSAJE_CITA_NO_ENCONTRADA = "No se encontró una cita con ese código."


class ErrorReserva(Exception):
    """Error de dominio al crear o gestionar una reserva."""


class DatosPacienteInvalidos(ErrorReserva):
    """Los datos de contacto mínimos no son válidos."""


class EmailNoVerificado(ErrorReserva):
    """El email del paciente todavía no está verificado."""


class SeguimientoRequiereValoracion(ErrorReserva):
    """No se puede reservar seguimiento sin una valoración realizada."""


class HuecoNoDisponible(ErrorReserva):
    """El inicio solicitado no está libre para esa sesión."""


class CitaNoEncontrada(ErrorReserva):
    """No hay una cita asociada al código de gestión proporcionado."""


class CitaNoCancelable(ErrorReserva):
    """La cita no cumple las condiciones para cancelarse."""


@dataclass(frozen=True)
class CitaPublica:
    fecha: date
    hora: time
    tipo_sesion: str
    modalidad: str
    estado: str


def _ahora_utc(ahora: datetime | None) -> datetime:
    if ahora is None:
        return datetime.now(timezone.utc)
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ErrorReserva("La fecha y hora deben incluir zona horaria.")
    return ahora.astimezone(timezone.utc)


def _hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def _buscar_cita_por_codigo(codigo: str) -> Cita:
    if (
        not isinstance(codigo, str)
        or not codigo
        or len(codigo) > _LONGITUD_MAXIMA_CODIGO
    ):
        raise CitaNoEncontrada(_MENSAJE_CITA_NO_ENCONTRADA)

    codigo_hash = _hash_codigo(codigo)
    cita = db.session.scalars(
        select(Cita)
        .options(joinedload(Cita.tipo_sesion))
        .where(Cita.hash_codigo_gestion == codigo_hash)
        .limit(1)
    ).first()

    if cita is None or not hmac.compare_digest(
        cita.hash_codigo_gestion, codigo_hash
    ):
        raise CitaNoEncontrada(_MENSAJE_CITA_NO_ENCONTRADA)
    return cita


def _cita_publica(cita: Cita) -> CitaPublica:
    inicio_local = cita.inicio.astimezone(_ZONA_MADRID)
    return CitaPublica(
        fecha=inicio_local.date(),
        hora=inicio_local.timetz().replace(tzinfo=None),
        tipo_sesion=cita.tipo_sesion.nombre,
        modalidad=cita.modalidad,
        estado=cita.estado,
    )


def _es_conflicto_de_solapamiento(error: IntegrityError) -> bool:
    error_postgres = error.orig
    codigo_estado = getattr(error_postgres, "sqlstate", None) or getattr(
        error_postgres, "pgcode", None
    )
    diagnostico = getattr(error_postgres, "diag", None)
    nombre_restriccion = getattr(diagnostico, "constraint_name", None)
    return (
        codigo_estado == "23P01"
        and nombre_restriccion == _HASH_SOLAPAMIENTO
    )


def obtener_o_crear_paciente(nombre: str, email: str, telefono: str) -> Paciente:
    if not all(isinstance(valor, str) for valor in (nombre, email, telefono)):
        raise DatosPacienteInvalidos("Completa los datos de contacto requeridos.")

    nombre = nombre.strip()
    email = email.strip().lower()
    telefono = telefono.strip()
    if (
        not nombre
        or not email
        or not telefono
        or len(nombre) > 120
        or len(email) > 254
        or len(telefono) > 32
    ):
        raise DatosPacienteInvalidos("Completa los datos de contacto requeridos.")

    paciente = db.session.scalar(
        select(Paciente).where(func.lower(Paciente.email) == email)
    )
    if paciente is not None:
        return paciente

    paciente = Paciente(
        nombre=nombre,
        email=email,
        telefono=telefono,
        email_verificado=False,
    )
    db.session.add(paciente)
    db.session.commit()
    return paciente


def crear_cita(
    paciente: Paciente,
    profesional: Profesional,
    tipo_sesion: TipoSesion,
    inicio: datetime,
    ahora: datetime | None = None,
) -> tuple[Cita, str]:
    if (
        not isinstance(paciente, Paciente)
        or not isinstance(profesional, Profesional)
        or not isinstance(tipo_sesion, TipoSesion)
        or not isinstance(inicio, datetime)
        or inicio.tzinfo is None
        or inicio.utcoffset() is None
    ):
        raise HuecoNoDisponible(_MENSAJE_HUECO_NO_DISPONIBLE)
    if not all(
        (
            paciente.id is not None,
            profesional.id is not None,
            tipo_sesion.id is not None,
        )
    ):
        raise HuecoNoDisponible(_MENSAJE_HUECO_NO_DISPONIBLE)

    paciente_guardado = db.session.get(Paciente, paciente.id)
    if paciente_guardado is None:
        raise DatosPacienteInvalidos("No se pudieron validar los datos del paciente.")
    if not paciente_guardado.email_verificado:
        raise EmailNoVerificado("Verifica tu email antes de reservar una cita.")

    seguimiento = db.session.scalar(
        select(TipoSesion).where(
            TipoSesion.id == tipo_sesion.id,
            func.lower(TipoSesion.nombre) == "seguimiento",
        )
    )
    if seguimiento is not None:
        tiene_valoracion_realizada = db.session.scalar(
            select(Cita.id)
            .where(
                Cita.paciente_id == paciente_guardado.id,
                Cita.estado == "realizada",
            )
            .limit(1)
        )
        if tiene_valoracion_realizada is None:
            raise SeguimientoRequiereValoracion(
                "Debes reservar una valoración inicial antes de un seguimiento."
            )

    ahora_utc = _ahora_utc(ahora)
    inicio_utc = inicio.astimezone(timezone.utc)
    inicio_local = inicio_utc.astimezone(_ZONA_MADRID)

    try:
        huecos = obtener_huecos_libres(
            inicio_local.date(),
            profesional.id,
            tipo_sesion.id,
            ahora=ahora_utc,
        )
    except ValueError as error:
        raise HuecoNoDisponible(_MENSAJE_HUECO_NO_DISPONIBLE) from error

    hueco_solicitado = next(
        (
            (inicio_hueco, fin_hueco)
            for inicio_hueco, fin_hueco in huecos
            if inicio_hueco.astimezone(timezone.utc) == inicio_utc
        ),
        None,
    )
    if hueco_solicitado is None:
        raise HuecoNoDisponible(_MENSAJE_HUECO_NO_DISPONIBLE)

    codigo = secrets.token_urlsafe(_DURACION_CODIGO_BYTES)
    cita = Cita(
        profesional_id=profesional.id,
        paciente_id=paciente_guardado.id,
        tipo_sesion_id=tipo_sesion.id,
        inicio=hueco_solicitado[0].astimezone(timezone.utc),
        fin=hueco_solicitado[1].astimezone(timezone.utc),
        modalidad="presencial",
        estado="confirmada",
        hash_codigo_gestion=_hash_codigo(codigo),
    )
    db.session.add(cita)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if _es_conflicto_de_solapamiento(error):
            raise HuecoNoDisponible(_MENSAJE_HUECO_NO_DISPONIBLE) from error
        raise ErrorReserva("No se pudo completar la reserva.") from error

    return cita, codigo


def consultar_cita_por_codigo(codigo: str) -> CitaPublica:
    return _cita_publica(_buscar_cita_por_codigo(codigo))


def cancelar_cita_por_codigo(
    codigo: str,
    ahora: datetime | None = None,
) -> CitaPublica:
    cita = _buscar_cita_por_codigo(codigo)
    if cita.estado != "confirmada":
        raise CitaNoCancelable("La cita no se puede cancelar.")

    ahora_utc = _ahora_utc(ahora)
    inicio_utc = cita.inicio.astimezone(timezone.utc)
    if inicio_utc - ahora_utc < timedelta(hours=24):
        raise CitaNoCancelable(
            "La cita solo se puede cancelar con al menos 24 horas de antelación."
        )

    cita.estado = "cancelada"
    cita.cancelada_en = ahora_utc
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ErrorReserva("No se pudo completar la cancelación.") from error

    return _cita_publica(cita)
