"""Tests for torgi.gov.ru scraper."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from scrapers.torgi_scraper import TorgiGovScraper
from models import SourceType, AuctionStatus, PropertyType


class TestTorgiGovScraperParsing:
    """Test TorgiGovScraper parsing logic."""

    def setup_method(self):
        self.scraper = TorgiGovScraper()

    def test_detect_property_type_apartment(self):
        assert self.scraper._detect_property_type("Квартира 3-комн.") == PropertyType.APARTMENT
        assert self.scraper._detect_property_type("2-комнатная квартира") == PropertyType.APARTMENT

    def test_detect_property_type_house(self):
        assert self.scraper._detect_property_type("Жилой дом 150 м²") == PropertyType.HOUSE
        assert self.scraper._detect_property_type("Дачный дом") == PropertyType.HOUSE

    def test_detect_property_type_land(self):
        assert self.scraper._detect_property_type("Земельный участок 10 соток") == PropertyType.LAND
        assert self.scraper._detect_property_type("Участок под ИЖС") == PropertyType.LAND

    def test_detect_property_type_commercial(self):
        assert self.scraper._detect_property_type("Нежилое помещение 200 м²") == PropertyType.COMMERCIAL
        assert self.scraper._detect_property_type("Офисное помещение") == PropertyType.COMMERCIAL

    def test_detect_property_type_garage(self):
        assert self.scraper._detect_property_type("Гараж бокс") == PropertyType.GARAGE
        assert self.scraper._detect_property_type("Машиноместо") == PropertyType.GARAGE

    def test_detect_property_type_unknown(self):
        assert self.scraper._detect_property_type("Some random text") == PropertyType.OTHER

    def test_detect_auction_status_active(self):
        assert self.scraper._detect_auction_status({"lotStatus": "Идут торги"}) == AuctionStatus.ACTIVE

    def test_detect_auction_status_completed(self):
        assert self.scraper._detect_auction_status({"lotStatus": "Торги завершены"}) == AuctionStatus.COMPLETED

    def test_detect_auction_status_cancelled(self):
        assert self.scraper._detect_auction_status({"lotStatus": "Торги отменены"}) == AuctionStatus.CANCELLED

    def test_parse_lot_card(self, torgi_api_response):
        """Test parsing a lot card from API response."""
        card = torgi_api_response["content"][0]
        result = self.scraper._parse_lot_card(card)

        assert result["source"] == SourceType.TORGIGOV
        assert result["source_id"] == "100001"
        assert "Квартира" in result["title"]
        assert result["property_type"] == PropertyType.APARTMENT
        assert result["address"] == "г. Москва, ул. Ленина, д. 10, кв. 42"
        assert result["city"] == "Москва"
        assert result["start_price"] == 8500000
        assert result["total_area"] == 54.0
        assert result["lot_number"] == "T-2025-001"
        assert result["organizer"] == "Управление Росимущества"
        assert result["auction_status"] == AuctionStatus.ACTIVE

    def test_parse_lot_card_price_per_sqm(self, torgi_api_response):
        """Should calculate price per sqm."""
        card = torgi_api_response["content"][0]
        result = self.scraper._parse_lot_card(card)

        assert result["price_per_sqm"] is not None
        assert abs(result["price_per_sqm"] - 8500000 / 54.0) < 0.01

    def test_parse_lot_card_land(self, torgi_api_response):
        """Test parsing land lot."""
        card = torgi_api_response["content"][1]
        result = self.scraper._parse_lot_card(card)

        assert result["property_type"] == PropertyType.LAND
        assert result["total_area"] == 1000.0
        assert result["start_price"] == 3200000

    def test_parse_lot_card_missing_fields(self):
        """Should handle missing fields gracefully."""
        card = {"id": "999", "lotName": "Test"}
        result = self.scraper._parse_lot_card(card)

        assert result["source_id"] == "999"
        assert result["title"] == "Test"
        assert result["start_price"] is None
        assert result["total_area"] is None
        assert result["address"] == ""

    def test_parse_lot_card_publish_date(self, torgi_api_response):
        """Should parse publish date correctly."""
        card = torgi_api_response["content"][0]
        result = self.scraper._parse_lot_card(card)

        assert result["publish_date"] == date(2025, 7, 1)
