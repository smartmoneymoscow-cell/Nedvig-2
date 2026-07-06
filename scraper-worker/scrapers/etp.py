"""Scraper for electronic trading platforms (ЭТП) — additional auction sources.

torgi.gov.ru is the main aggregator, but some lots appear first or exclusively
on the electronic trading platforms (ЭТП). This scraper handles:
- lot-online.ru (Росэлторг / Lot-online)
- fabrikant.ru (Фабрикант)
- utender.ru (UTender)

Note: torgi.gov.ru already aggregates most data including bankruptcy (229-ФЗ).
This scraper is supplementary — it catches lots that may not yet be in torgi.gov.ru.
"""

import re
import json
import hashlib
from datetime import datetime, date
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseScraper
from models import SourceType, AuctionStatus, PropertyType


# ETP codes from torgi.gov.ru (these are the real platform identifiers)
ETP_CODES = {
    "ETP_GPB": "ТЭО Газпромбанка",
    "ETP_RTS": "РТС-Тендер",
    "ETP_MMB": "ММВБ",
    "ETP_FAB": "Фабрикант",
    "ETP_AVT": "Сбербанк-АСТ",
    "ETP_ETP": "Единая ЭТП",
    "ETP_ROS": "Росэлторг",
    "ETP_NEB": "НЭБ",
    "ETP_AVK": "АВК",
}

# URLs for direct platform access
PLATFORM_URLS = {
    "roseltorg": "https://www.roseltorg.ru",
    "lot-online": "https://www.lot-online.ru",
    "fabrikant": "https://www.fabrikant.ru",
    "utender": "https://www.utender.ru",
}


class EtpScraper(BaseScraper):
    """Scraper for electronic trading platforms (ЭТП).

    This is a supplementary scraper. Primary data comes from torgi.gov.ru.
    """

    def __init__(self, platform: str = "lot-online"):
        super().__init__(f"etp-{platform}")
        self.platform = platform
        self.base_url = PLATFORM_URLS.get(platform, PLATFORM_URLS["lot-online"])

    def _detect_property_type(self, text: str) -> PropertyType:
        """Detect property type from text."""
        text = text.lower()
        if any(w in text for w in ["квартир", "комнат", "апартамент"]):
            return PropertyType.APARTMENT
        if any(w in text for w in ["дом", "усадьб", "коттедж"]):
            return PropertyType.HOUSE
        if any(w in text for w in ["земель", "участок", "земля"]):
            return PropertyType.LAND
        if any(w in text for w in ["нежилая", "коммерч", "офис", "магазин", "помещение"]):
            return PropertyType.COMMERCIAL
        if any(w in text for w in ["гараж", "машиноместо"]):
            return PropertyType.GARAGE
        return PropertyType.OTHER

    def scrape_listings(
        self,
        property_type: str = "real_estate",
        days_back: int = 30,
        max_pages: int = 20,
    ) -> list[dict]:
        """
        Scrape listings from the ETP.

        Args:
            property_type: Type filter
            days_back: How many days back
            max_pages: Maximum pages
        """
        all_listings = []

        logger.info(f"[{self.source_name}] Starting scrape: {self.base_url}")

        try:
            # Try the search/listing page
            url = f"{self.base_url}/trades"
            params = {
                "category": "real_estate",
                "status": "active",
                "page": 1,
            }

            for page_num in range(1, max_pages + 1):
                self._throttle(2.0, 5.0)
                params["page"] = page_num

                try:
                    response = self.fetch_with_retry(url, params=params)
                    soup = BeautifulSoup(response.text, "lxml")

                    # Generic card selectors (may need per-platform tuning)
                    cards = soup.select(
                        ".lot-card, .trade-card, .auction-item, "
                        ".lot-item, [class*='lot'], [class*='trade']"
                    )

                    if not cards:
                        logger.info(f"[{self.source_name}] No cards on page {page_num}")
                        break

                    for card in cards:
                        try:
                            listing = self._parse_card(card)
                            if listing:
                                all_listings.append(listing)
                        except Exception as e:
                            logger.warning(f"[{self.source_name}] Card parse error: {e}")

                    logger.info(
                        f"[{self.source_name}] Page {page_num}: {len(cards)} cards"
                    )

                except Exception as e:
                    logger.error(f"[{self.source_name}] Page {page_num} error: {e}")
                    break

        except Exception as e:
            logger.error(f"[{self.source_name}] Scrape failed: {e}")

        logger.info(f"[{self.source_name}] Total: {len(all_listings)} listings")
        return all_listings

    def _parse_card(self, card) -> Optional[dict]:
        """Parse a listing card from HTML."""
        title_el = card.select_one("h2, h3, .title, .name, a")
        title = title_el.get_text(strip=True) if title_el else ""

        link_el = card.select_one("a[href]")
        link = link_el.get("href", "") if link_el else ""

        price_el = card.select_one(".price, .cost, [class*='price']")
        price_text = price_el.get_text(strip=True) if price_el else ""

        address_el = card.select_one(".address, .location, [class*='address']")
        address = address_el.get_text(strip=True) if address_el else ""

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

        return {
            "source": SourceType.ETP,
            "source_id": hashlib.md5(f"{self.platform}:{title}:{link}".encode()).hexdigest()[:16],
            "source_url": link if link.startswith("http") else f"{self.base_url}{link}",
            "title": title,
            "address": address,
            "start_price": price,
            "current_price": price,
            "property_type": self._detect_property_type(title),
            "auction_status": AuctionStatus.ACTIVE,
        }

    def close(self):
        """Clean up."""
        super().close()
