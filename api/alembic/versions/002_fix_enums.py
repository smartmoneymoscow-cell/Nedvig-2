"""Fix enum values — add fedresurs and etp

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
    # Add new enum values for source type
    # PostgreSQL doesn't support IF NOT EXISTS for enum values directly,
    # so we use a DO block
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'fedresurs' AND enumtypid = 'sourcetype'::regtype) THEN
                ALTER TYPE sourcetype ADD VALUE 'fedresurs';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'etp' AND enumtypid = 'sourcetype'::regtype) THEN
                ALTER TYPE sourcetype ADD VALUE 'etp';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'cian' AND enumtypid = 'sourcetype'::regtype) THEN
                ALTER TYPE sourcetype ADD VALUE 'cian';
            END IF;
        END$$;
    """)


def downgrade() -> None:
    pass  # Cannot remove enum values in PostgreSQL
