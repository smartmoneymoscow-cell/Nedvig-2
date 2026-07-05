"""Scraper for CIAN.ru — Russian real estate marketplace.

Used for market price estimation (обогащение рыночной оценкой).
Compares auction properties with similar listings on CIAN.

Anti-detection strategy:
- curl_cffi with TLS fingerprint impersonation
- Rotating proxies
- Random delays
- Playwright fallback for JS-heavy pages
- Rate limiting awareness
"""

import re
import json
import time
import hashlib
import random
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper
from .proxy_manager import proxy_manager
from models import PropertyType


CIAN_BASE = "https://www.cian.ru"
CIAN_SEARCH_URL = "https://www.cian.ru/cat.php"
CIAN_API_SEARCH = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"

# CIAN property type mapping
CIAN_PROPERTY_TYPES = {
    PropertyType.APARTMENT: 1,  # kvartiry
    PropertyType.HOUSE: 2,      # doma
    PropertyType.LAND: 3,       # uchastki
    PropertyType.COMMERCIAL: 4, # commercial
    PropertyType.ROOM: 5,       # komnaty
    PropertyType.GARAGE: 6,     # garazhi
}

# City to CIAN region ID mapping
CIAN_REGIONS = {
    "москва": 1,
    "санкт-петербург": 2,
    "новосибирск": 3,
    "екатеринбург": 4,
    "казань": 5,
    "нижний новгород": 6,
    "челябинск": 7,
    "самара": 8,
    "омск": 9,
    "ростов-на-дону": 10,
}


class CianScraper(BaseScraper):
    """Scraper for CIAN.ru market price estimation."""

    def __init__(self):
        super().__init__("cian")
        self._api_session = None

    def _create_api_session(self):
        """Create session for CIAN API calls."""
        session = self._create_session()
        session.headers.update({
            "Referer": "https://www.cian.ru/",
            "Origin": "https://www.cian.ru",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        return session

    def _build_search_url(
        self,
        city: str,
        property_type: PropertyType,
        rooms: int = None,
        area_min: float = None,
        area_max: float = None,
        price_max: float = None,
        deal_type: str = "sale",
    ) -> str:
        """Build CIAN search URL with filters."""
        # Determine URL path based on property type
        type_paths = {
            PropertyType.APARTMENT: "kvartiry",
            PropertyType.HOUSE: "doma",
            PropertyType.LAND: "uchastki",
            PropertyType.COMMERCIAL: "commercial",
            PropertyType.ROOM: "komnaty",
            PropertyType.GARAGE: "garazhi",
        }

        path = type_paths.get(property_type, "kvartiry")
        deal = "prodam" if deal_type == "sale" else "sdam"

        params = {
            "deal_type": deal,
            "engine_version": 2,
            "offer_type": "flat" if property_type == PropertyType.APARTMENT else "house",
            "p": 1,
            "region": self._get_region_id(city),
        }

        if rooms:
            params["room"] = [rooms]
        if area_min:
            params["total_area"] = {"min": area_min * 0.9, "max": area_max * 1.1 if area_max else area_min * 1.5}
        if price_max:
            params["maxprice"] = int(price_max * 1.5)

        return f"{CIAN_BASE}/{deal}/{path}/"

    def _get_region_id(self, city: str) -> int:
        """Get CIAN region ID from city name."""
        city_lower = city.lower().strip() if city else ""
        return CIAN_REGIONS.get(city_lower, 1)  # Default to Moscow

    def _estimate_market_price_api(self, property_data: dict) -> Optional[dict]:
        """
        Estimate market price using CIAN search API.
        Returns dict with market_price and price_per_sqm.
        """
        city = property_data.get("city", "Москва")
        property_type = property_data.get("property_type", PropertyType.APARTMENT)
        rooms = property_data.get("rooms")
        total_area = property_data.get("total_area")
        address = property_data.get("address", "")

        if not total_area or total_area <= 0:
            logger.warning(f"[CIAN] No area data for estimation")
            return None

        try:
            if not self._api_session:
                self._api_session = self._create_api_session()

            self._throttle(3.0, 8.0)

            # Build API request
            payload = {
                "jsonQuery": {
                    "_type": "flatsale",
                    "engine_version": {"type": "term", "value": 2},
                    "geo": {
                        "type": "geo",
                        "value": [{"type": "district", "id": self._get_region_id(city)}]
                    },
                    "room": {"type": "terms", "value": [rooms or 1, 2, 3]},
                    "total_area": {
                        "type": "range",
                        "value": {
                            "gte": total_area * 0.7,
                            "lte": total_area * 1.3,
                        }
                    },
                    "sort": {"type": "term", "value": "price_object_order"},
                    "page": {"type": "term", "value": 1},
                }
            }

            response = self._api_session.post(
                CIAN_API_SEARCH,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                offers = data.get("data", {}).get("offersSerialized", [])

                if offers:
                    prices = []
                    for offer in offers[:20]:  # Take top 20 comparable
                        price = offer.get("bargainTerms", {}).get("price")
                        area = offer.get("totalArea")
                        if price and area and area > 0:
                            prices.append(price / area)

                    if prices:
                        # Remove outliers
                        prices.sort()
                        if len(prices) > 4:
                            prices = prices[1:-1]

                        avg_price_per_sqm = sum(prices) / len(prices)
                        market_price = avg_price_per_sqm * total_area

                        return {
                            "market_price": round(market_price, 2),
                            "price_per_sqm": round(avg_price_per_sqm, 2),
                            "comparable_count": len(prices),
                        }

            logger.warning(f"[CIAN] API returned {response.status_code}")

        except Exception as e:
            logger.error(f"[CIAN] API estimation failed: {e}")

        return None

    def _estimate_market_price_html(self, property_data: dict) -> Optional[dict]:
        """
        Fallback: estimate market price by scraping CIAN search results.
        """
        city = property_data.get("city", "Москва")
        property_type = property_data.get("property_type", PropertyType.APARTMENT)
        rooms = property_data.get("rooms")
        total_area = property_data.get("total_area")

        if not total_area or total_area <= 0:
            return None

        try:
            self._throttle(3.0, 8.0)

            # Build search URL
            deal = "prodam"
            type_paths = {
                PropertyType.APARTMENT: "kvartiry",
                PropertyType.HOUSE: "doma",
                PropertyType.LAND: "uchastki",
                PropertyType.COMMERCIAL: "commercial",
                PropertyType.ROOM: "komnaty",
            }
            path = type_paths.get(property_type, "kvartiry")

            params = {
                "deal_type": "sale",
                "offer_type": "flat",
                "total_area[min]": total_area * 0.7,
                "total_area[max]": total_area * 1.3,
                "region": self._get_region_id(city),
                "p": 1,
            }
            if rooms:
                params["room"] = rooms

            url = f"{CIAN_BASE}/{deal}/{path}/"
            response = self.fetch_with_retry(url, params=params)

            soup = BeautifulSoup(response.text, "lxml")

            # Extract prices from listing cards
            prices = []
            price_elements = soup.select(
                "[data-name='Price'] span, "
                ".price, "
                "[class*='price'], "
                "[class*='Price'], "
                "span[data-mark='MainPrice']"
            )

            for el in price_elements:
                text = el.get_text(strip=True)
                # Parse price like "12 500 000 ₽"
                match = re.search(r"([\d\s]+(?:\.\d+)?)", text.replace("\xa0", " "))
                if match:
                    try:
                        price = float(match.group(1).replace(" ", ""))
                        if price > 100000:  # Filter out obviously wrong values
                            prices.append(price)
                    except ValueError:
                        continue

            if prices and len(prices) >= 3:
                # Remove outliers
                prices.sort()
                if len(prices) > 4:
                    prices = prices[1:-1]

                avg_price = sum(prices) / len(prices)
                avg_per_sqm = avg_price / (total_area * 0.85)  # Approximate

                return {
                    "market_price": round(avg_price, 2),
                    "price_per_sqm": round(avg_per_sqm, 2),
                    "comparable_count": len(prices),
                }

            logger.warning(f"[CIAN] No prices found in HTML")

        except Exception as e:
            logger.error(f"[CIAN] HTML estimation failed: {e}")

        return None

    def estimate_market_price(self, property_data: dict) -> Optional[dict]:
        """
        Estimate market price for a property using CIAN data.

        Args:
            property_data: Dict with city, property_type, rooms, total_area, address

        Returns:
            Dict with market_price, price_per_sqm, comparable_count or None
        """
        # Try API first
        result = self._estimate_market_price_api(property_data)
        if result:
            return result

        # Fallback to HTML scraping
        logger.info("[CIAN] API failed, falling back to HTML scraping")
        return self._estimate_market_price_html(property_data)

    def batch_estimate(self, properties: list[dict], batch_size: int = 5) -> list[dict]:
        """
        Estimate market prices for multiple properties.

        Args:
            properties: List of property dicts
            batch_size: Number of properties before rotating session

        Returns:
            List of estimation results
        """
        results = []

        for i, prop in enumerate(properties):
            logger.info(f"[CIAN] Estimating {i+1}/{len(properties)}: {prop.get('title', 'unknown')}")

            estimation = self.estimate_market_price(prop)
            results.append(estimation or {})

            # Rotate session periodically
            if (i + 1) % batch_size == 0:
                self._rotate_session()
                self._api_session = None
                # Extra delay between batches
                time.sleep(random.uniform(10, 20))

        return results

    def scrape_listings(self, **kwargs) -> list[dict]:
        """Not used — CIAN is for price estimation only."""
        return []
