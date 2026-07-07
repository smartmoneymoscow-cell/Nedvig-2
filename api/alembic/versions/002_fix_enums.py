"""No-op — enum fix not needed (models use String columns via EnumString).

Revision ID: 002
Revises: 001
Create Date: 2025-07-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: models use EnumString (VARCHAR columns), not PG native enums.
    # Migration 001 already creates String columns for source/status/type.
    pass


def downgrade() -> None:
    pass
