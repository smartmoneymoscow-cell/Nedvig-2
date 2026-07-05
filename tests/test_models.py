"""Tests for database models."""

import pytest
from datetime import datetime, date

from models import (
    AuctionProperty, ScrapeLog, SourceType, AuctionStatus, PropertyType,
    EnumString,
)


class TestEnumString:
    """Test the EnumString TypeDecorator."""

    def test_bind_source_type(self):
        es = EnumString(SourceType, length=50)
        assert es.process_bind_param(SourceType.TORGIGOV, None) == "torgi_gov"
        assert es.process_bind_param(SourceType.GOSPLAN, None) == "gosplan"
        assert es.process_bind_param(None, None) is None

    def test_result_source_type(self):
        es = EnumString(SourceType, length=50)
        assert es.process_result_value("torgi_gov", None) == SourceType.TORGIGOV
        assert es.process_result_value("gosplan", None) == SourceType.GOSPLAN
        assert es.process_result_value(None, None) is None

    def test_bind_property_type(self):
        es = EnumString(PropertyType, length=50)
        assert es.process_bind_param(PropertyType.APARTMENT, None) == "apartment"
        assert es.process_bind_param(PropertyType.HOUSE, None) == "house"

    def test_result_property_type(self):
        es = EnumString(PropertyType, length=50)
        assert es.process_result_value("apartment", None) == PropertyType.APARTMENT
        assert es.process_result_value("unknown_value", None) == "unknown_value"

    def test_bind_auction_status(self):
        es = EnumString(AuctionStatus, length=50)
        assert es.process_bind_param(AuctionStatus.ACTIVE, None) == "active"
        assert es.process_bind_param(AuctionStatus.COMPLETED, None) == "completed"


class TestAuctionPropertyModel:
    """Test AuctionProperty model."""

    def test_to_dict_full(self, sample_property_data):
        prop = AuctionProperty(**sample_property_data)
        d = prop.to_dict()

        assert d["source"] == "torgi_gov"
        assert d["source_id"] == "test-123"
        assert d["title"] == "3-комнатная квартира, 75 м²"
        assert d["property_type"] == "apartment"
        assert d["city"] == "Москва"
        assert d["latitude"] == 55.7558
        assert d["longitude"] == 37.6173
        assert d["total_area"] == 75.0
        assert d["rooms"] == 3
        assert d["start_price"] == 12000000.0
        assert d["auction_status"] == "active"

    def test_to_dict_minimal(self):
        prop = AuctionProperty(
            source=SourceType.TORGIGOV,
            source_id="min-1",
        )
        d = prop.to_dict()

        assert d["source"] == "torgi_gov"
        assert d["source_id"] == "min-1"
        assert d["title"] is None
        assert d["latitude"] is None
        assert d["start_price"] is None

    def test_enum_values_stored_as_strings(self):
        prop = AuctionProperty(
            source=SourceType.GOSPLAN,
            source_id="gp-1",
            property_type=PropertyType.HOUSE,
            auction_status=AuctionStatus.UPCOMING,
        )
        # source should be the enum instance (SQLAlchemy handles conversion)
        assert prop.source in (SourceType.GOSPLAN, "gosplan")
        assert prop.property_type in (PropertyType.HOUSE, "house")


class TestScrapeLogModel:
    """Test ScrapeLog model."""

    def test_creation(self):
        log = ScrapeLog(
            source=SourceType.TORGIGOV,
            status="running",
            items_found=0,
        )
        assert log.source in (SourceType.TORGIGOV, "torgi_gov")
        assert log.status == "running"
        assert log.items_found == 0
