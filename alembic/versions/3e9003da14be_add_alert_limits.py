"""add alert limits

Revision ID: 3e9003da14be
Revises: 0a20889170e5
Create Date: 2026-09-15 01:40:15.724174

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e9003da14be"
down_revision: str | Sequence[str] | None = "0a20889170e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    alert_limits = op.create_table(
        "alert_limits",
        sa.Column("asset_kind", sa.String(16), primary_key=True),
        sa.Column("max_watched_assets", sa.Integer(), nullable=False),
        sa.Column("max_active_alerts", sa.Integer(), nullable=False),
        sa.Column("default_user_max_alerts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "max_watched_assets >= 0 AND max_active_alerts >= 0 AND default_user_max_alerts >= 0",
            name="ck_alert_limits_non_negative",
        ),
    )
    op.bulk_insert(
        alert_limits,
        [
            {"asset_kind": "token", "max_watched_assets": 200, "max_active_alerts": 5000, "default_user_max_alerts": 20},
            {"asset_kind": "nft", "max_watched_assets": 5, "max_active_alerts": 500, "default_user_max_alerts": 5},
        ],
    )
    op.create_table(
        "user_alert_limits",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "asset_kind",
            sa.String(16),
            sa.ForeignKey("alert_limits.asset_kind", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("max_alerts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_alerts >= 0", name="ck_user_alert_limits_non_negative"),
    )


def downgrade() -> None:
    op.drop_table("user_alert_limits")
    op.drop_table("alert_limits")
