"""add user notification preferences

Revision ID: 2b9f275a34e2
Revises: 3e9003da14be
Create Date: 2026-09-15 16:16:50.725177

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b9f275a34e2"
down_revision: str | Sequence[str] | None = "3e9003da14be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("quiet_hours_start", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("quiet_hours_end", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("timezone_offset_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("coin_link", sa.String(length=32), server_default="dexscreener", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_quiet_hours_start",
        "users",
        "quiet_hours_start IS NULL OR quiet_hours_start BETWEEN 0 AND 23",
    )
    op.create_check_constraint(
        "ck_users_quiet_hours_end",
        "users",
        "quiet_hours_end IS NULL OR quiet_hours_end BETWEEN 0 AND 23",
    )
    op.create_check_constraint(
        "ck_users_timezone_offset_minutes",
        "users",
        "timezone_offset_minutes BETWEEN -720 AND 840",
    )
    op.create_check_constraint(
        "ck_users_coin_link",
        "users",
        "coin_link IN ('tradingview', 'dexscreener', 'gmgn', 'fomo', 'coinmarketcap')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_coin_link", "users", type_="check")
    op.drop_constraint("ck_users_timezone_offset_minutes", "users", type_="check")
    op.drop_constraint("ck_users_quiet_hours_end", "users", type_="check")
    op.drop_constraint("ck_users_quiet_hours_start", "users", type_="check")
    op.drop_column("users", "coin_link")
    op.drop_column("users", "timezone_offset_minutes")
    op.drop_column("users", "quiet_hours_end")
    op.drop_column("users", "quiet_hours_start")
