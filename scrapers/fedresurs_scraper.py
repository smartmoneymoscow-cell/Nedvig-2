"""Scraper for Fedresurs (bankrot.fedresurs.ru) — Russian bankruptcy auction portal.

Fedresurs is an Angular SPA. Data is loaded via XHR after JS rendering.
This scraper uses Playwright to:
1. Render the SPA
2. Intercept XHR responses to capture trade data
3. Parse the rendered DOM as fallback

Strategy:
- Primary: Playwright with XHR interception (most reliable for SPA)
- Fallback 1: Playwright DOM parsing
- Fallback 2: curl_cffi with known API patterns
"""

import re
import json
import hashlib
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional

from loguru import logger

from .base_scraper import BaseScraper
from models import SourceType, AuctionStatus, PropertyType


FEDRESURS_BASE = "https://bankrot.fedresurs.ru"
FEDRESURS_TRADE_LIST = f"{FEDRESURS_BASE}/TradeList"

# Property type keywords for detection
PROPERTY_KEYWORDS = {
    PropertyType.APARTMENT: [
        "квартир", "комнат", "апартамент", "жилое помещение",
        "студия", "однокомнатн", "двухкомнатн", "трёхкомнатн",
    ],
    PropertyType.HOUSE: [
        "дом", "усадьб", "коттедж", "таунхаус", "жилое строение",
        "часть дома", "домовладение",
    ],
    PropertyType.LAND: [
        "земель", "участок", "земля", "поле", "с/х",
        "земельный участок", "дачный участок",
    ],
    PropertyType.COMMERCIAL: [
        "нежилая", "коммерч", "офис", "магазин", "торгов",
        "склад", "помещение", "нежилое", "торговый",
        "производственное", "административное",
    ],
    PropertyType.ROOM: ["комната", "доля", "часть квартиры"],
    PropertyType.GARAGE: ["гараж", "машиноместо", "паркинг", "бокс"],
}

# XHR URL patterns to intercept (Angular typically calls these)
XHR_PATTERNS = [
    "/api/",
    "/backend/",
    "trade",
    "auction",
    "lot",
    "search",
    "list",
    "sfactmessage",
]


class FedresursScraper(BaseScraper):
    """Scraper for Fedresurs bankruptcy property auctions.

    Uses Playwright for JS rendering + XHR interception.
    Falls back to curl_cffi if Playwright is unavailable.
    """

    def __init__(self):
        super().__init__("fedresurs")
        self._playwright = None
        self._browser = None
        self._page = None
        self._intercepted_data: list[dict] = []

    def _detect_property_type(self, text: str) -> PropertyType:
        """Detect property type from text using keyword matching."""
        if not text:
            return PropertyType.OTHER
        text = text.lower()
        for ptype, keywords in PROPERTY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return ptype
        return PropertyType.OTHER

    def _init_playwright(self) -> bool:
        """Initialize Playwright browser for JS rendering."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
            context = self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = context.new_page()

            # Stealth overrides
            self._page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en']
                });
                window.chrome = {runtime: {}};
            """)

            logger.info("[Fedresurs] Playwright initialized")
            return True
        except ImportError:
            logger.warning("[Fedresurs] Playwright not installed")
            return False
        except Exception as e:
            logger.error(f"[Fedresurs] Playwright init failed: {e}")
            return False

    def _setup_xhr_interception(self):
        """Set up XHR response interception to capture API data."""
        self._intercepted_data = []

        def handle_response(response):
            url = response.url.lower()
            # Check if this response matches our patterns
            if any(pat in url for pat in XHR_PATTERNS):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = response.json()
                        if isinstance(data, (dict, list)):
                            self._intercepted_data.append({
                                "url": response.url,
                                "data": data,
                                "status": response.status,
                            })
                            logger.debug(f"[Fedresurs] Intercepted XHR: {response.url}")
                except Exception:
                    pass

        self._page.on("response", handle_response)

    def _scrape_with_playwright(
        self,
        days_back: int = 30,
        max_pages: int = 20,
    ) -> list[dict]:
        """Scrape using Playwright with XHR interception."""
        all_listings = []

        if not self._page:
            if not self._init_playwright():
                logger.info("[Fedresurs] Falling back to curl_cffi")
                return self._scrape_with_curl_cffi(days_back, max_pages)

        try:
            # Set up XHR interception before navigation
            self._setup_xhr_interception()

            logger.info(f"[Fedresurs] Navigating to {FEDRESURS_TRADE_LIST}")
            self._page.goto(
                FEDRESURS_TRADE_LIST,
                wait_until="networkidle",
                timeout=30000,
            )
            # Wait for Angular to render
            self._page.wait_for_timeout(5000)

            # Try to extract data from intercepted XHR responses
            if self._intercepted_data:
                logger.info(f"[Fedresurs] Intercepted {len(self._intercepted_data)} XHR responses")
                for item in self._intercepted_data:
                    listings = self._parse_intercepted_data(item["data"])
                    all_listings.extend(listings)

            # If no data from XHR, try DOM parsing
            if not all_listings:
                logger.info("[Fedresurs] No data from XHR, trying DOM parsing")
                all_listings = self._parse_dom(max_pages)

            # Try pagination
            if all_listings and max_pages > 1:
                for page_num in range(2, max_pages + 1):
                    self._intercepted_data.clear()
                    try:
                        next_btn = self._page.query_selector(
                            'button.next, a.next, [aria-label="Следующая"], '
                            '.pagination .next, button:has-text("Следующая"), '
                            'a:has-text("Следующая"), li.next > a'
                        )
                        if next_btn and next_btn.is_enabled():
                            self._throttle(2.0, 4.0)
                            next_btn.click()
                            self._page.wait_for_timeout(3000)

                            # Check intercepted data for new page
                            for item in self._intercepted_data:
                                listings = self._parse_intercepted_data(item["data"])
                                all_listings.extend(listings)

                            if not self._intercepted_data:
                                # DOM fallback for pagination
                                page_listings = self._parse_dom(1)
                                all_listings.extend(page_listings)

                            logger.info(f"[Fedresurs] Page {page_num}: total={len(all_listings)}")
                        else:
                            break
                    except Exception as e:
                        logger.warning(f"[Fedresurs] Pagination error on page {page_num}: {e}")
                        break

        except Exception as e:
            logger.error(f"[Fedresurs] Playwright scrape failed: {e}")

        logger.info(f"[Fedresurs] Scrape complete: {len(all_listings)} total")
        return all_listings

    def _parse_intercepted_data(self, data) -> list[dict]:
        """Parse listings from intercepted XHR JSON data."""
        listings = []

        # Handle different response structures
        items = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ["items", "data", "results", "trades", "content", "rows"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            # Try nested
            if not items:
                for v in data.values():
                    if isinstance(v, dict):
                        for key in ["items", "data", "results", "trades"]:
                            if key in v and isinstance(v[key], list):
                                items = v[key]
                                break
                    if items:
                        break

        if not items:
            return listings

        for item in items:
            listing = self._parse_trade_item(item)
            if listing:
                listings.append(listing)

        return listings

    def _parse_trade_item(self, item: dict) -> Optional[dict]:
        """Parse a single trade item from API response."""
        # Try various field names (API might use different naming)
        title = (
            item.get("title") or
            item.get("name") or
            item.get("description") or
            item.get("lotName") or
            item.get("lotDescription") or
            item.get("subject") or
            ""
        )

        if not title or len(title) < 3:
            return None

        # Filter for real estate
        is_real_estate = False
        for keyword in ["квартир", "дом", "земель", "помещение", "нежилое",
                        "коммерч", "офис", "склад", "гараж", "машиноместо",
                        "участок", "комната", "жилое", "помещение"]:
            if keyword in title.lower():
                is_real_estate = True
                break

        if not is_real_estate:
            # Check category/type fields
            category = str(item.get("category", "") or item.get("type", "")).lower()
            if not any(kw in category for kw in ["недвижим", "имуществ", "строени", "помещен"]):
                return None

        # Parse price
        price = None
        for field in ["price", "startPrice", "start_price", "initialPrice",
                      "cost", "sum", "amount", "priceMin", "startSum"]:
            val = item.get(field)
            if val:
                try:
                    price = float(str(val).replace(" ", "").replace(",", "."))
                    if price > 0:
                        break
                except (ValueError, TypeError):
                    continue

        # Parse dates
        publish_date = None
        for field in ["publishDate", "date", "created", "publish_date",
                      "publicationDate", "noticeDate"]:
            raw = item.get(field)
            if raw:
                parsed = self._parse_date(str(raw)) or self._parse_datetime(str(raw))
                if parsed:
                    publish_date = parsed.date() if isinstance(parsed, datetime) else parsed
                    break

        # Source ID
        source_id = str(
            item.get("id") or
            item.get("tradeId") or
            item.get("lotId") or
            item.get("number") or
            hashlib.md5(title.encode()).hexdigest()[:16]
        )

        # URL
        url = item.get("url") or item.get("link") or item.get("href", "")
        if url and not url.startswith("http"):
            url = f"{FEDRESURS_BASE}{url}"

        # Address
        address = (
            item.get("address") or
            item.get("location") or
            item.get("lotAddress") or
            ""
        )

        # City/Region
        city = (
            item.get("city") or
            item.get("cityName") or
            item.get("regionName") or
            ""
        )
        region = item.get("region") or item.get("regionName") or ""

        return {
            "source": SourceType.FEDRESURS,
            "source_id": source_id,
            "source_url": url or FEDRESURS_TRADE_LIST,
            "title": title,
            "description": item.get("description") or item.get("text", ""),
            "property_type": self._detect_property_type(title),
            "address": address,
            "region": region,
            "city": city,
            "start_price": price,
            "current_price": price,
            "publish_date": publish_date,
            "lot_number": str(item.get("lotNumber") or item.get("number", "")),
            "organizer": item.get("organizer") or item.get("organizerName", ""),
            "auction_status": AuctionStatus.ACTIVE,
        }

    def _parse_dom(self, max_pages: int = 1) -> list[dict]:
        """Parse listings from rendered DOM (fallback)."""
        all_listings = []

        if not self._page:
            return all_listings

        # Angular typically renders cards with these patterns
        card_selectors = [
            # Angular component selectors
            'app-trade-card', 'app-lot-card', 'app-auction-item',
            # Common class patterns
            '.trade-card', '.lot-card', '.auction-item', '.search-result-item',
            '.trade-item', '.list-item', '.card-item',
            # Table rows
            'table tbody tr', '.results-table tr',
            # Generic containers with trade-like content
            '[class*="trade"]', '[class*="lot"]', '[class*="auction"]',
            '[class*="result"]', '[class*="search-item"]',
        ]

        for selector in card_selectors:
            cards = self._page.query_selector_all(selector)
            if cards and len(cards) > 0:
                logger.info(f"[Fedresurs] Found {len(cards)} cards with selector: {selector}")
                for card in cards:
                    try:
                        listing = self._parse_dom_card(card)
                        if listing:
                            all_listings.append(listing)
                    except Exception as e:
                        logger.debug(f"[Fedresurs] DOM card parse error: {e}")
                break

        return all_listings

    def _parse_dom_card(self, card) -> Optional[dict]:
        """Parse a single card from DOM element."""
        # Extract text content
        text = card.inner_text().strip()
        if not text or len(text) < 10:
            return None

        # Try to extract structured data
        title = ""
        link = ""
        price_text = ""
        address = ""
        date_text = ""

        # Title: first significant text or link
        title_el = card.query_selector(
            'h2, h3, h4, .title, .name, a, [class*="title"], [class*="name"]'
        )
        if title_el:
            title = title_el.inner_text().strip()

        # Link
        link_el = card.query_selector('a[href]')
        if link_el:
            link = link_el.get_attribute("href") or ""

        # Price
        price_el = card.query_selector(
            '.price, .cost, .sum, [class*="price"], [class*="cost"], [class*="sum"]'
        )
        if price_el:
            price_text = price_el.inner_text().strip()

        # Address
        addr_el = card.query_selector(
            '.address, .location, [class*="address"], [class*="location"]'
        )
        if addr_el:
            address = addr_el.inner_text().strip()

        # Date
        date_el = card.query_selector(
            '.date, time, [class*="date"], [class*="time"]'
        )
        if date_el:
            date_text = date_el.inner_text().strip()

        # Use full text as fallback for title
        if not title:
            title = text[:200]

        # Filter for real estate
        if not any(kw in title.lower() for kw in [
            "квартир", "дом", "земель", "помещение", "нежилое",
            "коммерч", "офис", "склад", "гараж", "машиноместо",
            "участок", "комната", "жилое",
        ]):
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

    def _scrape_with_curl_cffi(
        self,
        days_back: int = 30,
        max_pages: int = 20,
    ) -> list[dict]:
        """Fallback: scrape with curl_cffi (limited without JS rendering)."""
        all_listings = []

        logger.info("[Fedresurs] Using curl_cffi fallback (SPA content will be limited)")

        try:
            session = self._create_session()

            # Try the main page first to get cookies
            resp = session.get(FEDRESURS_TRADE_LIST, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"[Fedresurs] Main page returned {resp.status_code}")
                return all_listings

            # Try common API endpoint patterns
            api_patterns = [
                f"{FEDRESURS_BASE}/api/v1/trades",
                f"{FEDRESURS_BASE}/api/trades/search",
                f"{FEDRESURS_BASE}/api/trades",
                f"{FEDRESURS_BASE}/backend/trades/search",
                f"{FEDRESURS_BASE}/backend/api/v1/trades",
            ]

            for endpoint in api_patterns:
                try:
                    params = {
                        "limit": 50,
                        "offset": 0,
                        "category": "real_estate",
                    }
                    response = session.get(endpoint, params=params, timeout=15)
                    if response.status_code == 200:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            data = response.json()
                            items = self._parse_intercepted_data(data)
                            if items:
                                all_listings.extend(items)
                                logger.info(f"[Fedresurs] API {endpoint}: {len(items)} items")
                                break
                except Exception as e:
                    logger.debug(f"[Fedresurs] API {endpoint} failed: {e}")

            # If no API data, try parsing the HTML shell
            if not all_listings:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")

                # Look for embedded JSON (Angular often puts initial data in scripts)
                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string and ("trade" in script.string.lower() or
                                          "auction" in script.string.lower()):
                        try:
                            # Try to extract JSON from script content
                            json_match = re.search(
                                r'(?:window\.__INITIAL_STATE__|window\.data)\s*=\s*({.+?});',
                                script.string
                            )
                            if json_match:
                                data = json.loads(json_match.group(1))
                                items = self._parse_intercepted_data(data)
                                all_listings.extend(items)
                        except (json.JSONDecodeError, AttributeError):
                            pass

        except Exception as e:
            logger.error(f"[Fedresurs] curl_cffi scrape failed: {e}")

        logger.info(f"[Fedresurs] curl_cffi scrape complete: {len(all_listings)} total")
        return all_listings

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

        # Try Playwright first (SPA needs JS rendering)
        try:
            return self._scrape_with_playwright(days_back, max_pages)
        except Exception as e:
            logger.warning(f"[Fedresurs] Playwright failed: {e}")
            return self._scrape_with_curl_cffi(days_back, max_pages)

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
