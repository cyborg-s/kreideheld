"""Add a required password hash to accounts.

Revision ID: 20260923_03
Revises: 20260923_02
Create Date: 2026-09-30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_03"
down_revision: Union[str, Sequence[str], None] = "20260923_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("accounts", recreate="always") as batch_op:
        batch_op.drop_column("password_hash")
