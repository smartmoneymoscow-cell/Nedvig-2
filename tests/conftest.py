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
    """Mock torgi.gov.ru API response."""
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
                "totalArea": 54.0,
                "publishDate": "01.07.2025",
                "biddingStartDate": "15.07.2025 10:00",
                "biddingEndDate": "25.07.2025 18:00",
                "lotStatus": "Идут торги",
                "lotNumber": "T-2025-001",
                "organizerName": "Управление Росимущества",
            },
            {
                "id": "100002",
                "lotName": "Земельный участок 10 соток",
                "lotDescription": "Земельный участок для ИЖС",
                "lotAddress": "МО, Одинцовский р-н, д. Ново-Дарьино",
                "regionName": "Московская область",
                "cityName": "Одинцово",
                "startPrice": 3200000,
                "totalArea": 1000.0,
                "publishDate": "28.06.2025",
                "lotStatus": "Опубликован",
                "lotNumber": "T-2025-002",
            },
        ],
        "totalElements": 2,
        "totalPages": 1,
    }
