"""create appointments table

Revision ID: cc3i4j5k6l7m
Revises: bb2g3h4i5j6k
Create Date: 2026-04-08 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cc3i4j5k6l7m"
down_revision: Union[str, Sequence[str], None] = "bb2g3h4i5j6k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appointments_client_id"), "appointments", ["client_id"], unique=False)
    op.create_index(op.f("ix_appointments_service_id"), "appointments", ["service_id"], unique=False)
    op.create_index(op.f("ix_appointments_start_at"), "appointments", ["start_at"], unique=False)
    op.create_index(op.f("ix_appointments_end_at"), "appointments", ["end_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_appointments_end_at"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_start_at"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_service_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_client_id"), table_name="appointments")
    op.drop_table("appointments")
