"""Migrate accounts to the identity and role model.

Revision ID: 20260923_02
Revises: 20260923_01
Create Date: 2026-09-23

"""

import re
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260923_02"
down_revision: Union[str, Sequence[str], None] = "20260923_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_VALUES = ("OWNER", "ADMIN", "EMPLOYEE")
ACCOUNT_ID_PATTERN = re.compile(r"[A-Z]{2}-\d{6}")


def legacy_account_role() -> str | None:
    connection = op.get_bind()
    codes = connection.execute(sa.text("SELECT code FROM accounts")).scalars().all()

    invalid_codes = [code for code in codes if not ACCOUNT_ID_PATTERN.fullmatch(code)]
    if invalid_codes:
        raise RuntimeError(
            "Cannot migrate accounts whose codes do not match the required account ID format."
        )

    if not codes:
        return None

    role = context.get_x_argument(as_dictionary=True).get("legacy_account_role")
    if role not in ROLE_VALUES:
        raise RuntimeError(
            "Historical accounts require an explicit -x legacy_account_role=EMPLOYEE decision."
        )
    if role != "EMPLOYEE":
        raise RuntimeError(
            "Historical accounts have no email and therefore cannot be migrated as OWNER or ADMIN."
        )
    return role


def upgrade() -> None:
    role = legacy_account_role()
    account_role_type = sa.Enum(
        *ROLE_VALUES,
        name="accountrole",
        native_enum=False,
        create_constraint=True,
    )

    with op.batch_alter_table("accounts", recreate="always") as batch_op:
        batch_op.drop_index("ix_accounts_code")
        batch_op.drop_index("ix_accounts_tenant_id")
        batch_op.alter_column(
            "code",
            new_column_name="account_id",
            existing_type=sa.String(length=50),
            type_=sa.String(length=9),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "display_name",
            new_column_name="name",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "role",
                account_role_type,
                nullable=False,
                server_default=role or "EMPLOYEE",
            )
        )
        batch_op.add_column(
            sa.Column(
                "password_change_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.create_check_constraint(
            "ck_accounts_privileged_email",
            "role = 'EMPLOYEE' OR email IS NOT NULL",
        )

    with op.batch_alter_table("accounts", recreate="always") as batch_op:
        batch_op.alter_column("role", server_default=None, existing_type=account_role_type)
        batch_op.alter_column(
            "password_change_required",
            server_default=None,
            existing_type=sa.Boolean(),
        )

    op.create_index("ix_accounts_account_id", "accounts", ["account_id"], unique=True)
    op.create_index("ix_accounts_email", "accounts", ["email"], unique=True)
    op.create_index("ix_accounts_tenant_id", "accounts", ["tenant_id"], unique=False)


def downgrade() -> None:
    account_role_type = sa.Enum(
        *ROLE_VALUES,
        name="accountrole",
        native_enum=False,
        create_constraint=True,
    )

    with op.batch_alter_table("accounts", recreate="always") as batch_op:
        batch_op.drop_index("ix_accounts_account_id")
        batch_op.drop_index("ix_accounts_email")
        batch_op.drop_index("ix_accounts_tenant_id")
        batch_op.drop_constraint("ck_accounts_privileged_email", type_="check")
        batch_op.drop_constraint("accountrole", type_="check")
        batch_op.alter_column(
            "account_id",
            new_column_name="code",
            existing_type=sa.String(length=9),
            type_=sa.String(length=50),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "name",
            new_column_name="display_name",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.drop_column("password_change_required")
        batch_op.drop_column("role")
        batch_op.drop_column("email")

    op.create_index("ix_accounts_code", "accounts", ["code"], unique=True)
    op.create_index("ix_accounts_tenant_id", "accounts", ["tenant_id"], unique=False)
