"""Scraper for torgi.gov.ru — Russian government auction portal.

Uses the REAL public API:
GET /new/api/public/lotcards/search

Verified parameters from reverse-engineering and public Scrapy spiders:
- lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER
- byFirstVersion=true
- withFacets=true
- size={page_size} (max 100)
- sort=firstVersionPublicationDate,desc
- page={page_number}
- dynSubjRF={region_code} (OKATO region code, e.g. "77" = Moscow)
- text={search_text} (optional free text)
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
TORGIGOV_LOT_URL = f"{TORGIGOV_BASE}/new/public/lots/lot"

# Real estate category codes on torgi.gov.ru (from actual API facets)
REAL_ESTATE_CATEGORIES = {
    "9":    "Жилые помещения",
    "8":    "Здания",
    "11":   "Нежилые помещения",
    "301":  "Земли населенных пунктов",
    "307":  "Земли с/х назначения",
    "304":  "Земли промышленности",
    "406":  "Имущественный комплекс",
    "10":   "Сооружения",
    "4":    "Объекты незавершённого строительства",
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

# Real OKATO region codes (two-digit)
REGION_CODES = {
    "77": "Москва",
    "78": "Санкт-Петербург",
    "50": "Московская область",
    "47": "Ленинградская область",
    "54": "Новосибирская область",
    "66": "Свердловская область",
    "16": "Республика Татарстан",
    "52": "Нижегородская область",
    "23": "Краснодарский край",
    "30": "Астраханская область",
    "01": "Республика Адыгея",
    "02": "Республика Башкортостан",
    "03": "Республика Бурятия",
    "04": "Республика Алтай",
    "05": "Республика Дагестан",
    "06": "Республика Ингушетия",
    "07": "Кабардино-Балкарская Республика",
    "08": "Республика Калмыкия",
    "09": "Карачаево-Черкесская Республика",
    "10": "Республика Карелия",
    "11": "Республика Коми",
    "12": "Республика Марий Эл",
    "13": "Республика Мордовия",
    "14": "Республика Саха (Якутия)",
    "15": "Республика Северная Осетия — Алания",
    "17": "Республика Тыва",
    "18": "Удмуртская Республика",
    "19": "Республика Хакасия",
    "20": "Чеченская Республика",
    "21": "Чувашская Республика",
    "22": "Алтайский край",
    "24": "Красноярский край",
    "25": "Приморский край",
    "26": "Ставропольский край",
    "27": "Хабаровский край",
    "28": "Амурская область",
    "29": "Архангельская область",
    "31": "Белгородская область",
    "32": "Брянская область",
    "33": "Владимирская область",
    "34": "Волгоградская область",
    "35": "Вологодская область",
    "36": "Воронежская область",
    "37": "Ивановская область",
    "38": "Иркутская область",
    "39": "Калининградская область",
    "40": "Калужская область",
    "41": "Камчатский край",
    "42": "Кемеровская область",
    "43": "Кировская область",
    "44": "Костромская область",
    "45": "Курганская область",
    "46": "Курская область",
    "48": "Липецкая область",
    "49": "Магаданская область",
    "51": "Мурманская область",
    "53": "Омская область",
    "55": "Оренбургская область",
    "56": "Орловская область",
    "57": "Пензенская область",
    "58": "Пермский край",
    "59": "Псковская область",
    "60": "Ростовская область",
    "61": "Рязанская область",
    "62": "Самарская область",
    "63": "Саратовская область",
    "64": "Сахалинская область",
    "65": "Смоленская область",
    "67": "Тамбовская область",
    "68": "Тверская область",
    "69": "Томская область",
    "70": "Тульская область",
    "71": "Тюменская область",
    "72": "Ульяновская область",
    "73": "Челябинская область",
    "74": "Забайкальский край",
    "75": "Ярославская область",
    "76": "Еврейская автономная область",
    "79": "Чукотский автономный округ",
    "83": "Ненецкий автономный округ",
    "86": "Ханты-Мансийский автономный округ — Югра",
    "87": "Ямало-Ненецкий автономный округ",
    "89": "Республика Крым",
    "92": "Севастополь",
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

        if cat_code == "9":
            living_type = self._get_characteristic(card, "typeLivingQuarters")
            if living_type:
                living_type = living_type.lower()
                if "дом" in living_type:
                    return PropertyType.HOUSE
                if "комната" in living_type or "доля" in living_type:
                    return PropertyType.ROOM
            return PropertyType.APARTMENT

        if cat_code in ("301", "307", "304"):
            return PropertyType.LAND

        if cat_code in ("8", "10"):
            purpose = self._get_characteristic(card, "purposeBuilding")
            if purpose and "жилое" in purpose.lower():
                return PropertyType.HOUSE
            return PropertyType.COMMERCIAL

        if cat_code == "11":
            return PropertyType.COMMERCIAL

        if cat_code == "4":
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
        lot_id = card.get("id", "")
        title = card.get("lotName", "")
        description = card.get("lotDescription", "")

        start_price = card.get("priceMin") or card.get("startPrice")

        total_area = (
            self._get_characteristic_float(card, "totalAreaRealty") or
            self._get_characteristic_float(card, "SquareZU")
        )

        # Parse rooms from title
        rooms = None
        room_match = re.search(r"(\d+)\s*[-–]?\s*комн", title, re.IGNORECASE)
        if room_match:
            rooms = int(room_match.group(1))
        elif re.search(r"однокомнатн", title, re.IGNORECASE):
            rooms = 1
        elif re.search(r"двухкомнатн", title, re.IGNORECASE):
            rooms = 2
        elif re.search(r"тр[ёе]хкомнатн", title, re.IGNORECASE):
            rooms = 3
        elif re.search(r"четыр[ёе]хкомнатн", title, re.IGNORECASE):
            rooms = 4

        # Floor from characteristics
        floor = None
        location = self._get_characteristic(card, "locationObjectRealty")
        if location:
            floor_match = re.search(r"(\d+)\s*этаж", location, re.IGNORECASE)
            if floor_match:
                floor = int(floor_match.group(1))

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

        address = title  # lotName typically contains the full address
        region_code = card.get("subjectRFCode", "")

        organizer = None
        for attr in card.get("noticeAttributes", []):
            if "org" in attr.get("code", "").lower():
                organizer = attr.get("value", "")
                break

        result = {
            "source": SourceType.TORGIGOV,
            "source_id": lot_id,
            "source_url": f"{TORGIGOV_LOT_URL}/{lot_id}",
            "title": title,
            "description": description,
            "property_type": self._detect_property_type(card),
            "address": address,
            "region": region_code,
            "city": None,  # Needs geocoding
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

        if result["start_price"] and result["total_area"] and result["total_area"] > 0:
            result["price_per_sqm"] = result["start_price"] / result["total_area"]

        return result

    def scrape_listings(
        self,
        region_code: str = None,
        category_codes: list[str] = None,
        search_text: str = None,
        days_back: int = 30,
        max_pages: int = 100,
        page_size: int = 50,
    ) -> list[dict]:
        """
        Scrape auction listings from torgi.gov.ru using real API.

        Args:
            region_code: OKATO region code (e.g., "77" for Moscow).
            category_codes: List of category codes to filter.
            search_text: Free text search (e.g., "Жилой дом").
            days_back: How many days back to look.
            max_pages: Maximum number of pages to scrape.
            page_size: Items per page (max 100).
        """
        all_listings = []
        page = 0

        if category_codes is None:
            category_codes = list(REAL_ESTATE_CATEGORIES.keys())

        logger.info(
            f"[torgi.gov.ru] Starting scrape: "
            f"region={region_code}, categories={len(category_codes)}, "
            f"search={search_text}, days_back={days_back}"
        )

        if not self._api_session:
            self._api_session = self._create_api_session()

        while page < max_pages:
            try:
                self._throttle(1.0, 3.0)

                # Build real API params (verified from reverse engineering)
                params = {
                    "lotStatus": "PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER",
                    "byFirstVersion": "true",
                    "withFacets": "true",
                    "size": str(min(page_size, 100)),
                    "sort": "firstVersionPublicationDate,desc",
                    "page": str(page),
                }

                if region_code:
                    params["dynSubjRF"] = region_code

                if search_text:
                    params["text"] = search_text

                # Single category filter
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

                # Parse and filter by category
                for lot in lots:
                    lot_cat = lot.get("category", {}).get("code", "")
                    if len(category_codes) > 1 and lot_cat not in category_codes:
                        continue

                    parsed = self._parse_lot_card(lot)
                    all_listings.append(parsed)

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
        """Scrape all real estate categories."""
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
