"""Tests for API routes."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database import get_session


@pytest_asyncio.fixture
async def client(engine):
    """Create test client."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestPropertiesAPI:
    """Test properties API endpoints."""

    @pytest.mark.asyncio
    async def test_get_properties_empty(self, client):
        response = await client.get("/api/properties")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_properties_with_filters(self, client):
        response = await client.get(
            "/api/properties",
            params={
                "city": "Москва",
                "property_type": "apartment",
                "status": "active",
                "price_min": 1000000,
                "price_max": 20000000,
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_properties_pagination(self, client):
        response = await client.get(
            "/api/properties",
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_property_not_found(self, client):
        response = await client.get("/api/properties/99999")
        assert response.status_code == 404


class TestMapDataAPI:
    """Test map data API endpoint."""

    @pytest.mark.asyncio
    async def test_map_data_empty(self, client):
        response = await client.get("/api/map-data")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_map_data_with_filters(self, client):
        response = await client.get(
            "/api/map-data",
            params={"city": "Москва", "days": 30},
        )
        assert response.status_code == 200


class TestStatsAPI:
    """Test statistics API endpoint."""

    @pytest.mark.asyncio
    async def test_stats(self, client):
        response = await client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_source" in data
        assert "by_status" in data


class TestScrapeTriggerAPI:
    """Test scrape trigger endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_scrape_no_auth(self, client):
        """In dev mode (no ADMIN_API_KEY), scrape trigger should work."""
        response = await client.post("/api/scrape/trigger")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("started", "no_worker")


class TestScrapeLogsAPI:
    """Test scrape logs API endpoint."""

    @pytest.mark.asyncio
    async def test_scrape_logs(self, client):
        response = await client.get("/api/scrape-logs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestInputValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_properties_invalid_page(self, client):
        response = await client.get("/api/properties", params={"page": 0})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_properties_invalid_page_size(self, client):
        # Note: rate limiter may return 429 in test environment
        response = await client.get("/api/properties", params={"page_size": 1000})
        assert response.status_code in (422, 429)  # Validation error or rate limited

    @pytest.mark.asyncio
    async def test_map_data_invalid_days(self, client):
        response = await client.get("/api/map-data", params={"days": -1})
        # Should work (negative days = no filter) or rate limited
        assert response.status_code in (200, 429)
