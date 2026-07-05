"""SQLAlchemy models for estate auction data.

Uses String columns for enum fields (SQLite + PostgreSQL compatible).
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, Boolean,
    Index, JSON, TypeDecorator
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


# --- Enums ---

class SourceType(enum.Enum):
    TORGIGOV = "torgi_gov"
    GOSPLAN = "gosplan"


class AuctionStatus(enum.Enum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PropertyType(enum.Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    LAND = "land"
    COMMERCIAL = "commercial"
    ROOM = "room"
    GARAGE = "garage"
    OTHER = "other"


# --- Enum TypeDecorator (SQLite + PG compatible) ---

class EnumString(TypeDecorator):
    """Stores Python enum as string in DB. Works on SQLite and PostgreSQL."""
    impl = String
    cache_ok = True

    def __init__(self, enum_class, *args, **kwargs):
        self._enum_class = enum_class
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self._enum_class):
            return value.value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return self._enum_class(value)
        except ValueError:
            return value


# --- Models ---

class AuctionProperty(Base):
    """Объект недвижимости на торгах."""
    __tablename__ = "auction_properties"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Источник данных
    source: Mapped[str] = mapped_column(EnumString(SourceType, length=50))
    source_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Основные характеристики
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(
        EnumString(PropertyType, length=50), nullable=True
    )

    # Адрес и координаты
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Параметры объекта
    total_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    living_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Цены
    start_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    discount_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Информация о торгах
    auction_status: Mapped[Optional[str]] = mapped_column(
        EnumString(AuctionStatus, length=50), nullable=True
    )
    auction_date_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    auction_date_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    publish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    organizer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bid_step: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deposit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Метаданные
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_geocoded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_market_appraised: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_source_source_id", "source", "source_id", unique=True),
        Index("ix_publish_date", "publish_date"),
        Index("ix_city_property_type", "city", "property_type"),
        Index("ix_auction_status", "auction_status"),
        Index("ix_coords", "latitude", "longitude"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value if isinstance(self.source, SourceType) else self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "title": self.title,
            "description": self.description,
            "property_type": self.property_type.value if isinstance(self.property_type, PropertyType) else self.property_type,
            "address": self.address,
            "region": self.region,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "total_area": self.total_area,
            "living_area": self.living_area,
            "rooms": self.rooms,
            "floor": self.floor,
            "total_floors": self.total_floors,
            "start_price": self.start_price,
            "current_price": self.current_price,
            "market_price": self.market_price,
            "price_per_sqm": self.price_per_sqm,
            "discount_pct": self.discount_pct,
            "auction_status": self.auction_status.value if isinstance(self.auction_status, AuctionStatus) else self.auction_status,
            "auction_date_start": self.auction_date_start.isoformat() if self.auction_date_start else None,
            "auction_date_end": self.auction_date_end.isoformat() if self.auction_date_end else None,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "lot_number": self.lot_number,
            "organizer": self.organizer,
            "bid_step": self.bid_step,
            "deposit": self.deposit,
            "is_geocoded": self.is_geocoded,
            "is_market_appraised": self.is_market_appraised,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScrapeLog(Base):
    """Лог парсинга для отслеживания состояния."""
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(EnumString(SourceType, length=50))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    proxy_used: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
