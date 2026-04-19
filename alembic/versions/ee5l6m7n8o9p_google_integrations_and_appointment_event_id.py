"""google integrations and appointment event id

Revision ID: ee5l6m7n8o9p
Revises: dd4k5l6m7n8o
Create Date: 2026-04-19 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ee5l6m7n8o9p"
down_revision: Union[str, Sequence[str], None] = "dd4k5l6m7n8o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("appointments", sa.Column("google_event_id", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_appointments_google_event_id"), "appointments", ["google_event_id"], unique=False)

    op.create_table(
        "google_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token", sa.String(length=2048), nullable=False),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_google_integrations_user_id"), "google_integrations", ["user_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_google_integrations_user_id"), table_name="google_integrations")
    op.drop_table("google_integrations")

    op.drop_index(op.f("ix_appointments_google_event_id"), table_name="appointments")
    op.drop_column("appointments", "google_event_id")
