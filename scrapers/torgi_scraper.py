"""Scraper for torgi.gov.ru — Russian government auction portal.

Handles:
- API-based search for real estate lots
- Pagination through result pages
- Detail page scraping for additional info
- Anti-bot bypass via TLS fingerprinting + proxy rotation
"""

import re
import json
import time
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper
from .proxy_manager import proxy_manager
from models import SourceType, AuctionStatus, PropertyType


# torgi.gov.ru search API endpoint
TORGIGOV_API_URL = "https://torgi.gov.ru/new/public/lots/reg"
TORGIGOV_SEARCH_API = "https://torgi.gov.ru/new/api/public/lotcards/search"
TORGIGOV_LOT_API = "https://torgi.gov.ru/new/api/public/lotcards/{lotId}"
TORGIGOV_BASE = "https://torgi.gov.ru"

# Real estate category codes on torgi.gov.ru
PROPERTY_CATEGORIES = {
    "apartment": ["жилая", "квартир", "квартира", "комнат"],
    "house": ["дом", "жилой дом", "усадьб"],
    "land": ["земель", "участок", "земля"],
    "commercial": ["нежилая", "коммерч", "офис", "магазин", "помещение"],
    "garage": ["гараж", "машиноместо", "паркинг"],
}


class TorgiGovScraper(BaseScraper):
    """Scraper for torgi.gov.ru auction listings."""

    def __init__(self):
        super().__init__("torgi.gov.ru")
        self._api_session = None

    def _create_api_session(self):
        """Create session specifically for the torgi.gov.ru API."""
        session = self._create_session()
        session.headers.update({
            "Referer": "https://torgi.gov.ru/new/public/lots/reg",
            "Origin": "https://torgi.gov.ru",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
        })
        return session

    def _detect_property_type(self, title: str, description: str = "") -> PropertyType:
        """Detect property type from title and description."""
        text = f"{title} {description}".lower()
        for ptype, keywords in PROPERTY_CATEGORIES.items():
            for kw in keywords:
                if kw in text:
                    return PropertyType(ptype)
        return PropertyType.OTHER

    def _detect_auction_status(self, raw_data: dict) -> AuctionStatus:
        """Determine auction status from raw data."""
        status_str = raw_data.get("lotStatus", "").lower()
        if "завершен" in status_str or "completed" in status_str:
            return AuctionStatus.COMPLETED
        if "отменен" in status_str or "cancelled" in status_str:
            return AuctionStatus.CANCELLED
        if "идут" in status_str or "active" in status_str:
            return AuctionStatus.ACTIVE
        # Check by dates
        now = datetime.now()
        end_date = raw_data.get("biddingEndDate")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_dt < now:
                    return AuctionStatus.COMPLETED
            except (ValueError, TypeError):
                pass
        return AuctionStatus.UPCOMING

    def _parse_lot_card(self, card: dict) -> dict:
        """Parse a lot card from the API response."""
        title = card.get("lotName", "")
        description = card.get("lotDescription", "")

        # Parse price
        start_price = None
        price_str = card.get("startPrice") or card.get("currentPrice") or card.get("price")
        if price_str:
            try:
                start_price = float(str(price_str).replace(" ", "").replace(",", "."))
            except (ValueError, TypeError):
                pass

        # Parse area
        total_area = None
        area_str = card.get("totalArea") or card.get("area")
        if area_str:
            try:
                total_area = float(str(area_str).replace(" ", "").replace(",", "."))
            except (ValueError, TypeError):
                pass

        # Parse dates
        publish_date = None
        for date_field in ["publishDate", "createDate", "publicationDate"]:
            raw_date = card.get(date_field)
            if raw_date:
                publish_date = self._parse_date(raw_date) or self._parse_datetime(str(raw_date))
                if publish_date and isinstance(publish_date, datetime):
                    publish_date = publish_date.date()
                if publish_date:
                    break

        auction_start = self._parse_datetime(card.get("biddingStartDate", ""))
        auction_end = self._parse_datetime(card.get("biddingEndDate", ""))

        # Build result
        result = {
            "source": SourceType.TORGIGOV,
            "source_id": str(card.get("id") or card.get("lotId") or card.get("lotNumber", "")),
            "source_url": f"{TORGIGOV_BASE}/new/public/lots/lot/{card.get('id', '')}",
            "title": title,
            "description": description,
            "property_type": self._detect_property_type(title, description),
            "address": card.get("lotAddress") or card.get("address", ""),
            "region": card.get("regionName") or card.get("region", ""),
            "city": card.get("cityName") or card.get("city", ""),
            "total_area": total_area,
            "start_price": start_price,
            "current_price": start_price,
            "auction_status": self._detect_auction_status(card),
            "auction_date_start": auction_start,
            "auction_date_end": auction_end,
            "publish_date": publish_date,
            "lot_number": card.get("lotNumber", ""),
            "organizer": card.get("organizerName") or card.get("organizer", ""),
            "deposit": self._parse_price(str(card.get("deposit", ""))) if card.get("deposit") else None,
            "raw_data": card,
        }

        # Calculate price per sqm
        if result["start_price"] and result["total_area"] and result["total_area"] > 0:
            result["price_per_sqm"] = result["start_price"] / result["total_area"]

        return result

    def scrape_listings(
        self,
        region_code: str = None,
        property_category: str = None,
        days_back: int = 30,
        max_pages: int = 50,
        status_filter: str = None,
    ) -> list[dict]:
        """
        Scrape auction listings from torgi.gov.ru.

        Args:
            region_code: Region OKATO code (e.g., "77" for Moscow)
            property_category: Category filter
            days_back: How many days back to look
            max_pages: Maximum number of pages to scrape
            status_filter: Filter by auction status
        """
        all_listings = []
        page = 0
        page_size = 20

        logger.info(f"[torgi.gov.ru] Starting scrape: region={region_code}, days_back={days_back}")

        # Ensure we have a session
        if not self._api_session:
            self._api_session = self._create_api_session()

        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d.%m.%Y")

        while page < max_pages:
            try:
                self._throttle(1.0, 3.0)

                # Build search params for torgi.gov.ru API
                params = {
                    "dynSubjRF": region_code or "",
                    "lotPropertyType": "2",  # 2 = real estate
                    "biddType": "",
                    "publishDateFrom": date_from,
                    "lotStatus": status_filter or "",
                    "catCode": property_category or "",
                    "startPriceFrom": "",
                    "startPriceTo": "",
                    "page": str(page),
                    "size": str(page_size),
                    "sort": "publishDate,desc",
                }

                logger.info(f"[torgi.gov.ru] Fetching page {page + 1}")

                # Try API endpoint first
                response = None
                try:
                    response = self._api_session.get(
                        TORGIGOV_SEARCH_API,
                        params=params,
                        timeout=30,
                    )
                except Exception as e:
                    logger.warning(f"[torgi.gov.ru] API request failed: {e}")

                if response and response.status_code == 200:
                    try:
                        data = response.json()
                        lots = data.get("content") or data.get("data") or data.get("lots") or []

                        if not lots:
                            # Try alternate response structure
                            if isinstance(data, list):
                                lots = data
                            else:
                                logger.info(f"[torgi.gov.ru] No lots found on page {page + 1}")
                                break

                        for lot in lots:
                            parsed = self._parse_lot_card(lot)
                            all_listings.append(parsed)

                        logger.info(f"[torgi.gov.ru] Page {page + 1}: found {len(lots)} lots")

                        if len(lots) < page_size:
                            break

                        page += 1
                        continue

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"[torgi.gov.ru] Failed to parse API response: {e}")

                # Fallback: scrape HTML page
                if not response or response.status_code != 200:
                    listings = self._scrape_html_page(page)
                    if not listings:
                        break
                    all_listings.extend(listings)
                    page += 1

            except Exception as e:
                logger.error(f"[torgi.gov.ru] Error on page {page + 1}: {e}")
                self._rotate_session()
                self._api_session = self._create_api_session()
                if page > 0:
                    page += 1
                else:
                    break

        logger.info(f"[torgi.gov.ru] Scrape complete: {len(all_listings)} total listings")
        return all_listings

    def _scrape_html_page(self, page: int) -> list[dict]:
        """Fallback: scrape HTML search results page."""
        try:
            url = f"{TORGIGOV_API_URL}?page={page}"
            response = self.fetch_with_retry(url)

            soup = BeautifulSoup(response.text, "lxml")
            listings = []

            # Parse lot cards from HTML
            lot_cards = soup.select(".lot-card, .lotItem, [class*='lot-card'], tr.lot-row")

            for card in lot_cards:
                try:
                    title_el = card.select_one("a.lot-title, .lotName a, h3 a, td:nth-child(2)")
                    title = title_el.get_text(strip=True) if title_el else ""
                    link = title_el.get("href", "") if title_el else ""

                    price_el = card.select_one(".lot-price, .price, td:nth-child(3)")
                    price_text = price_el.get_text(strip=True) if price_el else ""

                    address_el = card.select_one(".lot-address, .address, td:nth-child(4)")
                    address = address_el.get_text(strip=True) if address_el else ""

                    date_el = card.select_one(".lot-date, .date, td:nth-child(5)")
                    date_text = date_el.get_text(strip=True) if date_el else ""

                    # Extract lot ID from link
                    lot_id = ""
                    if link:
                        match = re.search(r"/lot/(\d+)", link)
                        if match:
                            lot_id = match.group(1)

                    if title or lot_id:
                        result = {
                            "source": SourceType.TORGIGOV,
                            "source_id": lot_id or hashlib.md5(title.encode()).hexdigest()[:16],
                            "source_url": f"{TORGIGOV_BASE}{link}" if link else "",
                            "title": title,
                            "address": address,
                            "start_price": self._parse_price(price_text),
                            "current_price": self._parse_price(price_text),
                            "publish_date": self._parse_date(date_text),
                            "property_type": self._detect_property_type(title),
                            "auction_status": AuctionStatus.ACTIVE,
                        }
                        listings.append(result)

                except Exception as e:
                    logger.warning(f"[torgi.gov.ru] Failed to parse lot card: {e}")
                    continue

            logger.info(f"[torgi.gov.ru] HTML page {page}: {len(listings)} listings")
            return listings

        except Exception as e:
            logger.error(f"[torgi.gov.ru] HTML scrape failed: {e}")
            return []

    def get_lot_details(self, lot_id: str) -> Optional[dict]:
        """Fetch detailed information for a specific lot."""
        try:
            url = TORGIGOV_LOT_API.format(lotId=lot_id)
            response = self.fetch_with_retry(url)
            data = response.json()
            return self._parse_lot_card(data)
        except Exception as e:
            logger.error(f"[torgi.gov.ru] Failed to get lot {lot_id}: {e}")
            return None

    def scrape_moscow(self, days_back: int = 30) -> list[dict]:
        """Convenience: scrape Moscow region (code 77)."""
        return self.scrape_listings(region_code="77", days_back=days_back)

    def scrape_spb(self, days_back: int = 30) -> list[dict]:
        """Convenience: scrape Saint Petersburg (code 78)."""
        return self.scrape_listings(region_code="78", days_back=days_back)
