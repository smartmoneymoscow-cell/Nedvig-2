"""Initial schema — uses String columns (not PG enums) for source/status/type.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # auction_properties — String columns for source/status/type (EnumString in models)
    op.create_table(
        'auction_properties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('property_type', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('region', sa.String(255), nullable=True),
        sa.Column('city', sa.String(255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('total_area', sa.Float(), nullable=True),
        sa.Column('living_area', sa.Float(), nullable=True),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('total_floors', sa.Integer(), nullable=True),
        sa.Column('start_price', sa.Float(), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('market_price', sa.Float(), nullable=True),
        sa.Column('price_per_sqm', sa.Float(), nullable=True),
        sa.Column('discount_pct', sa.Float(), nullable=True),
        sa.Column('auction_status', sa.String(50), nullable=True),
        sa.Column('auction_date_start', sa.DateTime(), nullable=True),
        sa.Column('auction_date_end', sa.DateTime(), nullable=True),
        sa.Column('publish_date', sa.Date(), nullable=True),
        sa.Column('lot_number', sa.String(100), nullable=True),
        sa.Column('organizer', sa.Text(), nullable=True),
        sa.Column('bid_step', sa.Float(), nullable=True),
        sa.Column('deposit', sa.Float(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_geocoded', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('is_market_appraised', sa.Boolean(), server_default=sa.text('false')),
    )

    # Indexes
    op.create_index('ix_source_source_id', 'auction_properties', ['source', 'source_id'], unique=True)
    op.create_index('ix_publish_date', 'auction_properties', ['publish_date'])
    op.create_index('ix_city_property_type', 'auction_properties', ['city', 'property_type'])
    op.create_index('ix_auction_status', 'auction_properties', ['auction_status'])
    op.create_index('ix_coords', 'auction_properties', ['latitude', 'longitude'])

    # scrape_logs
    op.create_table(
        'scrape_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items_found', sa.Integer(), server_default=sa.text('0')),
        sa.Column('items_new', sa.Integer(), server_default=sa.text('0')),
        sa.Column('items_updated', sa.Integer(), server_default=sa.text('0')),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), server_default=sa.text("'running'")),
        sa.Column('proxy_used', sa.String(500), nullable=True),
    )

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100), server_default=sa.text("''")),
        sa.Column('role', sa.String(50), server_default=sa.text("'user'")),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('users')
    op.drop_table('scrape_logs')
    op.drop_index('ix_coords', 'auction_properties')
    op.drop_index('ix_auction_status', 'auction_properties')
    op.drop_index('ix_city_property_type', 'auction_properties')
    op.drop_index('ix_publish_date', 'auction_properties')
    op.drop_index('ix_source_source_id', 'auction_properties')
    op.drop_table('auction_properties')
