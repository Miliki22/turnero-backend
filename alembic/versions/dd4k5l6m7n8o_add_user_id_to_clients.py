"""add user_id to clients

Revision ID: dd4k5l6m7n8o
Revises: cc3i4j5k6l7m
Create Date: 2026-04-18 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dd4k5l6m7n8o"
down_revision: Union[str, Sequence[str], None] = "cc3i4j5k6l7m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("clients", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_clients_user_id"), "clients", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_clients_user_id_users",
        "clients",
        "users",
        ["user_id"],
        ["id"],
    )

    op.execute(
        """
        INSERT INTO users (email, password_hash, role, is_active, created_at)
        SELECT
            CONCAT('legacy-client-', c.id, '@local.invalid') AS email,
            '!',
            'client',
            TRUE,
            NOW()
        FROM clients c
        WHERE c.user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE clients c
        SET user_id = u.id
        FROM users u
        WHERE u.email = CONCAT('legacy-client-', c.id, '@local.invalid')
          AND c.user_id IS NULL
        """
    )

    op.alter_column("clients", "user_id", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_clients_user_id_users", "clients", type_="foreignkey")
    op.drop_index(op.f("ix_clients_user_id"), table_name="clients")
    op.drop_column("clients", "user_id")
