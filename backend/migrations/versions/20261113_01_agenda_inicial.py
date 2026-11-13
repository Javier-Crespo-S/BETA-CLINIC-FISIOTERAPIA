"""Crea el esquema inicial de la agenda.

Revision ID: 20261113_01
Revises:
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa


revision = "20261113_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "paciente",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("telefono", sa.String(length=32), nullable=False),
        sa.Column("email_verificado", sa.Boolean(), nullable=False),
        sa.Column("identificador_clerk", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identificador_clerk"),
    )
    op.create_table(
        "profesional",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("especialidad", sa.String(length=120), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tipo_sesion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("duracion_minutos", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.bulk_insert(
        sa.table(
            "tipo_sesion",
            sa.column("nombre", sa.String()),
            sa.column("duracion_minutos", sa.Integer()),
            sa.column("activo", sa.Boolean()),
        ),
        [
            {
                "nombre": "valoración inicial",
                "duracion_minutos": 60,
                "activo": True,
            },
            {"nombre": "seguimiento", "duracion_minutos": 30, "activo": True},
        ],
    )
    op.create_table(
        "bloqueo",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profesional_id", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.String(length=20), nullable=False),
        sa.CheckConstraint("fin > inicio", name="ck_bloqueo_horario"),
        sa.CheckConstraint(
            "motivo IN ('vacaciones', 'festivo', 'descanso')",
            name="ck_bloqueo_motivo",
        ),
        sa.ForeignKeyConstraint(["profesional_id"], ["profesional.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "disponibilidad_semanal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profesional_id", sa.Integer(), nullable=False),
        sa.Column(
            "dia_semana",
            sa.Integer(),
            nullable=False,
            comment="0=lunes, 6=domingo",
        ),
        sa.Column(
            "hora_inicio",
            sa.Time(timezone=False),
            nullable=False,
            comment="Hora local de Europe/Madrid",
        ),
        sa.Column(
            "hora_fin",
            sa.Time(timezone=False),
            nullable=False,
            comment="Hora local de Europe/Madrid",
        ),
        sa.CheckConstraint(
            "dia_semana BETWEEN 0 AND 6", name="ck_disponibilidad_dia_semana"
        ),
        sa.CheckConstraint("hora_fin > hora_inicio", name="ck_disponibilidad_horario"),
        sa.ForeignKeyConstraint(["profesional_id"], ["profesional.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cita",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profesional_id", sa.Integer(), nullable=False),
        sa.Column("paciente_id", sa.Integer(), nullable=False),
        sa.Column("tipo_sesion_id", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "modalidad", sa.String(length=20), nullable=False, default="presencial"
        ),
        sa.Column(
            "estado", sa.String(length=20), nullable=False, default="confirmada"
        ),
        sa.Column("hash_codigo_gestion", sa.String(length=255), nullable=False),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("fin > inicio", name="ck_cita_horario"),
        sa.CheckConstraint(
            "EXTRACT(MINUTE FROM inicio) % 30 = 0 "
            "AND EXTRACT(SECOND FROM inicio) = 0 "
            "AND EXTRACT(EPOCH FROM (fin - inicio)) % 1800 = 0",
            name="ck_cita_franjas_30_minutos",
        ),
        sa.CheckConstraint(
            "modalidad IN ('presencial')", name="ck_cita_modalidad"
        ),
        sa.CheckConstraint(
            "estado IN ('confirmada', 'cancelada', 'realizada', 'ausente')",
            name="ck_cita_estado",
        ),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"]),
        sa.ForeignKeyConstraint(["profesional_id"], ["profesional.id"]),
        sa.ForeignKeyConstraint(["tipo_sesion_id"], ["tipo_sesion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        ALTER TABLE cita
        ADD CONSTRAINT ex_cita_profesional_horario_activo
        EXCLUDE USING gist (
            profesional_id WITH =,
            tstzrange(inicio, fin, '[)') WITH &&
        )
        WHERE (estado <> 'cancelada')
        """
    )


def downgrade():
    op.drop_table("cita")
    op.drop_table("disponibilidad_semanal")
    op.drop_table("bloqueo")
    op.drop_table("tipo_sesion")
    op.drop_table("profesional")
    op.drop_table("paciente")
