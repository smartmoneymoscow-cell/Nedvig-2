"""Tests for CIAN scraper."""


from scrapers.cian import CianScraper
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
        assert self.scraper._get_region_id("Неизвестный город") == 1

    def test_get_region_id_empty(self):
        assert self.scraper._get_region_id("") == 1
        assert self.scraper._get_region_id(None) == 1

    def test_build_search_url_apartment(self):
        url = self.scraper._build_search_url("Москва", PropertyType.APARTMENT)
        assert "cian.ru" in url
        assert "offer_type=flat" in url
        assert "region=1" in url

    def test_build_search_url_house(self):
        url = self.scraper._build_search_url("Москва", PropertyType.HOUSE)
        assert "offer_type=house" in url

    def test_build_search_url_with_rooms(self):
        url = self.scraper._build_search_url("Москва", PropertyType.APARTMENT, rooms=2)
        assert "room2=1" in url

    def test_build_search_url_region(self):
        url = self.scraper._build_search_url("Санкт-Петербург", PropertyType.APARTMENT)
        assert "region=2" in url

    def test_scrape_listings_returns_empty(self):
        assert self.scraper.scrape_listings() == []

    def test_estimate_market_price_no_area(self):
        result = self.scraper.estimate_market_price({
            "city": "Москва",
            "property_type": PropertyType.APARTMENT,
            "total_area": None,
        })
        assert result is None

    def test_estimate_market_price_zero_area(self):
        result = self.scraper.estimate_market_price({
            "city": "Москва",
            "property_type": PropertyType.APARTMENT,
            "total_area": 0,
        })
        assert result is None

    def test_remove_outliers(self):
        prices = [100, 110, 120, 130, 140, 150, 1000]  # 1000 is outlier
        result = self.scraper._remove_outliers(prices)
        assert 1000 not in result
        assert len(result) == 6

    def test_remove_outliers_no_outliers(self):
        prices = [100, 110, 120, 130, 140]
        result = self.scraper._remove_outliers(prices)
        assert len(result) == 5

    def test_remove_outliers_small_list(self):
        prices = [100, 110]
        result = self.scraper._remove_outliers(prices)
        assert len(result) == 2
