from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202605120001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("access_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("chain", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("contract_address", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_asset_id", sa.String(length=255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_asset_id", name="uq_assets_provider_asset"),
    )
    op.create_index("ix_assets_lookup", "assets", ["type", "chain", "symbol"])
    op.create_table(
        "asset_aliases",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "provider_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.UniqueConstraint("asset_id", "kind", name="uq_provider_links_asset_kind"),
    )
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("price_native", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("native_symbol", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("baseline_price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_active_asset", "alerts", ["status", "asset_id"])
    op.create_table(
        "alert_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("alert_id", sa.BigInteger(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("price_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("percent_change", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("notification_status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("notification_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_index("ix_alerts_active_asset", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("price_snapshots")
    op.drop_table("provider_links")
    op.drop_table("asset_aliases")
    op.drop_index("ix_assets_lookup", table_name="assets")
    op.drop_table("assets")
    op.drop_table("users")
