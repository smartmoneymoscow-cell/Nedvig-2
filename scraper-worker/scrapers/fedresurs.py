"""Scraper for Fedresurs (bankrot.fedresurs.ru) — Russian bankruptcy auction portal.

Fedresurs (Единый федеральный реестр сведений о банкротстве) publishes
property auctions from bankruptcy proceedings. This is a major source of
below-market real estate deals.

The site is an SPA (Angular/Vue). Data is loaded via internal API endpoints.
This scraper uses Playwright for JS rendering + API interception.

Note: This replaces the previous GosPlanScraper which targeted the wrong source.
"""

import re
import json
import hashlib
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional

from loguru import logger

from .base import BaseScraper
from models import SourceType, AuctionStatus, PropertyType


FEDRESURS_BASE = "https://bankrot.fedresurs.ru"
FEDRESURS_API = "https://bankrot.fedresurs.ru/api"

# Property type keywords for detection
PROPERTY_KEYWORDS = {
    PropertyType.APARTMENT: ["квартир", "комнат", "апартамент", "жилое помещение"],
    PropertyType.HOUSE: ["дом", "усадьб", "коттедж", "таунхаус", "жилое строение"],
    PropertyType.LAND: ["земель", "участок", "земля", "поле", "с/х"],
    PropertyType.COMMERCIAL: ["нежилая", "коммерч", "офис", "магазин", "торгов", "склад", "помещение"],
    PropertyType.ROOM: ["комната", "доля"],
    PropertyType.GARAGE: ["гараж", "машиноместо", "паркинг"],
}


class FedresursScraper(BaseScraper):
    """Scraper for Fedresurs bankruptcy property auctions.

    Uses Playwright for JS-rendered content (the site is an SPA).
    Falls back to httpx if Playwright is unavailable.
    """

    def __init__(self):
        super().__init__("fedresurs")
        self._playwright = None
        self._browser = None
        self._page = None

    def _detect_property_type(self, text: str) -> PropertyType:
        """Detect property type from text."""
        text = text.lower()
        for ptype, keywords in PROPERTY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return ptype
        return PropertyType.OTHER

    def _init_playwright(self):
        """Initialize Playwright browser for JS rendering."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
            )
            context = self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            self._page = context.new_page()

            # Stealth: override navigator.webdriver
            self._page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            logger.info("[Fedresurs] Playwright initialized")
            return True
        except ImportError:
            logger.warning("[Fedresurs] Playwright not installed, using httpx fallback")
            return False
        except Exception as e:
            logger.error(f"[Fedresurs] Playwright init failed: {e}")
            return False

    def _scrape_with_playwright(
        self,
        days_back: int = 30,
        max_pages: int = 20,
    ) -> list[dict]:
        """Scrape using Playwright (JS rendering)."""
        all_listings = []

        if not self._page:
            if not self._init_playwright():
                return self._scrape_with_httpx(days_back, max_pages)

        try:
            # Navigate to the search page
            self._page.goto(
                f"{FEDRESURS_BASE}/TradeList",
                wait_until="networkidle",
                timeout=30000,
            )
            self._page.wait_for_timeout(3000)

            # Set filters: real estate category
            # Try to select property type filter
            try:
                # Look for category/type selector
                type_selectors = [
                    'select[name*="type"]',
                    'select[name*="category"]',
                    '[data-test="category-select"]',
                    '.category-select',
                ]
                for sel in type_selectors:
                    el = self._page.query_selector(sel)
                    if el:
                        el.select_option(label="Недвижимость")
                        self._page.wait_for_timeout(1000)
                        break
            except Exception as e:
                logger.debug(f"[Fedresurs] Could not set category filter: {e}")

            for page_num in range(max_pages):
                self._throttle(2.0, 5.0)

                # Extract auction cards from the page
                cards = self._page.query_selector_all(
                    '.trade-card, .auction-item, .lot-card, '
                    '[class*="trade"], [class*="lot"], '
                    'tr[class*="row"], .list-item'
                )

                if not cards:
                    # Try alternative: get data from intercepted API responses
                    logger.info(f"[Fedresurs] No cards found on page {page_num + 1}")
                    break

                for card in cards:
                    try:
                        listing = self._parse_playwright_card(card)
                        if listing:
                            all_listings.append(listing)
                    except Exception as e:
                        logger.warning(f"[Fedresurs] Card parse error: {e}")

                logger.info(f"[Fedresurs] Page {page_num + 1}: {len(cards)} cards")

                # Try to go to next page
                next_btn = self._page.query_selector(
                    'button.next, a.next, [aria-label="Next"], '
                    '.pagination .next, button:has-text("Следующая")'
                )
                if next_btn and next_btn.is_enabled():
                    next_btn.click()
                    self._page.wait_for_timeout(2000)
                else:
                    break

        except Exception as e:
            logger.error(f"[Fedresurs] Playwright scrape failed: {e}")

        return all_listings

    def _parse_playwright_card(self, card) -> Optional[dict]:
        """Parse a card element from Playwright."""
        title_el = card.query_selector(
            'h2, h3, .title, .name, a, [class*="title"]'
        )
        title = title_el.inner_text().strip() if title_el else ""

        link_el = card.query_selector('a[href]')
        link = link_el.get_attribute("href") if link_el else ""

        price_el = card.query_selector(
            '.price, .cost, [class*="price"], [class*="cost"]'
        )
        price_text = price_el.inner_text().strip() if price_el else ""

        address_el = card.query_selector(
            '.address, .location, [class*="address"], [class*="location"]'
        )
        address = address_el.inner_text().strip() if address_el else ""

        date_el = card.query_selector(
            '.date, time, [class*="date"], [class*="time"]'
        )
        date_text = date_el.inner_text().strip() if date_el else ""

        if not title:
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
            f"fedresurs:{title}:{link}".encode()
        ).hexdigest()[:16]

        return {
            "source": SourceType.FEDRESURS,
            "source_id": source_id,
            "source_url": link if link.startswith("http") else f"{FEDRESURS_BASE}{link}",
            "title": title,
            "description": "",
            "property_type": self._detect_property_type(title),
            "address": address,
            "region": None,
            "city": None,
            "start_price": price,
            "current_price": price,
            "publish_date": publish_date,
            "auction_status": AuctionStatus.ACTIVE,
        }

    def _scrape_with_httpx(
        self,
        days_back: int = 30,
        max_pages: int = 20,
    ) -> list[dict]:
        """Fallback: scrape with httpx (limited without JS rendering)."""
        all_listings = []

        logger.info("[Fedresurs] Using httpx fallback (JS content may be missing)")

        try:
            # Try known API endpoints (may change)
            api_endpoints = [
                f"{FEDRESURS_API}/v1/trades",
                f"{FEDRESURS_API}/trades/search",
                f"{FEDRESURS_BASE}/api/trades",
            ]

            for endpoint in api_endpoints:
                try:
                    params = {
                        "limit": 50,
                        "offset": 0,
                        "category": "real_estate",
                    }

                    response = self.fetch_with_retry(endpoint, params=params)
                    data = response.json()

                    items = (
                        data.get("items") or
                        data.get("data") or
                        data.get("results") or
                        data.get("trades") or
                        []
                    )

                    if items:
                        for item in items:
                            listing = self._parse_api_item(item)
                            if listing:
                                all_listings.append(listing)
                        logger.info(f"[Fedresurs] API endpoint {endpoint}: {len(items)} items")
                        break

                except Exception as e:
                    logger.debug(f"[Fedresurs] API endpoint {endpoint} failed: {e}")
                    continue

            if not all_listings:
                # Try HTML scraping as last resort
                try:
                    response = self.fetch_with_retry(FEDRESURS_BASE)
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, "lxml")

                    # Look for embedded JSON data
                    scripts = soup.find_all("script", type="application/json")
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            items = self._find_trades_in_json(data)
                            for item in items:
                                listing = self._parse_api_item(item)
                                if listing:
                                    all_listings.append(listing)
                        except (json.JSONDecodeError, AttributeError):
                            continue

                    if not all_listings:
                        # Parse visible HTML cards
                        cards = soup.select(
                            ".trade-card, .auction-item, .lot-card, "
                            "[class*='trade'], [class*='lot']"
                        )
                        for card in cards:
                            title_el = card.select_one("h2, h3, .title, a")
                            title = title_el.get_text(strip=True) if title_el else ""

                            link_el = card.select_one("a[href]")
                            link = link_el.get("href", "") if link_el else ""

                            if title:
                                source_id = hashlib.md5(
                                    f"fedresurs:{title}:{link}".encode()
                                ).hexdigest()[:16]
                                all_listings.append({
                                    "source": SourceType.FEDRESURS,
                                    "source_id": source_id,
                                    "source_url": link if link.startswith("http") else f"{FEDRESURS_BASE}{link}",
                                    "title": title,
                                    "property_type": self._detect_property_type(title),
                                    "auction_status": AuctionStatus.ACTIVE,
                                })

                except Exception as e:
                    logger.error(f"[Fedresurs] HTML scrape failed: {e}")

        except Exception as e:
            logger.error(f"[Fedresurs] httpx scrape failed: {e}")

        logger.info(f"[Fedresurs] Scrape complete: {len(all_listings)} total")
        return all_listings

    def _parse_api_item(self, item: dict) -> Optional[dict]:
        """Parse a trade item from API response."""
        title = (
            item.get("title") or
            item.get("name") or
            item.get("description", "")
        )

        if not title:
            return None

        # Parse price
        price = None
        for field in ["price", "startPrice", "start_price", "initialPrice", "cost"]:
            val = item.get(field)
            if val:
                try:
                    price = float(str(val).replace(" ", "").replace(",", "."))
                    break
                except (ValueError, TypeError):
                    continue

        # Parse date
        publish_date = None
        for field in ["publishDate", "date", "created", "publish_date"]:
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
            hashlib.md5(title.encode()).hexdigest()[:16]
        )

        url = item.get("url") or item.get("link", "")

        return {
            "source": SourceType.FEDRESURS,
            "source_id": source_id,
            "source_url": url if url.startswith("http") else f"{FEDRESURS_BASE}{url}",
            "title": title,
            "description": item.get("description") or item.get("text", ""),
            "property_type": self._detect_property_type(title),
            "address": item.get("address") or item.get("location", ""),
            "region": item.get("region") or item.get("regionName", ""),
            "city": item.get("city") or item.get("cityName", ""),
            "start_price": price,
            "current_price": price,
            "publish_date": publish_date,
            "lot_number": item.get("lotNumber") or item.get("number", ""),
            "organizer": item.get("organizer") or item.get("organizerName", ""),
            "auction_status": AuctionStatus.ACTIVE,
        }

    def _find_trades_in_json(self, data) -> list[dict]:
        """Recursively find trades array in JSON data."""
        if isinstance(data, dict):
            if "trades" in data and isinstance(data["trades"], list):
                return data["trades"]
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            for v in data.values():
                result = self._find_trades_in_json(v)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_trades_in_json(item)
                if result:
                    return result
        return []

    def scrape_listings(
        self,
        days_back: int = 30,
        max_pages: int = 20,
        **kwargs,
    ) -> list[dict]:
        """
        Scrape property listings from Fedresurs.

        Args:
            days_back: How many days back to look.
            max_pages: Maximum pages to scrape.
        """
        logger.info(f"[Fedresurs] Starting scrape: days_back={days_back}")

        # Try Playwright first (SPA site), fall back to httpx
        try:
            return self._scrape_with_playwright(days_back, max_pages)
        except Exception as e:
            logger.warning(f"[Fedresurs] Playwright failed: {e}, falling back to httpx")
            return self._scrape_with_httpx(days_back, max_pages)

    def close(self):
        """Clean up Playwright resources."""
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        super().close()
