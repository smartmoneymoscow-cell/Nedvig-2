"""Scraper for CIAN.ru — Russian real estate marketplace.

Used for market price estimation (обогащение рыночной оценкой).
Searches for comparable properties and calculates average price per m².

Real CIAN search URL pattern:
https://cian.ru/cat.php?engine_version=2&p=1&region={id}&offer_type=flat&deal_type=sale&room1=1&room2=1

Anti-detection strategy:
- curl_cffi with TLS fingerprint impersonation
- Rotating proxies
- Random delays (3-8s between requests)
- Realistic browser headers
"""

import re
import json
import time
import random
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper
from .proxy_manager import proxy_manager
from models import PropertyType


CIAN_BASE = "https://www.cian.ru"
CIAN_SEARCH_PATH = "/cat.php"

# CIAN region IDs (from actual URLs)
CIAN_REGIONS = {
    "москва": 1,
    "санкт-петербург": 2,
    "новосибирск": 4,
    "екатеринбург": 5,
    "казань": 6,
    "нижний новгород": 7,
    "челябинск": 9,
    "самара": 10,
    "ростов-на-дону": 11,
    "уфа": 12,
    "красноярск": 13,
    "пермь": 14,
    "воронеж": 15,
    "волгоград": 16,
    "краснодар": 17,
    "саратов": 18,
    "тюмень": 19,
    "томск": 20,
    "омск": 21,
    "иркутск": 22,
    "владивосток": 23,
    "ярославль": 24,
    "махачкала": 25,
    "хабаровск": 26,
    "оренбург": 27,
    "новокузнецк": 28,
    "кемерово": 29,
    "рязань": 30,
    "калининград": 66,
    "владимир": 170,
}

# Offer type mapping
OFFER_TYPES = {
    PropertyType.APARTMENT: "flat",
    PropertyType.HOUSE: "house",
    PropertyType.ROOM: "room",
    PropertyType.COMMERCIAL: "office",
}

# Room configuration for apartments
ROOM_OPTIONS = {
    None: "room1=1&room2=1&room3=1&room4=1&room9=1",  # All types
    1: "room1=1",
    2: "room2=1",
    3: "room3=1",
    4: "room4=1",
    5: "room5=1",
}


class CianScraper(BaseScraper):
    """Scraper for CIAN.ru market price estimation."""

    def __init__(self):
        super().__init__("cian")
        self._session = None

    def _create_session(self):
        """Create session with CIAN-specific headers."""
        session = super()._create_session()
        session.headers.update({
            "Referer": CIAN_BASE,
            "Origin": CIAN_BASE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        })
        return session

    def _get_region_id(self, city: str) -> int:
        """Get CIAN region ID from city name."""
        city_lower = city.lower().strip() if city else ""
        return CIAN_REGIONS.get(city_lower, 1)  # Default Moscow

    def _build_search_url(
        self,
        city: str,
        property_type: PropertyType,
        rooms: int = None,
        area_min: float = None,
        area_max: float = None,
    ) -> str:
        """Build CIAN search URL with filters."""
        region_id = self._get_region_id(city)
        offer_type = OFFER_TYPES.get(property_type, "flat")

        # Base params
        params = {
            "engine_version": 2,
            "p": 1,
            "region": region_id,
            "offer_type": offer_type,
            "deal_type": "sale",
            "sort": "price_object_order",
        }

        # Room filter
        if property_type == PropertyType.APARTMENT:
            if rooms and rooms in ROOM_OPTIONS:
                params_str = ROOM_OPTIONS[rooms]
            else:
                params_str = ROOM_OPTIONS[None]
        else:
            params_str = ""

        # Area filter
        if area_min:
            params["mintarea"] = area_min * 0.7
        if area_max:
            params["maxtarea"] = area_max * 1.3

        url = f"{CIAN_BASE}{CIAN_SEARCH_PATH}?{urlencode(params)}"
        if params_str:
            url += f"&{params_str}"

        return url

    def estimate_market_price(self, property_data: dict) -> Optional[dict]:
        """
        Estimate market price for a property using CIAN search results.

        Args:
            property_data: Dict with city, property_type, rooms, total_area

        Returns:
            Dict with market_price, price_per_sqm, comparable_count or None
        """
        city = property_data.get("city", "Москва")
        property_type = property_data.get("property_type", PropertyType.APARTMENT)
        rooms = property_data.get("rooms")
        total_area = property_data.get("total_area")

        if not total_area or total_area <= 0:
            logger.warning("[CIAN] No area data for estimation")
            return None

        try:
            if not self._session:
                self._session = self._create_session()

            self._throttle(3.0, 8.0)

            # Build search URL
            url = self._build_search_url(
                city=city,
                property_type=property_type,
                rooms=rooms,
                area_min=total_area,
                area_max=total_area,
            )

            logger.info(f"[CIAN] Searching: {url[:100]}...")

            response = self._session.get(url, timeout=30)

            if response.status_code == 403:
                logger.warning("[CIAN] 403 Forbidden — anti-bot triggered")
                self._rotate_session()
                return None

            if response.status_code != 200:
                logger.warning(f"[CIAN] HTTP {response.status_code}")
                return None

            # Parse HTML
            soup = BeautifulSoup(response.text, "lxml")

            # Extract prices from listing cards
            prices = self._extract_prices(soup)

            if len(prices) < 3:
                logger.warning(f"[CIAN] Too few prices found: {len(prices)}")
                # Try alternative parsing
                prices = self._extract_prices_json(soup)

            if len(prices) < 3:
                logger.warning(f"[CIAN] Still too few prices: {len(prices)}")
                return None

            # Remove outliers (IQR method)
            prices = self._remove_outliers(prices)

            if len(prices) < 2:
                return None

            # Calculate average price per m²
            avg_price_per_sqm = sum(prices) / len(prices)
            market_price = avg_price_per_sqm * total_area

            return {
                "market_price": round(market_price, 2),
                "price_per_sqm": round(avg_price_per_sqm, 2),
                "comparable_count": len(prices),
            }

        except Exception as e:
            logger.error(f"[CIAN] Estimation failed: {e}")
            return None

    def _extract_prices(self, soup: BeautifulSoup) -> list[float]:
        """Extract prices per m² from HTML page."""
        prices = []

        # Strategy 1: Find price elements with data attributes
        price_elements = soup.select(
            "[data-name='Price'] span, "
            "span[data-mark='MainPrice'], "
            "[class*='Price'] span, "
            "[class*='price'] span"
        )

        # Strategy 2: Find area elements
        area_elements = soup.select(
            "[data-name='Area'] span, "
            "[class*='Area'] span, "
            "[class*='area'] span"
        )

        # Strategy 3: Try to match price/area pairs from card containers
        cards = soup.select(
            "[data-name='OffersSerpItem'], "
            "[class*='CardSection'], "
            "[class*='listing-item'], "
            "article"
        )

        for card in cards:
            price = self._extract_card_price(card)
            area = self._extract_card_area(card)
            if price and area and area > 0:
                prices.append(price / area)

        # Strategy 4: Fallback — parse all visible prices
        if not prices:
            for el in price_elements:
                price = self._parse_price_element(el)
                if price and price > 500000:  # Filter obvious non-prices
                    prices.append(price)

        return prices

    def _extract_prices_json(self, soup: BeautifulSoup) -> list[float]:
        """Try to extract prices from embedded JSON data."""
        prices = []

        # Look for __NEXT_DATA__ or similar embedded JSON
        scripts = soup.find_all("script", type="application/json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                offers = self._find_offers_in_json(data)
                for offer in offers:
                    price = offer.get("price") or offer.get("bargainTerms", {}).get("price")
                    area = offer.get("totalArea")
                    if price and area and area > 0:
                        prices.append(price / area)
            except (json.JSONDecodeError, AttributeError):
                continue

        return prices

    def _find_offers_in_json(self, data) -> list[dict]:
        """Recursively find offers array in JSON data."""
        if isinstance(data, dict):
            if "offersSerialized" in data:
                return data["offersSerialized"]
            if "offers" in data and isinstance(data["offers"], list):
                return data["offers"]
            for v in data.values():
                result = self._find_offers_in_json(v)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_offers_in_json(item)
                if result:
                    return result
        return []

    def _extract_card_price(self, card) -> Optional[float]:
        """Extract price from a single card element."""
        price_el = card.select_one(
            "[data-name='Price'], [class*='Price'], [class*='price']"
        )
        if price_el:
            return self._parse_price_element(price_el)
        return None

    def _extract_card_area(self, card) -> Optional[float]:
        """Extract area from a single card element."""
        area_el = card.select_one(
            "[data-name='Area'], [class*='Area'], [class*='area']"
        )
        if area_el:
            text = area_el.get_text(strip=True)
            match = re.search(r"([\d]+(?:[.,]\d+)?)", text)
            if match:
                try:
                    return float(match.group(1).replace(",", "."))
                except ValueError:
                    pass
        return None

    def _parse_price_element(self, el) -> Optional[float]:
        """Parse price from an element's text."""
        text = el.get_text(strip=True)
        # Remove currency symbols and spaces
        cleaned = re.sub(r"[^\d]", "", text)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                pass
        return None

    def _remove_outliers(self, prices: list[float]) -> list[float]:
        """Remove outliers using IQR method."""
        if len(prices) < 4:
            return prices

        prices_sorted = sorted(prices)
        q1_idx = len(prices_sorted) // 4
        q3_idx = 3 * len(prices_sorted) // 4
        q1 = prices_sorted[q1_idx]
        q3 = prices_sorted[q3_idx]
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        return [p for p in prices if lower <= p <= upper]

    def batch_estimate(self, properties: list[dict], batch_size: int = 5) -> list[dict]:
        """Estimate market prices for multiple properties."""
        results = []

        for i, prop in enumerate(properties):
            logger.info(f"[CIAN] Estimating {i+1}/{len(properties)}: {prop.get('title', '')[:50]}")

            estimation = self.estimate_market_price(prop)
            results.append(estimation or {})

            # Rotate session periodically
            if (i + 1) % batch_size == 0:
                self._rotate_session()
                self._session = None
                time.sleep(random.uniform(10, 20))

        return results

    def scrape_listings(self, **kwargs) -> list[dict]:
        """Not used — CIAN is for price estimation only."""
        return []
