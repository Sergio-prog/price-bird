"""add connected apps and durable deliveries

Revision ID: fa283d730c35
Revises: 202605120001
Create Date: 2026-09-10 02:29:00.515274

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "fa283d730c35"
down_revision: Union[str, Sequence[str], None] = "202605120001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bird_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("alerts", sa.Column("repeat", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("alerts", sa.Column("armed", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("alerts", sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="900"))
    op.add_column("alerts", sa.Column("last_triggered_at", sa.DateTime(timezone=True)))
    op.add_column("alerts", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("alerts", sa.Column("note", sa.String(300)))
    op.execute("UPDATE alerts SET repeat = true WHERE type = 'percent_change'")
    op.create_table(
        "connected_apps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("secret_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_connected_apps_user_id", "connected_apps", ["user_id"])
    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("alert_events.id")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("connected_apps.id")),
        sa.Column("destination", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("leased_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_id", "destination", name="uq_delivery_event_destination"),
    )
    op.create_index("ix_delivery_due", "deliveries", ["status", "next_attempt_at"])
    op.create_index("ix_deliveries_user_id", "deliveries", ["user_id"])
    for table, columns in {
        "alerts": ["baseline_price", "threshold_value"],
        "price_snapshots": ["price_usd", "price_native"],
    }.items():
        for column in columns:
            op.alter_column(table, column, type_=sa.Numeric(78, 36), existing_type=sa.Numeric(28, 10))


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_table("connected_apps")
    for column in ("note", "expires_at", "last_triggered_at", "cooldown_seconds", "armed", "repeat"):
        op.drop_column("alerts", column)
    op.drop_column("users", "bird_enabled")
    # Preserve widened precision: narrowing it can destroy legitimate small prices.
