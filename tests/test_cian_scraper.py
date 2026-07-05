"""Tests for CIAN scraper."""

import pytest
from unittest.mock import patch, MagicMock

from scrapers.cian_scraper import CianScraper
from models import PropertyType


class TestCianScraperLogic:
    """Test CianScraper utility methods."""

    def setup_method(self):
        self.scraper = CianScraper()

    def test_get_region_id_moscow(self):
        assert self.scraper._get_region_id("Москва") == 1
        assert self.scraper._get_region_id("москва") == 1

    def test_get_region_id_spb(self):
        assert self.scraper._get_region_id("Санкт-Петербург") == 2

    def test_get_region_id_unknown(self):
        assert self.scraper._get_region_id("Неизвестный город") == 1  # Default Moscow

    def test_get_region_id_empty(self):
        assert self.scraper._get_region_id("") == 1
        assert self.scraper._get_region_id(None) == 1

    def test_build_search_url_apartment(self):
        url = self.scraper._build_search_url("Москва", PropertyType.APARTMENT)
        assert "kvartiry" in url
        assert "cian.ru" in url

    def test_build_search_url_house(self):
        url = self.scraper._build_search_url("Москва", PropertyType.HOUSE)
        assert "doma" in url

    def test_build_search_url_land(self):
        url = self.scraper._build_search_url("Москва", PropertyType.LAND)
        assert "uchastki" in url

    def test_scrape_listings_returns_empty(self):
        """CIAN scraper is for estimation only, not listing scraping."""
        assert self.scraper.scrape_listings() == []

    def test_estimate_market_price_no_area(self):
        """Should return None if no area data."""
        result = self.scraper.estimate_market_price({
            "city": "Москва",
            "property_type": PropertyType.APARTMENT,
            "total_area": None,
        })
        assert result is None

    def test_estimate_market_price_zero_area(self):
        """Should return None if area is zero."""
        result = self.scraper.estimate_market_price({
            "city": "Москва",
            "property_type": PropertyType.APARTMENT,
            "total_area": 0,
        })
        assert result is None
