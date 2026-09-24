"""allow explorer coin link

Revision ID: 44989df52b1f
Revises: 62679a483e93
Create Date: 2026-09-25 01:45:02.078811

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44989df52b1f"
down_revision: str | Sequence[str] | None = "62679a483e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREVIOUS_LINKS = "'tradingview', 'dexscreener', 'gmgn', 'fomo', 'coinmarketcap'"
CURRENT_LINKS = f"{PREVIOUS_LINKS}, 'explorer'"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_users_coin_links", "users", type_="check")
    op.create_check_constraint("ck_users_coin_links", "users", f"coin_links <@ ARRAY[{CURRENT_LINKS}]::varchar[]")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE users SET coin_links = array_remove(coin_links, 'explorer')")
    op.drop_constraint("ck_users_coin_links", "users", type_="check")
    op.create_check_constraint("ck_users_coin_links", "users", f"coin_links <@ ARRAY[{PREVIOUS_LINKS}]::varchar[]")
