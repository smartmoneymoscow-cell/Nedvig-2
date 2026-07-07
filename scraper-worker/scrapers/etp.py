"""Scraper for electronic trading platforms (ЭТП) — additional auction sources.

Primary data comes from torgi.gov.ru (which aggregates most lots).
This scraper catches supplementary lots from major ЭТП platforms:
- lot-online.ru (Росэлторг)
- fabrikant.ru (Фабрикант)
- utender.ru (UTender)
- roseltorg.ru (Росэлторг)

Strategy:
1. curl_cffi with TLS fingerprint (primary)
2. Playwright for JS-heavy sites (fallback)
3. Parse both API responses and HTML
"""

import re
import json
import hashlib
from datetime import datetime, date
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseScraper
from models import SourceType, AuctionStatus, PropertyType


# Platform configurations
PLATFORMS = {
    "lot-online": {
        "base_url": "https://www.lot-online.ru",
        "search_url": "https://www.lot-online.ru/auction/commerce/",
        "name": "Лот-Онлайн (Росэлторг)",
    },
    "fabrikant": {
        "base_url": "https://www.fabrikant.ru",
        "search_url": "https://www.fabrikant.ru/trades/procedure/search/",
        "name": "Фабрикант",
    },
    "utender": {
        "base_url": "https://www.utender.ru",
        "search_url": "https://www.utender.ru/trades/",
        "name": "ЮТендер",
    },
    "roseltorg": {
        "base_url": "https://www.roseltorg.ru",
        "search_url": "https://www.roseltorg.ru/auction/search/",
        "name": "Росэлторг",
    },
}

# Property type keywords
PROPERTY_KEYWORDS = {
    PropertyType.APARTMENT: ["квартир", "комнат", "апартамент"],
    PropertyType.HOUSE: ["дом", "усадьб", "коттедж", "таунхаус"],
    PropertyType.LAND: ["земель", "участок", "земля", "поле"],
    PropertyType.COMMERCIAL: ["нежилая", "коммерч", "офис", "магазин", "помещение", "склад"],
    PropertyType.GARAGE: ["гараж", "машиноместо", "паркинг"],
}


class EtpScraper(BaseScraper):
    """Scraper for electronic trading platforms (ЭТП).

    Supplementary scraper — primary data comes from torgi.gov.ru.
    """

    def __init__(self, platform: str = "lot-online"):
        config = PLATFORMS.get(platform, PLATFORMS["lot-online"])
        super().__init__(f"etp-{platform}")
        self.platform = platform
        self.base_url = config["base_url"]
        self.search_url = config["search_url"]
        self.platform_name = config["name"]

    def _detect_property_type(self, text: str) -> PropertyType:
        """Detect property type from text."""
        if not text:
            return PropertyType.OTHER
        text = text.lower()
        for ptype, keywords in PROPERTY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return ptype
        return PropertyType.OTHER

    def _is_real_estate(self, text: str) -> bool:
        """Check if text relates to real estate."""
        if not text:
            return False
        text = text.lower()
        return any(kw in text for kw in [
            "квартир", "дом", "земель", "помещение", "нежилое",
            "коммерч", "офис", "склад", "гараж", "машиноместо",
            "участок", "комната", "жилое", "недвижим", "строени",
            "помещен", "здани", "сооружен",
        ])

    def scrape_listings(
        self,
        days_back: int = 30,
        max_pages: int = 20,
        **kwargs,
    ) -> list[dict]:
        """
        Scrape listings from the ETP.

        Args:
            days_back: How many days back
            max_pages: Maximum pages
        """
        all_listings = []

        logger.info(f"[{self.source_name}] Starting scrape: {self.platform_name}")

        # Strategy 1: Try API endpoints first
        api_listings = self._try_api()
        if api_listings:
            all_listings.extend(api_listings)
            logger.info(f"[{self.source_name}] API returned {len(api_listings)} items")

        # Strategy 2: HTML scraping
        if not all_listings:
            html_listings = self._scrape_html(max_pages)
            all_listings.extend(html_listings)
            logger.info(f"[{self.source_name}] HTML returned {len(html_listings)} items")

        logger.info(f"[{self.source_name}] Total: {len(all_listings)} listings")
        return all_listings

    def _try_api(self) -> list[dict]:
        """Try known API endpoints for the platform."""
        listings = []

        api_endpoints = self._get_api_endpoints()

        for endpoint in api_endpoints:
            try:
                response = self.fetch_with_retry(endpoint, params={"limit": 50})
                ct = response.headers.get("content-type", "")

                if "json" in ct:
                    data = response.json()
                    items = self._extract_items_from_json(data)
                    for item in items:
                        listing = self._parse_api_item(item)
                        if listing:
                            listings.append(listing)
                    if listings:
                        break
            except Exception as e:
                logger.debug(f"[{self.source_name}] API {endpoint} failed: {e}")

        return listings

    def _get_api_endpoints(self) -> list[str]:
        """Get API endpoint URLs for the platform."""
        endpoints = {
            "lot-online": [
                f"{self.base_url}/api/v1/trades",
                f"{self.base_url}/api/trades/search",
                f"{self.base_url}/api/auction/list",
            ],
            "fabrikant": [
                f"{self.base_url}/api/v1/procedures",
                f"{self.base_url}/api/procedures/search",
                f"{self.base_url}/api/trades",
            ],
            "utender": [
                f"{self.base_url}/api/v1/trades",
                f"{self.base_url}/api/trades",
            ],
            "roseltorg": [
                f"{self.base_url}/api/v1/auctions",
                f"{self.base_url}/api/auctions/search",
            ],
        }
        return endpoints.get(self.platform, [])

    def _extract_items_from_json(self, data) -> list:
        """Extract items array from JSON response."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["items", "data", "results", "trades", "procedures",
                        "auctions", "lots", "rows", "content"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    def _parse_api_item(self, item: dict) -> Optional[dict]:
        """Parse a listing from API JSON response."""
        title = (
            item.get("title") or
            item.get("name") or
            item.get("description") or
            item.get("subject") or
            ""
        )

        if not title or len(title) < 3:
            return None

        # Filter for real estate
        if not self._is_real_estate(title):
            category = str(item.get("category", "") or item.get("type", "")).lower()
            if not self._is_real_estate(category):
                return None

        # Parse price
        price = None
        for field in ["price", "startPrice", "start_price", "initialPrice",
                      "cost", "sum", "amount", "priceMin"]:
            val = item.get(field)
            if val:
                try:
                    price = float(str(val).replace(" ", "").replace(",", "."))
                    if price > 0:
                        break
                except (ValueError, TypeError):
                    continue

        # Parse date
        publish_date = None
        for field in ["publishDate", "date", "created", "publish_date", "startDate"]:
            raw = item.get(field)
            if raw:
                parsed = self._parse_date(str(raw)) or self._parse_datetime(str(raw))
                if parsed:
                    publish_date = parsed.date() if isinstance(parsed, datetime) else parsed
                    break

        source_id = str(
            item.get("id") or
            item.get("tradeId") or
            item.get("lotId") or
            hashlib.md5(f"{self.platform}:{title}".encode()).hexdigest()[:16]
        )

        url = item.get("url") or item.get("link") or item.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        return {
            "source": SourceType.ETP,
            "source_id": source_id,
            "source_url": url or self.search_url,
            "title": title,
            "description": item.get("description") or item.get("text", ""),
            "property_type": self._detect_property_type(title),
            "address": item.get("address") or item.get("location", ""),
            "region": item.get("region") or item.get("regionName", ""),
            "city": item.get("city") or item.get("cityName", ""),
            "start_price": price,
            "current_price": price,
            "publish_date": publish_date,
            "lot_number": str(item.get("lotNumber") or item.get("number", "")),
            "organizer": item.get("organizer") or item.get("organizerName", ""),
            "auction_status": AuctionStatus.ACTIVE,
        }

    def _scrape_html(self, max_pages: int = 20) -> list[dict]:
        """Scrape listings from HTML pages."""
        all_listings = []

        try:
            for page_num in range(1, max_pages + 1):
                self._throttle(2.0, 5.0)

                try:
                    url = self.search_url
                    params = {"page": page_num}

                    response = self.fetch_with_retry(url, params=params)
                    soup = BeautifulSoup(response.text, "lxml")

                    # Try platform-specific selectors
                    cards = self._find_cards(soup)

                    if not cards:
                        logger.info(f"[{self.source_name}] No cards on page {page_num}")
                        break

                    for card in cards:
                        try:
                            listing = self._parse_html_card(card)
                            if listing:
                                all_listings.append(listing)
                        except Exception as e:
                            logger.debug(f"[{self.source_name}] Card parse error: {e}")

                    logger.info(f"[{self.source_name}] Page {page_num}: {len(cards)} cards")

                    # Check if there's a next page
                    if not self._has_next_page(soup):
                        break

                except Exception as e:
                    logger.error(f"[{self.source_name}] Page {page_num} error: {e}")
                    break

        except Exception as e:
            logger.error(f"[{self.source_name}] HTML scrape failed: {e}")

        return all_listings

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """Find listing cards in HTML using multiple selector strategies."""
        # Strategy 1: Common card class patterns
        selectors = [
            ".lot-card", ".trade-card", ".auction-item", ".procedure-card",
            ".lot-item", ".trade-item", ".search-result",
            "[class*='lot']", "[class*='trade']", "[class*='auction']",
            "[class*='procedure']", "[class*='result-item']",
            "article", ".card", ".item",
        ]

        for selector in selectors:
            cards = soup.select(selector)
            # Filter: must contain meaningful content
            cards = [c for c in cards if len(c.get_text(strip=True)) > 20]
            if cards and len(cards) >= 2:  # At least 2 to avoid false positives
                return cards

        # Strategy 2: Table rows
        tables = soup.select("table")
        for table in tables:
            rows = table.select("tbody tr")
            if rows and len(rows) >= 2:
                return rows

        return []

    def _parse_html_card(self, card) -> Optional[dict]:
        """Parse a listing card from HTML."""
        # Extract title
        title_el = card.select_one(
            "h2, h3, h4, .title, .name, a, [class*='title'], [class*='name']"
        )
        title = title_el.get_text(strip=True) if title_el else ""

        # Extract link
        link_el = card.select_one("a[href]")
        link = link_el.get("href", "") if link_el else ""

        # Extract price
        price_el = card.select_one(
            ".price, .cost, .sum, [class*='price'], [class*='cost'], [class*='sum']"
        )
        price_text = price_el.get_text(strip=True) if price_el else ""

        # Extract address
        addr_el = card.select_one(
            ".address, .location, [class*='address'], [class*='location']"
        )
        address = addr_el.get_text(strip=True) if addr_el else ""

        # Extract date
        date_el = card.select_one(
            ".date, time, [class*='date'], [class*='time']"
        )
        date_text = date_el.get_text(strip=True) if date_el else ""

        # Use card text as fallback
        if not title:
            text = card.get_text(strip=True)
            title = text[:100] if text else ""

        if not title or len(title) < 5:
            return None

        # Filter for real estate
        if not self._is_real_estate(title):
            return None

        # Parse price
        price = None
        if price_text:
            cleaned = re.sub(r"[^\d]", "", price_text)
            if cleaned:
                try:
                    price = float(cleaned)
                except ValueError:
                    pass

        # Parse date
        publish_date = None
        if date_text:
            publish_date = self._parse_date(date_text)

        source_id = hashlib.md5(
            f"{self.platform}:{title}:{link}".encode()
        ).hexdigest()[:16]

        return {
            "source": SourceType.ETP,
            "source_id": source_id,
            "source_url": link if link.startswith("http") else urljoin(self.base_url, link),
            "title": title,
            "address": address,
            "start_price": price,
            "current_price": price,
            "property_type": self._detect_property_type(title),
            "publish_date": publish_date,
            "auction_status": AuctionStatus.ACTIVE,
        }

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page."""
        next_selectors = [
            'a.next', 'button.next', '.pagination .next',
            'a:contains("Следующая")', 'a:contains("Далее")',
            'a[rel="next"]', '.pager .next',
        ]
        for selector in next_selectors:
            try:
                el = soup.select_one(selector)
                if el and not el.get("disabled"):
                    return True
            except Exception:
                pass
        return False

    def close(self):
        """Clean up."""
        super().close()
