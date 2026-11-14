"""Añade unicidad al email sin distinguir mayúsculas.

Revision ID: 20261114_02
Revises: 20261114_01
Create Date: 2026-11-14

"""
from alembic import op
import sqlalchemy as sa


revision = "20261114_02"
down_revision = "20261114_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_paciente_email_lower",
        "paciente",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_paciente_email_lower", table_name="paciente")
