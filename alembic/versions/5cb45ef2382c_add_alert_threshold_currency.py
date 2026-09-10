"""add alert threshold currency

Revision ID: 5cb45ef2382c
Revises: f23d5634ec96
Create Date: 2026-09-10 20:39:40.036808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cb45ef2382c'
down_revision: Union[str, Sequence[str], None] = 'f23d5634ec96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
