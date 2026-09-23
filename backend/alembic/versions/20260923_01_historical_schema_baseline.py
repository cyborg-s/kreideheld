"""Baseline for the historical SQLite schema.

Revision ID: 20260923_01
Revises:
Create Date: 2026-09-23

This revision represents the schema present before the account identity and
role model was introduced. It is not applied by this change.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("unit_preference", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_email", "tenants", ["email"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_code", "accounts", ["code"], unique=True)
    op.create_index("ix_accounts_tenant_id", "accounts", ["tenant_id"], unique=False)

    op.create_table(
        "rest_type_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("measure_fields", sa.JSON(), nullable=False),
        sa.Column("accepted_rotated_input", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rest_type_definitions_tenant_id", "rest_type_definitions", ["tenant_id"], unique=False)

    op.create_table(
        "rest_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("rest_type_id", sa.String(length=36), nullable=False),
        sa.Column("chalk_number", sa.String(length=50), nullable=False),
        sa.Column("material_name", sa.String(length=255), nullable=False),
        sa.Column("length_mm", sa.Integer(), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("rest_meter_mm", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["rest_type_id"], ["rest_type_definitions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rest_items_chalk_number", "rest_items", ["chalk_number"], unique=False)
    op.create_index("ix_rest_items_rest_type_id", "rest_items", ["rest_type_id"], unique=False)
    op.create_index("ix_rest_items_tenant_id", "rest_items", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rest_items_tenant_id", table_name="rest_items")
    op.drop_index("ix_rest_items_rest_type_id", table_name="rest_items")
    op.drop_index("ix_rest_items_chalk_number", table_name="rest_items")
    op.drop_table("rest_items")
    op.drop_index("ix_rest_type_definitions_tenant_id", table_name="rest_type_definitions")
    op.drop_table("rest_type_definitions")
    op.drop_index("ix_accounts_tenant_id", table_name="accounts")
    op.drop_index("ix_accounts_code", table_name="accounts")
    op.drop_table("accounts")
    op.drop_index("ix_tenants_email", table_name="tenants")
    op.drop_table("tenants")
