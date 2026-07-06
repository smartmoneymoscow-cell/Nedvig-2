"""Initial schema

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
    # Create enum types
    op.execute("CREATE TYPE sourcetype AS ENUM ('torgi_gov', 'gosplan')")
    op.execute("CREATE TYPE auctionstatus AS ENUM ('active', 'upcoming', 'completed', 'cancelled')")
    op.execute("CREATE TYPE propertytype AS ENUM ('apartment', 'house', 'land', 'commercial', 'room', 'garage', 'other')")

    # auction_properties table
    op.create_table(
        'auction_properties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.Enum('torgi_gov', 'gosplan', name='sourcetype'), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('property_type', sa.Enum('apartment', 'house', 'land', 'commercial', 'room', 'garage', 'other', name='propertytype'), nullable=True),
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
        sa.Column('auction_status', sa.Enum('active', 'upcoming', 'completed', 'cancelled', name='auctionstatus'), nullable=True),
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
        sa.Column('is_geocoded', sa.Boolean(), default=False),
        sa.Column('is_market_appraised', sa.Boolean(), default=False),
    )

    # Indexes
    op.create_index('ix_source_source_id', 'auction_properties', ['source', 'source_id'], unique=True)
    op.create_index('ix_publish_date', 'auction_properties', ['publish_date'])
    op.create_index('ix_city_property_type', 'auction_properties', ['city', 'property_type'])
    op.create_index('ix_auction_status', 'auction_properties', ['auction_status'])
    op.create_index('ix_coords', 'auction_properties', ['latitude', 'longitude'])

    # scrape_logs table
    op.create_table(
        'scrape_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.Enum('torgi_gov', 'gosplan', name='sourcetype'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items_found', sa.Integer(), default=0),
        sa.Column('items_new', sa.Integer(), default=0),
        sa.Column('items_updated', sa.Integer(), default=0),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), default='running'),
        sa.Column('proxy_used', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('scrape_logs')
    op.drop_index('ix_coords', 'auction_properties')
    op.drop_index('ix_auction_status', 'auction_properties')
    op.drop_index('ix_city_property_type', 'auction_properties')
    op.drop_index('ix_publish_date', 'auction_properties')
    op.drop_index('ix_source_source_id', 'auction_properties')
    op.drop_table('auction_properties')
    op.execute('DROP TYPE IF EXISTS propertytype')
    op.execute('DROP TYPE IF EXISTS auctionstatus')
    op.execute('DROP TYPE IF EXISTS sourcetype')
