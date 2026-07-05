"""Tests for torgi.gov.ru scraper — using real API response structure."""

import pytest
from datetime import date

from scrapers.torgi_scraper import TorgiGovScraper
from models import SourceType, AuctionStatus, PropertyType


class TestTorgiGovScraperParsing:
    """Test TorgiGovScraper parsing logic with real API structure."""

    def setup_method(self):
        self.scraper = TorgiGovScraper()

    def _make_card(self, **overrides) -> dict:
        """Create a minimal lot card matching real API structure."""
        card = {
            "id": "23000020750000000041_1",
            "noticeNumber": "23000020750000000041",
            "lotNumber": 1,
            "lotStatus": "PUBLISHED",
            "biddType": {"code": "229FZ", "name": "Реализация имущества должников"},
            "biddForm": {"code": "PA", "name": "Аукцион"},
            "lotName": "Квартира, пл. 54 кв.м., г. Москва, ул. Тверская, д. 10, кв. 42",
            "lotDescription": "Квартира двухкомнатная",
            "priceMin": 8500000.0,
            "biddEndTime": "2025-07-25T12:00:00.000+00:00",
            "characteristics": [
                {"characteristicValue": 54.0, "name": "Общая площадь", "code": "totalAreaRealty", "type": "Decimal"},
                {"characteristicValue": "Квартира", "name": "Вид жилого помещения", "code": "typeLivingQuarters", "type": "Text(100)"},
                {"characteristicValue": "73:24:030807:2502", "name": "Кадастровый номер", "code": "cadastralNumberRealty", "type": "Text(20)"},
            ],
            "currencyCode": "643",
            "subjectRFCode": "77",
            "category": {"code": "9", "name": "Жилые помещения"},
            "createDate": "2025-07-01T07:01:19.273+00:00",
            "noticeFirstVersionPublicationDate": "2025-07-01T07:02:03.81Z",
            "isAnnulled": False,
        }
        card.update(overrides)
        return card

    def test_detect_property_type_apartment(self):
        card = self._make_card(category={"code": "9", "name": "Жилые помещения"})
        assert self.scraper._detect_property_type(card) == PropertyType.APARTMENT

    def test_detect_property_type_house(self):
        card = self._make_card(
            category={"code": "9", "name": "Жилые помещения"},
            characteristics=[
                {"characteristicValue": "Жилой дом", "name": "Вид жилого помещения", "code": "typeLivingQuarters", "type": "Text(100)"},
            ],
        )
        assert self.scraper._detect_property_type(card) == PropertyType.HOUSE

    def test_detect_property_type_land(self):
        card = self._make_card(category={"code": "301", "name": "Земли населенных пунктов"})
        assert self.scraper._detect_property_type(card) == PropertyType.LAND

    def test_detect_property_type_commercial(self):
        card = self._make_card(category={"code": "11", "name": "Нежилые помещения"})
        assert self.scraper._detect_property_type(card) == PropertyType.COMMERCIAL

    def test_detect_property_type_building(self):
        card = self._make_card(category={"code": "8", "name": "Здания"})
        assert self.scraper._detect_property_type(card) == PropertyType.COMMERCIAL

    def test_detect_property_type_unknown(self):
        card = self._make_card(
            category={"code": "999", "name": "Прочее"},
            lotName="Какой-то неизвестный лот",
        )
        assert self.scraper._detect_property_type(card) == PropertyType.OTHER

    def test_detect_auction_status_published(self):
        card = self._make_card(lotStatus="PUBLISHED")
        result = self.scraper._parse_lot_card(card)
        assert result["auction_status"] == AuctionStatus.UPCOMING

    def test_detect_auction_status_applications(self):
        card = self._make_card(lotStatus="APPLICATIONS_SUBMISSION")
        result = self.scraper._parse_lot_card(card)
        assert result["auction_status"] == AuctionStatus.ACTIVE

    def test_detect_auction_status_completed(self):
        card = self._make_card(lotStatus="COMPLETED")
        result = self.scraper._parse_lot_card(card)
        assert result["auction_status"] == AuctionStatus.COMPLETED

    def test_detect_auction_status_cancelled(self):
        card = self._make_card(lotStatus="ANULLED")
        result = self.scraper._parse_lot_card(card)
        assert result["auction_status"] == AuctionStatus.CANCELLED

    def test_parse_lot_card(self):
        card = self._make_card()
        result = self.scraper._parse_lot_card(card)

        assert result["source"] == SourceType.TORGIGOV
        assert result["source_id"] == "23000020750000000041_1"
        assert "Квартира" in result["title"]
        assert result["property_type"] == PropertyType.APARTMENT
        assert result["total_area"] == 54.0
        assert result["start_price"] == 8500000.0
        assert result["lot_number"] == "1"

    def test_parse_lot_card_price_per_sqm(self):
        card = self._make_card()
        result = self.scraper._parse_lot_card(card)
        assert result["price_per_sqm"] is not None
        assert abs(result["price_per_sqm"] - 8500000 / 54.0) < 0.01

    def test_parse_lot_card_land(self):
        card = self._make_card(
            category={"code": "301", "name": "Земли населенных пунктов"},
            characteristics=[
                {"characteristicValue": 1000.0, "name": "Площадь земельного участка", "code": "SquareZU", "type": "Decimal"},
            ],
            lotName="Земельный участок 10 соток, Ленинградская область",
        )
        result = self.scraper._parse_lot_card(card)
        assert result["property_type"] == PropertyType.LAND
        assert result["total_area"] == 1000.0

    def test_parse_lot_card_missing_fields(self):
        card = {"id": "999", "lotName": "Test", "lotStatus": "PUBLISHED"}
        result = self.scraper._parse_lot_card(card)
        assert result["source_id"] == "999"
        assert result["title"] == "Test"
        assert result["start_price"] is None
        assert result["total_area"] is None

    def test_parse_lot_card_publish_date(self):
        card = self._make_card()
        result = self.scraper._parse_lot_card(card)
        assert result["publish_date"] == date(2025, 7, 1)

    def test_parse_lot_card_rooms_from_title(self):
        card = self._make_card(lotName="3-комнатная квартира, 78 м², г. Москва")
        result = self.scraper._parse_lot_card(card)
        assert result["rooms"] == 3

    def test_parse_lot_card_rooms_from_title_2(self):
        card = self._make_card(lotName="Однокомнатная квартира, 38 м²")
        result = self.scraper._parse_lot_card(card)
        assert result["rooms"] == 1

    def test_get_characteristic(self):
        card = self._make_card()
        assert self.scraper._get_characteristic(card, "totalAreaRealty") == "54.0"
        assert self.scraper._get_characteristic(card, "typeLivingQuarters") == "Квартира"
        assert self.scraper._get_characteristic(card, "nonexistent") is None

    def test_get_characteristic_float(self):
        card = self._make_card()
        assert self.scraper._get_characteristic_float(card, "totalAreaRealty") == 54.0
        assert self.scraper._get_characteristic_float(card, "nonexistent") is None
