"""Scraper for ГосПлан (GosPlan) — aggregated government property data.

GosPlan aggregates data from multiple government sources including:
- Росимущество (Federal Property Management Agency)
- Regional auction platforms
- Bankruptcy auction data

This scraper handles the GosPlan API and web interface.
"""

import re
import json
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper
from .proxy_manager import proxy_manager
from models import SourceType, AuctionStatus, PropertyType


GOSPLAN_BASE = "https://gosplan.info"
GOSPLAN_API = "https://gosplan.info/api/v1"
GOSPLAN_SEARCH = "https://gosplan.info/search"


class GosPlanScraper(BaseScraper):
    """Scraper for GosPlan aggregated auction data."""

    def __init__(self):
        super().__init__("gosplan")

    def _detect_property_type(self, text: str) -> PropertyType:
        """Detect property type from text."""
        text = text.lower()
        keywords = {
            PropertyType.APARTMENT: ["квартир", "комнат", "апартамент"],
            PropertyType.HOUSE: ["дом", "усадьб", "коттедж", "таунхаус"],
            PropertyType.LAND: ["земель", "участок", "земля", "поле"],
            PropertyType.COMMERCIAL: ["нежилая", "коммерч", "офис", "магазин", "торгов", "склад"],
            PropertyType.ROOM: ["комната", "доля"],
            PropertyType.GARAGE: ["гараж", "машиноместо", "паркинг"],
        }
        for ptype, kws in keywords.items():
            for kw in kws:
                if kw in text:
                    return ptype
        return PropertyType.OTHER

    def _parse_listing(self, card_data: dict) -> dict:
        """Parse a GosPlan listing into standardized format."""
        title = card_data.get("title") or card_data.get("name", "")
        description = card_data.get("description") or card_data.get("text", "")

        # Parse price
        start_price = None
        for price_field in ["startPrice", "price", "start_price", "cost"]:
            val = card_data.get(price_field)
            if val:
                try:
                    start_price = float(str(val).replace(" ", "").replace(",", "."))
                    break
                except (ValueError, TypeError):
                    continue

        # Parse area
        total_area = None
        for area_field in ["totalArea", "area", "square", "total_area"]:
            val = card_data.get(area_field)
            if val:
                try:
                    total_area = float(str(val).replace(" ", "").replace(",", "."))
                    break
                except (ValueError, TypeError):
                    continue

        # Parse dates
        publish_date = None
        for date_field in ["publishDate", "date", "created", "publish_date"]:
            raw = card_data.get(date_field)
            if raw:
                parsed = self._parse_date(str(raw)) or self._parse_datetime(str(raw))
                if parsed:
                    publish_date = parsed.date() if isinstance(parsed, datetime) else parsed
                    break

        result = {
            "source": SourceType.GOSPLAN,
            "source_id": str(card_data.get("id") or card_data.get("lotId") or hashlib.md5(title.encode()).hexdigest()[:16]),
            "source_url": card_data.get("url") or card_data.get("link", ""),
            "title": title,
            "description": description,
            "property_type": self._detect_property_type(f"{title} {description}"),
            "address": card_data.get("address") or card_data.get("location", ""),
            "region": card_data.get("region") or card_data.get("regionName", ""),
            "city": card_data.get("city") or card_data.get("cityName", ""),
            "total_area": total_area,
            "start_price": start_price,
            "current_price": start_price,
            "publish_date": publish_date,
            "lot_number": card_data.get("lotNumber") or card_data.get("number", ""),
            "organizer": card_data.get("organizer") or card_data.get("organizerName", ""),
            "auction_status": AuctionStatus.ACTIVE,
            "raw_data": card_data,
        }

        # Price per sqm
        if result["start_price"] and result["total_area"] and result["total_area"] > 0:
            result["price_per_sqm"] = result["start_price"] / result["total_area"]

        return result

    def scrape_listings(
        self,
        city: str = None,
        property_type: str = None,
        days_back: int = 30,
        max_pages: int = 50,
    ) -> list[dict]:
        """
        Scrape property listings from GosPlan.

        Args:
            city: City filter
            property_type: Property type filter
            days_back: How many days back to look
            max_pages: Maximum pages to scrape
        """
        all_listings = []
        page = 1

        logger.info(f"[GosPlan] Starting scrape: city={city}, days_back={days_back}")

        while page <= max_pages:
            try:
                self._throttle(1.0, 3.0)

                # Try API first
                params = {
                    "page": page,
                    "limit": 20,
                    "type": "real_estate",
                }
                if city:
                    params["city"] = city
                if property_type:
                    params["property_type"] = property_type
                if days_back:
                    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                    params["date_from"] = date_from

                try:
                    response = self.fetch_with_retry(f"{GOSPLAN_API}/lots", params=params)
                    data = response.json()

                    lots = data.get("data") or data.get("items") or data.get("lots") or []
                    if not lots:
                        if isinstance(data, list):
                            lots = data
                        else:
                            break

                    for lot in lots:
                        all_listings.append(self._parse_listing(lot))

                    logger.info(f"[GosPlan] Page {page}: {len(lots)} lots")

                    if len(lots) < 20:
                        break

                    page += 1

                except Exception as api_err:
                    logger.warning(f"[GosPlan] API failed: {api_err}, trying HTML fallback")
                    html_listings = self._scrape_html(page, city)
                    if not html_listings:
                        break
                    all_listings.extend(html_listings)
                    page += 1

            except Exception as e:
                logger.error(f"[GosPlan] Error on page {page}: {e}")
                self._rotate_session()
                break

        logger.info(f"[GosPlan] Scrape complete: {len(all_listings)} total")
        return all_listings

    def _scrape_html(self, page: int, city: str = None) -> list[dict]:
        """Fallback HTML scraping."""
        try:
            params = {"page": page}
            if city:
                params["city"] = city

            response = self.fetch_with_retry(GOSPLAN_SEARCH, params=params)
            soup = BeautifulSoup(response.text, "lxml")
            listings = []

            # Generic card parsing
            cards = soup.select(".lot-card, .auction-card, .property-card, [class*='lot'], [class*='card']")
            for card in cards:
                try:
                    title_el = card.select_one("h2, h3, .title, .name, a")
                    title = title_el.get_text(strip=True) if title_el else ""

                    link_el = card.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""

                    price_el = card.select_one(".price, .cost, [class*='price']")
                    price_text = price_el.get_text(strip=True) if price_el else ""

                    address_el = card.select_one(".address, .location, [class*='address']")
                    address = address_el.get_text(strip=True) if address_el else ""

                    if title:
                        result = {
                            "source": SourceType.GOSPLAN,
                            "source_id": hashlib.md5(title.encode()).hexdigest()[:16],
                            "source_url": link if link.startswith("http") else f"{GOSPLAN_BASE}{link}",
                            "title": title,
                            "address": address,
                            "start_price": self._parse_price(price_text),
                            "current_price": self._parse_price(price_text),
                            "property_type": self._detect_property_type(title),
                            "auction_status": AuctionStatus.ACTIVE,
                        }
                        listings.append(result)

                except Exception as e:
                    logger.warning(f"[GosPlan] Failed to parse card: {e}")

            logger.info(f"[GosPlan] HTML page {page}: {len(listings)} listings")
            return listings

        except Exception as e:
            logger.error(f"[GosPlan] HTML scrape failed: {e}")
            return []
