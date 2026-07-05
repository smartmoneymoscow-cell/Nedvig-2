"""Tests for base scraper utilities."""

import pytest
from datetime import datetime, date
from unittest.mock import patch

from scrapers.base_scraper import BaseScraper


# Concrete implementation for testing
class DummyScraper(BaseScraper):
    def scrape_listings(self, **kwargs):
        return []


class TestBaseScraperParsing:
    """Test parsing utilities in BaseScraper."""

    def setup_method(self):
        self.scraper = DummyScraper("test")

    def test_parse_price_normal(self):
        assert self.scraper._parse_price("12 500 000 руб.") == 12500000.0
        assert self.scraper._parse_price("8500000") == 8500000.0
        assert self.scraper._parse_price("3 200 000 ₽") == 3200000.0

    def test_parse_price_with_spaces(self):
        assert self.scraper._parse_price("1 000 000") == 1000000.0

    def test_parse_price_with_comma(self):
        assert self.scraper._parse_price("1500000,50") == 1500000.5

    def test_parse_price_empty(self):
        assert self.scraper._parse_price("") is None
        assert self.scraper._parse_price(None) is None

    def test_parse_price_invalid(self):
        assert self.scraper._parse_price("abc") is None

    def test_parse_date_dot_format(self):
        result = self.scraper._parse_date("01.07.2025")
        assert result == date(2025, 7, 1)

    def test_parse_date_slash_format(self):
        result = self.scraper._parse_date("01/07/2025")
        assert result == date(2025, 7, 1)

    def test_parse_date_iso_format(self):
        result = self.scraper._parse_date("2025-07-01")
        assert result == date(2025, 7, 1)

    def test_parse_date_empty(self):
        assert self.scraper._parse_date("") is None
        assert self.scraper._parse_date(None) is None

    def test_parse_date_invalid(self):
        assert self.scraper._parse_date("not a date") is None

    def test_parse_datetime_dot_format(self):
        result = self.scraper._parse_datetime("01.07.2025 10:30:00")
        assert result == datetime(2025, 7, 1, 10, 30, 0)

    def test_parse_datetime_iso_format(self):
        result = self.scraper._parse_datetime("2025-07-01T10:30:00")
        assert result == datetime(2025, 7, 1, 10, 30, 0)

    def test_parse_datetime_empty(self):
        assert self.scraper._parse_datetime("") is None
        assert self.scraper._parse_datetime(None) is None

    def test_context_manager(self):
        """Should be usable as context manager."""
        with DummyScraper("test") as scraper:
            assert scraper.source_name == "test"


class TestBaseScraperThrottle:
    """Test request throttling."""

    def test_throttle_delay(self):
        """Should enforce minimum delay between requests."""
        import time
        scraper = DummyScraper("test")
        scraper._last_request_time = time.time()
        start = time.time()
        scraper._throttle(0.1, 0.2)
        elapsed = time.time() - start
        assert elapsed >= 0.09  # Allow small margin
