from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.extensiones import db
from app.models import Cita, DisponibilidadSemanal, Paciente, Profesional, TipoSesion
from app.services.reservas import (
    CitaNoCancelable,
    CitaNoEncontrada,
    EmailNoVerificado,
    HuecoNoDisponible,
    SeguimientoRequiereValoracion,
    cancelar_cita_por_codigo,
    consultar_cita_por_codigo,
    crear_cita,
    obtener_o_crear_paciente,
)


_MADRID = ZoneInfo("Europe/Madrid")
_AHORA = datetime(2030, 1, 7, 8, 0, tzinfo=_MADRID)
_INICIO = datetime(2030, 1, 8, 10, 0, tzinfo=_MADRID)


@pytest.fixture
def datos_reserva(contexto_aplicacion):
    profesional = Profesional(
        nombre="Profesional de reservas",
        especialidad="Fisioterapia general",
        activo=True,
    )
    paciente = Paciente(
        nombre="Paciente de prueba",
        email="reservas@example.invalid",
        telefono="600000001",
        email_verificado=True,
    )
    db.session.add_all((profesional, paciente))
    db.session.flush()

    tipos = {
        tipo.nombre: tipo
        for tipo in db.session.scalars(
            select(TipoSesion).where(
                TipoSesion.nombre.in_(("valoración inicial", "seguimiento"))
            )
        ).all()
    }
    for dia_semana in range(5):
        db.session.add(
            DisponibilidadSemanal(
                profesional_id=profesional.id,
                dia_semana=dia_semana,
                hora_inicio=time(9, 0),
                hora_fin=time(12, 0),
            )
        )
    db.session.commit()

    return {
        "profesional_id": profesional.id,
        "paciente_id": paciente.id,
        "valoracion_id": tipos["valoración inicial"].id,
        "seguimiento_id": tipos["seguimiento"].id,
    }


def _crear_cita_realizada(datos, inicio=_AHORA + timedelta(hours=2)):
    db.session.add(
        Cita(
            profesional_id=datos["profesional_id"],
            paciente_id=datos["paciente_id"],
            tipo_sesion_id=datos["valoracion_id"],
            inicio=inicio,
            fin=inicio + timedelta(minutes=60),
            modalidad="presencial",
            estado="realizada",
            hash_codigo_gestion="hash-ficticio-de-cita-realizada",
        )
    )
    db.session.commit()


def _crear_reserva(
    datos,
    tipo_sesion_id=None,
    inicio=_INICIO,
    ahora=_AHORA,
):
    paciente = db.session.get(Paciente, datos["paciente_id"])
    profesional = db.session.get(Profesional, datos["profesional_id"])
    tipo_sesion = db.session.get(
        TipoSesion,
        tipo_sesion_id or datos["valoracion_id"],
    )
    return crear_cita(
        paciente=paciente,
        profesional=profesional,
        tipo_sesion=tipo_sesion,
        inicio=inicio,
        ahora=ahora,
    )


def test_reserva_correcta_de_valoracion_y_codigo_no_se_guarda_en_claro(datos_reserva):
    cita, codigo = _crear_reserva(datos_reserva)

    assert cita.estado == "confirmada"
    assert cita.modalidad == "presencial"
    assert cita.fin - cita.inicio == timedelta(minutes=60)
    assert cita.inicio.tzinfo is not None
    assert len(codigo) >= 40
    assert cita.hash_codigo_gestion != codigo
    assert cita.hash_codigo_gestion
    valores_guardados = tuple(
        str(getattr(cita, columna.name))
        for columna in Cita.__table__.columns
    )
    assert codigo not in valores_guardados


def test_reserva_correcta_de_seguimiento_con_cita_realizada(datos_reserva):
    _crear_cita_realizada(datos_reserva)

    cita, _ = _crear_reserva(
        datos_reserva,
        tipo_sesion_id=datos_reserva["seguimiento_id"],
    )

    assert cita.tipo_sesion_id == datos_reserva["seguimiento_id"]
    assert cita.fin - cita.inicio == timedelta(minutes=30)


def test_rechaza_seguimiento_sin_cita_realizada(datos_reserva):
    with pytest.raises(SeguimientoRequiereValoracion, match="valoración inicial"):
        _crear_reserva(
            datos_reserva,
            tipo_sesion_id=datos_reserva["seguimiento_id"],
        )


def test_acepta_seguimiento_si_existe_cita_realizada(datos_reserva):
    _crear_cita_realizada(datos_reserva)

    cita, _ = _crear_reserva(
        datos_reserva,
        tipo_sesion_id=datos_reserva["seguimiento_id"],
    )

    assert cita.estado == "confirmada"


def test_rechaza_reserva_con_email_no_verificado(datos_reserva):
    paciente = db.session.get(Paciente, datos_reserva["paciente_id"])
    paciente.email_verificado = False
    db.session.commit()

    with pytest.raises(EmailNoVerificado, match="Verifica tu email"):
        _crear_reserva(datos_reserva)


@pytest.mark.parametrize(
    ("inicio", "ahora"),
    (
        (_INICIO, datetime(2030, 1, 7, 23, 0, tzinfo=_MADRID)),
        (
            datetime(2030, 3, 11, 10, 0, tzinfo=_MADRID),
            _AHORA,
        ),
    ),
    ids=("menos-de-12-horas", "mas-de-60-dias"),
)
def test_rechaza_reserva_fuera_de_la_ventana_permitida(
    datos_reserva, inicio, ahora
):
    with pytest.raises(HuecoNoDisponible):
        _crear_reserva(datos_reserva, inicio=inicio, ahora=ahora)


@pytest.mark.parametrize(
    ("inicio", "id_mensaje"),
    (
        (
            datetime(2030, 1, 8, 10, 15, tzinfo=_MADRID),
            "fuera-de-franja",
        ),
        (
            datetime(2030, 1, 8, 12, 30, tzinfo=_MADRID),
            "fuera-de-disponibilidad",
        ),
    ),
)
def test_rechaza_inicio_fuera_de_los_huecos(datos_reserva, inicio, id_mensaje):
    with pytest.raises(HuecoNoDisponible):
        _crear_reserva(datos_reserva, inicio=inicio)


def test_reservas_simultaneas_del_mismo_hueco_solo_una_se_confirma(
    aplicacion, datos_reserva
):
    segundo_paciente = Paciente(
        nombre="Otro paciente ficticio",
        email="otro-reservas@example.invalid",
        telefono="600000002",
        email_verificado=True,
    )
    db.session.add(segundo_paciente)
    db.session.commit()
    ids_pacientes = (datos_reserva["paciente_id"], segundo_paciente.id)
    barrera = Barrier(2)

    def reservar(id_paciente):
        with aplicacion.app_context():
            try:
                paciente = db.session.get(Paciente, id_paciente)
                profesional = db.session.get(
                    Profesional, datos_reserva["profesional_id"]
                )
                tipo_sesion = db.session.get(
                    TipoSesion, datos_reserva["valoracion_id"]
                )
                barrera.wait(timeout=10)
                crear_cita(
                    paciente=paciente,
                    profesional=profesional,
                    tipo_sesion=tipo_sesion,
                    inicio=_INICIO,
                    ahora=_AHORA,
                )
                return "confirmada"
            except HuecoNoDisponible:
                return "El hueco ya no está disponible."
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(reservar, ids_pacientes))

    assert sorted(resultados) == ["El hueco ya no está disponible.", "confirmada"]


def test_consulta_cita_con_codigo_correcto_no_incluye_datos_personales(
    datos_reserva,
):
    _, codigo = _crear_reserva(datos_reserva)

    consulta = consultar_cita_por_codigo(codigo)

    assert consulta.fecha == _INICIO.date()
    assert consulta.hora == _INICIO.timetz().replace(tzinfo=None)
    assert consulta.tipo_sesion == "valoración inicial"
    assert consulta.modalidad == "presencial"
    assert consulta.estado == "confirmada"
    assert not hasattr(consulta, "nombre")
    assert not hasattr(consulta, "email")
    assert not hasattr(consulta, "telefono")


def test_consulta_cita_con_codigo_incorrecto(datos_reserva):
    with pytest.raises(CitaNoEncontrada):
        consultar_cita_por_codigo("codigo-ficticio-invalido")


@pytest.mark.parametrize(
    "codigo",
    ("", None, 123, "x" * 257),
    ids=("vacio", "nulo", "no-textual", "demasiado-largo"),
)
def test_codigo_mal_formado_usa_el_mismo_error_generico(codigo):
    with pytest.raises(CitaNoEncontrada) as error:
        consultar_cita_por_codigo(codigo)

    assert str(error.value) == "No se encontró una cita con ese código."


def test_busqueda_por_codigo_encuentra_la_cita_correcta_entre_varias(
    datos_reserva,
):
    _, codigo_correcto = _crear_reserva(datos_reserva)
    cita_correcta = db.session.scalar(select(Cita))

    segundo_paciente = Paciente(
        nombre="Paciente adicional",
        email="adicional@example.invalid",
        telefono="600000003",
        email_verificado=True,
    )
    db.session.add(segundo_paciente)
    db.session.flush()
    otra_cita = Cita(
        profesional_id=datos_reserva["profesional_id"],
        paciente_id=segundo_paciente.id,
        tipo_sesion_id=datos_reserva["valoracion_id"],
        inicio=datetime(2030, 1, 8, 11, 0, tzinfo=_MADRID),
        fin=datetime(2030, 1, 8, 12, 0, tzinfo=_MADRID),
        modalidad="presencial",
        estado="confirmada",
        hash_codigo_gestion="hash-ficticio-distinto",
    )
    db.session.add(otra_cita)
    db.session.commit()

    consulta = consultar_cita_por_codigo(codigo_correcto)

    assert consulta.hora == _INICIO.timetz().replace(tzinfo=None)
    assert cita_correcta.hash_codigo_gestion != otra_cita.hash_codigo_gestion


def test_indice_unico_de_hash_existe():
    indices = {indice["name"]: indice for indice in inspect(db.engine).get_indexes("cita")}

    assert "uq_cita_hash_codigo_gestion" in indices
    assert indices["uq_cita_hash_codigo_gestion"]["unique"] is True
    assert indices["uq_cita_hash_codigo_gestion"]["column_names"] == [
        "hash_codigo_gestion"
    ]


def test_indice_unico_rechaza_hashes_duplicados(datos_reserva):
    primera = Cita(
        profesional_id=datos_reserva["profesional_id"],
        paciente_id=datos_reserva["paciente_id"],
        tipo_sesion_id=datos_reserva["valoracion_id"],
        inicio=_INICIO,
        fin=_INICIO + timedelta(minutes=60),
        modalidad="presencial",
        estado="confirmada",
        hash_codigo_gestion="hash-duplicado-ficticio",
    )
    db.session.add(primera)
    db.session.commit()

    duplicada = Cita(
        profesional_id=datos_reserva["profesional_id"],
        paciente_id=datos_reserva["paciente_id"],
        tipo_sesion_id=datos_reserva["valoracion_id"],
        inicio=datetime(2030, 1, 8, 11, 0, tzinfo=_MADRID),
        fin=datetime(2030, 1, 8, 12, 0, tzinfo=_MADRID),
        modalidad="presencial",
        estado="confirmada",
        hash_codigo_gestion="hash-duplicado-ficticio",
    )
    db.session.add(duplicada)

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_cancelar_cita_con_mas_de_24_horas(datos_reserva):
    _, codigo = _crear_reserva(datos_reserva)
    ahora = _INICIO - timedelta(hours=25)

    cita_publica = cancelar_cita_por_codigo(codigo, ahora=ahora)

    cita = db.session.scalar(select(Cita))
    assert cita_publica.estado == "cancelada"
    assert cita.estado == "cancelada"
    assert cita.cancelada_en == ahora.astimezone(timezone.utc)


def test_rechaza_cancelacion_con_menos_de_24_horas(datos_reserva):
    _, codigo = _crear_reserva(datos_reserva)
    ahora = _INICIO - timedelta(hours=23, minutes=59)

    with pytest.raises(CitaNoCancelable, match="24 horas"):
        cancelar_cita_por_codigo(codigo, ahora=ahora)


def test_cita_cancelada_libera_el_hueco(datos_reserva):
    _, codigo = _crear_reserva(datos_reserva)
    cancelar_cita_por_codigo(codigo, ahora=_AHORA)

    nueva_cita, _ = _crear_reserva(datos_reserva)

    assert nueva_cita.inicio == _INICIO.astimezone(timezone.utc)
    assert nueva_cita.estado == "confirmada"


def test_no_se_puede_cancelar_una_cita_dos_veces(datos_reserva):
    _, codigo = _crear_reserva(datos_reserva)
    cancelar_cita_por_codigo(codigo, ahora=_AHORA)

    with pytest.raises(CitaNoCancelable, match="no se puede cancelar"):
        cancelar_cita_por_codigo(codigo, ahora=_AHORA)


def test_obtener_paciente_existente_no_sobrescribe_sus_datos(contexto_aplicacion):
    paciente = obtener_o_crear_paciente(
        "Nombre original",
        "Original@example.invalid",
        "600000010",
    )
    paciente_id = paciente.id
    db.session.commit()

    existente = obtener_o_crear_paciente(
        "Nombre nuevo",
        "original@example.invalid",
        "600000099",
    )

    assert existente.id == paciente_id
    assert existente.nombre == "Nombre original"
    assert existente.email == "original@example.invalid"
    assert existente.telefono == "600000010"


def test_nuevo_paciente_se_crea_con_email_no_verificado(contexto_aplicacion):
    paciente = obtener_o_crear_paciente(
        "Paciente nuevo",
        "nuevo@example.invalid",
        "600000011",
    )

    assert paciente.email_verificado is False


def test_indice_unico_de_email_normalizado_existe():
    indices = {
        indice["name"]: indice
        for indice in inspect(db.engine).get_indexes("paciente")
    }

    assert "uq_paciente_email_lower" in indices
    indice_email = indices["uq_paciente_email_lower"]
    assert indice_email["unique"] is True
    assert indice_email["column_names"] == [None]
    expresion = indice_email["expressions"][0]
    assert expresion.startswith("lower(email")


def test_base_de_datos_rechaza_emails_que_difieren_en_mayusculas(
    contexto_aplicacion,
):
    db.session.add(
        Paciente(
            nombre="Paciente original",
            email="duplicado@example.invalid",
            telefono="600000012",
            email_verificado=False,
        )
    )
    db.session.commit()
    db.session.add(
        Paciente(
            nombre="Paciente duplicado",
            email="DUPLICADO@example.invalid",
            telefono="600000013",
            email_verificado=False,
        )
    )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_creacion_concurrente_con_mismo_email_devuelve_un_paciente(
    aplicacion,
    contexto_aplicacion,
):
    barrera = Barrier(2)

    def crear(nombre, telefono):
        with aplicacion.app_context():
            try:
                barrera.wait(timeout=10)
                paciente = obtener_o_crear_paciente(
                    nombre,
                    "carrera@example.invalid",
                    telefono,
                )
                return paciente.id
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        ids_pacientes = list(
            ejecutor.map(
                lambda datos: crear(*datos),
                (
                    ("Paciente concurrente A", "600000014"),
                    ("Paciente concurrente B", "600000015"),
                ),
            )
        )

    assert ids_pacientes[0] == ids_pacientes[1]
    assert (
        db.session.scalar(
            select(db.func.count())
            .select_from(Paciente)
            .where(db.func.lower(Paciente.email) == "carrera@example.invalid")
        )
        == 1
    )
