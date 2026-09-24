"""store multiple coin links

Revision ID: 62679a483e93
Revises: 207d0afe3715
Create Date: 2026-09-25 01:32:32.988543

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "62679a483e93"
down_revision: str | Sequence[str] | None = "207d0afe3715"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COIN_LINKS = "'tradingview', 'dexscreener', 'gmgn', 'fomo', 'coinmarketcap'"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "coin_links",
            postgresql.ARRAY(sa.String(length=32)),
            server_default=sa.text("'{dexscreener}'::varchar[]"),
            nullable=False,
        ),
    )
    op.execute("UPDATE users SET coin_links = ARRAY[coin_link]::varchar[]")
    op.create_check_constraint("ck_users_coin_links", "users", f"coin_links <@ ARRAY[{COIN_LINKS}]::varchar[]")
    op.drop_constraint("ck_users_coin_link", "users", type_="check")
    op.drop_column("users", "coin_link")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "users",
        sa.Column("coin_link", sa.String(length=32), server_default="dexscreener", nullable=False),
    )
    op.execute("UPDATE users SET coin_link = COALESCE(coin_links[1], 'dexscreener')")
    op.create_check_constraint("ck_users_coin_link", "users", f"coin_link IN ({COIN_LINKS})")
    op.drop_constraint("ck_users_coin_links", "users", type_="check")
    op.drop_column("users", "coin_links")
