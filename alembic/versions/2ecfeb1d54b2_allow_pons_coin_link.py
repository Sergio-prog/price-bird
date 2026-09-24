"""allow pons coin link

Revision ID: 2ecfeb1d54b2
Revises: 44989df52b1f
Create Date: 2026-09-25 02:23:24.049034

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ecfeb1d54b2"
down_revision: str | Sequence[str] | None = "44989df52b1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREVIOUS_LINKS = "'tradingview', 'dexscreener', 'gmgn', 'fomo', 'coinmarketcap', 'explorer'"
CURRENT_LINKS = f"{PREVIOUS_LINKS}, 'pons'"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_users_coin_links", "users", type_="check")
    op.create_check_constraint("ck_users_coin_links", "users", f"coin_links <@ ARRAY[{CURRENT_LINKS}]::varchar[]")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE users SET coin_links = array_remove(coin_links, 'pons')")
    op.drop_constraint("ck_users_coin_links", "users", type_="check")
    op.create_check_constraint("ck_users_coin_links", "users", f"coin_links <@ ARRAY[{PREVIOUS_LINKS}]::varchar[]")
