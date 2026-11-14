"""Añade un índice único al hash del código de gestión.

Revision ID: 20261114_01
Revises: 20261113_01
Create Date: 2026-11-14

"""
from alembic import op


revision = "20261114_01"
down_revision = "20261113_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_cita_hash_codigo_gestion",
        "cita",
        ["hash_codigo_gestion"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_cita_hash_codigo_gestion", table_name="cita")
