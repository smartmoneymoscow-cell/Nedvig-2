"""Shared test fixtures."""

import os
import asyncio
import pytest
import pytest_asyncio

# Force SQLite mode for tests
os.environ["USE_SQLITE"] = "true"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from models import Base
from database import get_session


TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create test database engine."""
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Create a test database session with rollback."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_property_data():
    """Sample property data for tests."""
    return {
        "source": "torgi_gov",
        "source_id": "test-123",
        "source_url": "https://torgi.gov.ru/lot/123",
        "title": "3-комнатная квартира, 75 м²",
        "description": "Трёхкомнатная квартира в центре Москвы",
        "property_type": "apartment",
        "address": "ул. Тверская, д. 1, кв. 10",
        "region": "Москва",
        "city": "Москва",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "total_area": 75.0,
        "rooms": 3,
        "floor": 5,
        "total_floors": 9,
        "start_price": 12000000.0,
        "current_price": 12000000.0,
        "auction_status": "active",
        "lot_number": "LOT-001",
    }


@pytest.fixture
def torgi_api_response():
    """Mock torgi.gov.ru API response (based on real API structure)."""
    return {
        "content": [
            {
                "id": "100001",
                "lotName": "Квартира 2-комн., 54 м²",
                "lotDescription": "Двухкомнатная квартира в жилом состоянии",
                "lotAddress": "г. Москва, ул. Ленина, д. 10, кв. 42",
                "regionName": "Москва",
                "cityName": "Москва",
                "startPrice": 8500000,
                "priceMin": 8500000,
                "totalArea": 54.0,
                "publishDate": "01.07.2025",
                "biddingStartDate": "15.07.2025 10:00",
                "biddingEndDate": "25.07.2025 18:00",
                "lotStatus": "APPLICATIONS_SUBMISSION",
                "lotNumber": "T-2025-001",
                "organizerName": "Управление Росимущества",
                "category": {"code": "9", "name": "Жилые помещения"},
                "characteristics": [
                    {"code": "totalAreaRealty", "characteristicValue": 54.0},
                    {"code": "numberFloors", "characteristicValue": "9"},
                ],
                "noticeFirstVersionPublicationDate": "2025-07-01T10:00:00.00Z",
                "biddEndTime": "2025-07-25T18:00:00.00Z",
            },
            {
                "id": "100002",
                "lotName": "Земельный участок 10 соток",
                "lotDescription": "Земельный участок для ИЖС",
                "lotAddress": "МО, Одинцовский р-н, д. Ново-Дарьино",
                "regionName": "Московская область",
                "cityName": "Одинцово",
                "startPrice": 3200000,
                "publishDate": "28.06.2025",
                "lotStatus": "PUBLISHED",
                "lotNumber": "T-2025-002",
                "category": {"code": "301", "name": "Земли населенных пунктов"},
                "characteristics": [
                    {"code": "SquareZU", "characteristicValue": 1000.0},
                ],
                "noticeFirstVersionPublicationDate": "2025-06-28T08:00:00.00Z",
            },
        ],
        "totalElements": 2,
        "totalPages": 1,
        "categoryFacet": [
            {"_id": "9", "count": 150},
            {"_id": "301", "count": 80},
        ],
    }


@pytest.fixture
def sample_listings():
    """Sample parsed listings for testing upsert."""
    from models import SourceType, AuctionStatus, PropertyType

    return [
        {
            "source": SourceType.TORGIGOV,
            "source_id": "lot-001",
            "source_url": "https://torgi.gov.ru/new/public/lots/lot/lot-001",
            "title": "Квартира 2-комн., 54 м²",
            "property_type": PropertyType.APARTMENT,
            "address": "г. Москва, ул. Ленина, д. 10",
            "start_price": 8500000.0,
            "current_price": 8500000.0,
            "total_area": 54.0,
            "rooms": 2,
            "auction_status": AuctionStatus.ACTIVE,
        },
        {
            "source": SourceType.TORGIGOV,
            "source_id": "lot-002",
            "source_url": "https://torgi.gov.ru/new/public/lots/lot/lot-002",
            "title": "Земельный участок 10 соток",
            "property_type": PropertyType.LAND,
            "address": "МО, Одинцовский р-н",
            "start_price": 3200000.0,
            "current_price": 3200000.0,
            "total_area": 1000.0,
            "auction_status": AuctionStatus.UPCOMING,
        },
    ]
