from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensiones import db


class Profesional(db.Model):
    __tablename__ = "profesional"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    especialidad: Mapped[str] = mapped_column(String(120), nullable=False)
    activo: Mapped[bool] = mapped_column(nullable=False, default=True)

    disponibilidades: Mapped[list["DisponibilidadSemanal"]] = relationship(
        back_populates="profesional"
    )
    bloqueos: Mapped[list["Bloqueo"]] = relationship(back_populates="profesional")
    citas: Mapped[list["Cita"]] = relationship(back_populates="profesional")


class Paciente(db.Model):
    __tablename__ = "paciente"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    telefono: Mapped[str] = mapped_column(String(32), nullable=False)
    email_verificado: Mapped[bool] = mapped_column(nullable=False, default=False)
    identificador_clerk: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    citas: Mapped[list["Cita"]] = relationship(back_populates="paciente")


class TipoSesion(db.Model):
    __tablename__ = "tipo_sesion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool] = mapped_column(nullable=False, default=True)

    citas: Mapped[list["Cita"]] = relationship(back_populates="tipo_sesion")


class DisponibilidadSemanal(db.Model):
    __tablename__ = "disponibilidad_semanal"
    __table_args__ = (
        CheckConstraint(
            "dia_semana BETWEEN 0 AND 6", name="ck_disponibilidad_dia_semana"
        ),
        CheckConstraint("hora_fin > hora_inicio", name="ck_disponibilidad_horario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profesional_id: Mapped[int] = mapped_column(
        ForeignKey("profesional.id"), nullable=False
    )
    dia_semana: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0=lunes, 6=domingo"
    )
    hora_inicio: Mapped[time] = mapped_column(
        Time(timezone=False), nullable=False, comment="Hora local de Europe/Madrid"
    )
    hora_fin: Mapped[time] = mapped_column(
        Time(timezone=False), nullable=False, comment="Hora local de Europe/Madrid"
    )

    profesional: Mapped["Profesional"] = relationship(
        back_populates="disponibilidades"
    )


class Bloqueo(db.Model):
    __tablename__ = "bloqueo"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="ck_bloqueo_horario"),
        CheckConstraint(
            "motivo IN ('vacaciones', 'festivo', 'descanso')",
            name="ck_bloqueo_motivo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profesional_id: Mapped[int] = mapped_column(
        ForeignKey("profesional.id"), nullable=False
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)

    profesional: Mapped["Profesional"] = relationship(back_populates="bloqueos")


class Cita(db.Model):
    __tablename__ = "cita"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="ck_cita_horario"),
        CheckConstraint(
            "EXTRACT(MINUTE FROM inicio) % 30 = 0 "
            "AND EXTRACT(SECOND FROM inicio) = 0 "
            "AND EXTRACT(EPOCH FROM (fin - inicio)) % 1800 = 0",
            name="ck_cita_franjas_30_minutos",
        ),
        CheckConstraint(
            "modalidad IN ('presencial')", name="ck_cita_modalidad"
        ),
        CheckConstraint(
            "estado IN ('confirmada', 'cancelada', 'realizada', 'ausente')",
            name="ck_cita_estado",
        ),
        ExcludeConstraint(
            ("profesional_id", "="),
            (literal_column("tstzrange(inicio, fin, '[)')"), "&&"),
            where=text("estado <> 'cancelada'"),
            using="gist",
            name="ex_cita_profesional_horario_activo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profesional_id: Mapped[int] = mapped_column(
        ForeignKey("profesional.id"), nullable=False
    )
    paciente_id: Mapped[int] = mapped_column(ForeignKey("paciente.id"), nullable=False)
    tipo_sesion_id: Mapped[int] = mapped_column(
        ForeignKey("tipo_sesion.id"), nullable=False
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modalidad: Mapped[str] = mapped_column(
        String(20), nullable=False, default="presencial"
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmada"
    )
    hash_codigo_gestion: Mapped[str] = mapped_column(String(255), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profesional: Mapped["Profesional"] = relationship(back_populates="citas")
    paciente: Mapped["Paciente"] = relationship(back_populates="citas")
    tipo_sesion: Mapped["TipoSesion"] = relationship(back_populates="citas")
