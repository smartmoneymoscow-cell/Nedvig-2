"""Scraper for torgi.gov.ru — Russian government auction portal.

Uses the REAL public API discovered via web research:
GET /new/api/public/lotcards/search

Response structure:
- content[]: lot cards with nested characteristics
- pageable: pagination info
- categoryFacet: category counts
- totalElements: total count
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


TORGIGOV_BASE = "https://torgi.gov.ru"
TORGIGOV_SEARCH_API = f"{TORGIGOV_BASE}/new/api/public/lotcards/search"
TORGIGOV_EXPORT_API = f"{TORGIGOV_BASE}/new/api/public/lotcards/export/excel"
TORGIGOV_LOT_URL = f"{TORGIGOV_BASE}/new/public/lots/lot"

# Real estate category codes on torgi.gov.ru (from actual API facets)
REAL_ESTATE_CATEGORIES = {
    "9":    "Жилые помещения",          # Apartments, houses
    "8":    "Здания",                    # Buildings
    "11":   "Нежилые помещения",         # Non-residential premises
    "301":  "Земли населенных пунктов",  # Land in settlements
    "307":  "Земли с/х назначения",      # Agricultural land
    "304":  "Земли промышленности",      # Industrial land
    "406":  "Имущественный комплекс",    # Property complex
    "10":   "Сооружения",               # Structures
    "4":    "Объекты незавершённого строительства",  # Unfinished construction
}

# Status mapping from real API values
STATUS_MAP = {
    "PUBLISHED": AuctionStatus.UPCOMING,
    "APPLICATIONS_SUBMISSION": AuctionStatus.ACTIVE,
    "DETERMINING_WINNER": AuctionStatus.ACTIVE,
    "COMPLETED": AuctionStatus.COMPLETED,
    "CANCELLED": AuctionStatus.CANCELLED,
    "ANULLED": AuctionStatus.CANCELLED,
}


class TorgiGovScraper(BaseScraper):
    """Scraper for torgi.gov.ru auction listings using real public API."""

    def __init__(self):
        super().__init__("torgi.gov.ru")
        self._api_session = None

    def _create_api_session(self):
        """Create session with correct headers for torgi.gov.ru API."""
        session = self._create_session()
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": f"{TORGIGOV_BASE}/new/public/lots/reg",
            "Origin": TORGIGOV_BASE,
            "OrganizationId": "null",
            "BranchId": "null",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
        return session

    def _get_characteristic(self, card: dict, code: str) -> Optional[str]:
        """Extract a characteristic value by code from the lot card."""
        for char in card.get("characteristics", []):
            if char.get("code") == code:
                val = char.get("characteristicValue")
                if val is not None:
                    # Handle multiselect (list of dicts)
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        return val[0].get("name", "")
                    return str(val)
        return None

    def _get_characteristic_float(self, card: dict, code: str) -> Optional[float]:
        """Extract a numeric characteristic value."""
        val = self._get_characteristic(card, code)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return None

    def _detect_property_type(self, card: dict) -> PropertyType:
        """Detect property type from category and characteristics."""
        category = card.get("category", {})
        cat_code = category.get("code", "")
        cat_name = category.get("name", "").lower()

        # Check category
        if cat_code == "9":  # Жилые помещения
            living_type = self._get_characteristic(card, "typeLivingQuarters")
            if living_type:
                living_type = living_type.lower()
                if "дом" in living_type:
                    return PropertyType.HOUSE
                if "комната" in living_type or "доля" in living_type:
                    return PropertyType.ROOM
            return PropertyType.APARTMENT

        if cat_code in ("301", "307", "304"):  # Земли
            return PropertyType.LAND

        if cat_code in ("8", "10"):  # Здания, сооружения
            purpose = self._get_characteristic(card, "purposeBuilding")
            if purpose and "жилое" in purpose.lower():
                return PropertyType.HOUSE
            return PropertyType.COMMERCIAL

        if cat_code == "11":  # Нежилые помещения
            return PropertyType.COMMERCIAL

        if cat_code == "4":  # Объекты незавершённого строительства
            return PropertyType.OTHER

        # Fallback: check title
        title = card.get("lotName", "").lower()
        if any(w in title for w in ["квартир", "комнат"]):
            return PropertyType.APARTMENT
        if any(w in title for w in ["дом", "жилой дом"]):
            return PropertyType.HOUSE
        if any(w in title for w in ["земельный участок", "участок"]):
            return PropertyType.LAND
        if any(w in title for w in ["нежилое", "помещение", "офис"]):
            return PropertyType.COMMERCIAL
        if any(w in title for w in ["гараж", "машиноместо"]):
            return PropertyType.GARAGE

        return PropertyType.OTHER

    def _parse_lot_card(self, card: dict) -> dict:
        """Parse a lot card from the real API response."""
        # Basic info
        lot_id = card.get("id", "")
        title = card.get("lotName", "")
        description = card.get("lotDescription", "")

        # Price
        start_price = card.get("priceMin")

        # Area — extract from characteristics
        total_area = (
            self._get_characteristic_float(card, "totalAreaRealty") or
            self._get_characteristic_float(card, "SquareZU")  # Land area
        )

        # Rooms — extract from title (e.g., "3-комнатная квартира", "Однокомнатная")
        rooms = None
        room_match = re.search(r"(\d+)\s*[-–]?\s*комн", title, re.IGNORECASE)
        if room_match:
            rooms = int(room_match.group(1))
        elif re.search(r"однокомнатн", title, re.IGNORECASE):
            rooms = 1
        elif re.search(r"двухкомнатн|двухкомнатн", title, re.IGNORECASE):
            rooms = 2
        elif re.search(r"трехкомнатн|трёхкомнатн", title, re.IGNORECASE):
            rooms = 3
        elif re.search(r"четырехкомнатн|четырёхкомнатн", title, re.IGNORECASE):
            rooms = 4

        # Floor — extract from characteristic
        floor = None
        location = self._get_characteristic(card, "locationObjectRealty")
        if location:
            floor_match = re.search(r"(\d+)\s*этаж", location, re.IGNORECASE)
            if floor_match:
                floor = int(floor_match.group(1))

        # Total floors
        total_floors = None
        floors_str = self._get_characteristic(card, "numberFloors")
        if floors_str:
            try:
                total_floors = int(floors_str)
            except (ValueError, TypeError):
                pass

        # Status
        lot_status = card.get("lotStatus", "")
        auction_status = STATUS_MAP.get(lot_status, AuctionStatus.UPCOMING)

        # Dates
        publish_date = None
        pub_str = card.get("noticeFirstVersionPublicationDate")
        if pub_str:
            try:
                # Format: "2024-05-05T07:02:03.81Z"
                publish_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                pass

        auction_end = None
        end_str = card.get("biddEndTime")
        if end_str:
            try:
                auction_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Address — from lotName (usually contains address)
        address = title  # lotName typically contains the full address

        # Region
        region_code = card.get("subjectRFCode", "")

        # Organizer — not directly available, but can be extracted from noticeAttributes
        organizer = None
        for attr in card.get("noticeAttributes", []):
            if "org" in attr.get("code", "").lower():
                organizer = attr.get("value", "")
                break

        # Category info
        category = card.get("category", {})
        category_name = category.get("name", "")

        # Cadastral number
        cadastral = (
            self._get_characteristic(card, "cadastralNumberRealty") or
            self._get_characteristic(card, "CadastralNumber")
        )

        # Build result
        result = {
            "source": SourceType.TORGIGOV,
            "source_id": lot_id,
            "source_url": f"{TORGIGOV_LOT_URL}/{lot_id}",
            "title": title,
            "description": description,
            "property_type": self._detect_property_type(card),
            "address": address,
            "region": region_code,
            "city": None,  # Not directly available, need geocoding
            "latitude": None,
            "longitude": None,
            "total_area": total_area,
            "rooms": rooms,
            "floor": floor,
            "total_floors": total_floors,
            "start_price": start_price,
            "current_price": start_price,
            "auction_status": auction_status,
            "auction_date_end": auction_end,
            "publish_date": publish_date,
            "lot_number": str(card.get("lotNumber", "")),
            "organizer": organizer,
            "raw_data": card,
        }

        # Price per sqm
        if result["start_price"] and result["total_area"] and result["total_area"] > 0:
            result["price_per_sqm"] = result["start_price"] / result["total_area"]

        return result

    def scrape_listings(
        self,
        region_code: str = None,
        category_codes: list[str] = None,
        days_back: int = 30,
        max_pages: int = 100,
        page_size: int = 50,
    ) -> list[dict]:
        """
        Scrape auction listings from torgi.gov.ru using real API.

        Args:
            region_code: Region OKATO code (e.g., "77" for Moscow)
            category_codes: List of category codes to filter.
                Default: real estate categories.
            days_back: How many days back to look
            max_pages: Maximum number of pages to scrape
            page_size: Items per page (max 100)
        """
        all_listings = []
        page = 0

        # Default: all real estate categories
        if category_codes is None:
            category_codes = list(REAL_ESTATE_CATEGORIES.keys())

        logger.info(
            f"[torgi.gov.ru] Starting scrape: "
            f"region={region_code}, categories={len(category_codes)}, days_back={days_back}"
        )

        # Ensure session
        if not self._api_session:
            self._api_session = self._create_api_session()

        # Calculate date filter
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d.%m.%Y")

        while page < max_pages:
            try:
                self._throttle(1.0, 3.0)

                # Build real API params
                params = {
                    "lotStatus": "PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER",
                    "byFirstVersion": "true",
                    "withFacets": "true",
                    "size": str(min(page_size, 100)),
                    "sort": "firstVersionPublicationDate,desc",
                    "page": str(page),
                }

                # Optional filters
                if region_code:
                    params["dynSubjRF"] = region_code

                # Category filter — if single category, use catCode param
                # If multiple, we'll filter in post-processing
                if len(category_codes) == 1:
                    params["catCode"] = category_codes[0]

                logger.info(f"[torgi.gov.ru] Fetching page {page + 1}")

                response = self._api_session.get(
                    TORGIGOV_SEARCH_API,
                    params=params,
                    timeout=30,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"[torgi.gov.ru] API returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    self._rotate_session()
                    self._api_session = self._create_api_session()
                    if page > 0:
                        page += 1
                        continue
                    break

                data = response.json()
                lots = data.get("content", [])

                if not lots:
                    logger.info(f"[torgi.gov.ru] No lots on page {page + 1}")
                    break

                # Parse and filter
                for lot in lots:
                    # Filter by category if multiple
                    lot_cat = lot.get("category", {}).get("code", "")
                    if len(category_codes) > 1 and lot_cat not in category_codes:
                        continue

                    parsed = self._parse_lot_card(lot)
                    all_listings.append(parsed)

                # Pagination info
                total_pages = data.get("totalPages", 0)
                total_elements = data.get("totalElements", 0)

                logger.info(
                    f"[torgi.gov.ru] Page {page + 1}/{total_pages}: "
                    f"{len(lots)} lots, total={total_elements}"
                )

                if page >= total_pages - 1:
                    break

                page += 1

            except Exception as e:
                logger.error(f"[torgi.gov.ru] Error on page {page + 1}: {e}")
                self._rotate_session()
                self._api_session = self._create_api_session()
                if page > 0:
                    page += 1
                else:
                    break

        logger.info(f"[torgi.gov.ru] Scrape complete: {len(all_listings)} total")
        return all_listings

    def scrape_listings_all_real_estate(
        self,
        region_code: str = None,
        days_back: int = 30,
    ) -> list[dict]:
        """Scrape all real estate categories (apartments, houses, land, commercial)."""
        return self.scrape_listings(
            region_code=region_code,
            category_codes=list(REAL_ESTATE_CATEGORIES.keys()),
            days_back=days_back,
        )

    def scrape_listings_by_category(
        self,
        category_code: str,
        region_code: str = None,
        days_back: int = 30,
    ) -> list[dict]:
        """Scrape listings for a specific category code."""
        return self.scrape_listings(
            region_code=region_code,
            category_codes=[category_code],
            days_back=days_back,
        )

    def get_categories(self) -> dict:
        """Get available categories with counts from the API."""
        if not self._api_session:
            self._api_session = self._create_api_session()

        try:
            response = self._api_session.get(
                TORGIGOV_SEARCH_API,
                params={
                    "lotStatus": "PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER",
                    "byFirstVersion": "true",
                    "withFacets": "true",
                    "size": "1",
                    "sort": "firstVersionPublicationDate,desc",
                },
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                facets = data.get("categoryFacet", [])
                return {f["_id"]: f["count"] for f in facets}
        except Exception as e:
            logger.error(f"[torgi.gov.ru] Failed to get categories: {e}")

        return {}

    def scrape_moscow(self, days_back: int = 30) -> list[dict]:
        """Convenience: scrape Moscow region (code 77)."""
        return self.scrape_listings(region_code="77", days_back=days_back)

    def scrape_spb(self, days_back: int = 30) -> list[dict]:
        """Convenience: scrape Saint Petersburg (code 78)."""
        return self.scrape_listings(region_code="78", days_back=days_back)
