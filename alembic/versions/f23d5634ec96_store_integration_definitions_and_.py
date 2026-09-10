"""store integration definitions and secrets

Revision ID: f23d5634ec96
Revises: fa283d730c35
Create Date: 2026-09-10 15:43:17.142347

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f23d5634ec96"
down_revision: str | Sequence[str] | None = "fa283d730c35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("webhook_path", sa.String(255), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_integration_definitions_slug", "integration_definitions", ["slug"], unique=True)
    op.add_column("connected_apps", sa.Column("integration_definition_id", sa.String(36)))
    op.add_column("connected_apps", sa.Column("secret_encrypted", sa.Text()))
    op.create_foreign_key(
        "fk_connected_apps_integration_definition_id",
        "connected_apps",
        "integration_definitions",
        ["integration_definition_id"],
        ["id"],
    )
    op.create_index(
        "ix_connected_apps_integration_definition_id",
        "connected_apps",
        ["integration_definition_id"],
    )
    op.create_unique_constraint(
        "uq_connected_apps_user_integration",
        "connected_apps",
        ["user_id", "integration_definition_id"],
    )
    op.alter_column("connected_apps", "url", existing_type=sa.Text(), nullable=True)
    for table, column in (
        ("alert_events", "alert_id"),
        ("alerts", "asset_id"),
        ("alerts", "user_id"),
        ("price_snapshots", "asset_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    # Previous releases derived or read secrets from process environment. They cannot be
    # migrated safely, so require users to reconnect or the operator to adopt Trenchbook
    # connections with the setup command.
    op.execute("UPDATE connected_apps SET enabled = false")


def downgrade() -> None:
    for table, column in (
        ("price_snapshots", "asset_id"),
        ("alerts", "user_id"),
        ("alerts", "asset_id"),
        ("alert_events", "alert_id"),
    ):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
    op.execute(
        """
        UPDATE connected_apps AS connection
        SET url = definition.base_url || '/' || ltrim(definition.webhook_path, '/')
        FROM integration_definitions AS definition
        WHERE connection.integration_definition_id = definition.id
        """
    )
    op.alter_column("connected_apps", "url", existing_type=sa.Text(), nullable=False)
    op.drop_constraint("uq_connected_apps_user_integration", "connected_apps", type_="unique")
    op.drop_index("ix_connected_apps_integration_definition_id", table_name="connected_apps")
    op.drop_constraint("fk_connected_apps_integration_definition_id", "connected_apps", type_="foreignkey")
    op.drop_column("connected_apps", "secret_encrypted")
    op.drop_column("connected_apps", "integration_definition_id")
    op.drop_index("ix_integration_definitions_slug", table_name="integration_definitions")
    op.drop_table("integration_definitions")
