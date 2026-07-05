"""Enrichment service — orchestrates scraping, geocoding, and market appraisal.

Pipeline:
1. Scrape torgi.gov.ru (main source — includes all auction types)
2. Scrape ETP platforms (supplementary — catches missing lots)
3. Geocode addresses (Yandex Geocoder)
4. Estimate market prices (CIAN)
"""

import time
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuctionProperty, ScrapeLog, SourceType
from scrapers import TorgiGovScraper, CianScraper, EtpScraper
from services.geocoder import geocoder
from config import settings


class EnrichmentService:
    """Orchestrates the full data pipeline: scrape → store → geocode → appraise."""

    async def run_full_pipeline(
        self,
        session: AsyncSession,
        region_code: str = None,
        days_back: int = 30,
    ):
        """Run the complete data collection and enrichment pipeline."""
        start_time = time.time()

        # Step 1: Scrape torgi.gov.ru
        logger.info("=" * 60)
        logger.info("STEP 1: Scraping torgi.gov.ru")
        logger.info("=" * 60)
        await self._scrape_torgi(session, region_code, days_back)

        # Step 2: Scrape ETP (supplementary)
        logger.info("=" * 60)
        logger.info("STEP 2: Scraping ETP platforms")
        logger.info("=" * 60)
        await self._scrape_etp(session, days_back)

        # Step 3: Geocode new properties
        logger.info("=" * 60)
        logger.info("STEP 3: Geocoding addresses")
        logger.info("=" * 60)
        await self._geocode_properties(session)

        # Step 4: Market price estimation via CIAN
        logger.info("=" * 60)
        logger.info("STEP 4: Market price estimation (CIAN)")
        logger.info("=" * 60)
        await self._estimate_market_prices(session)

        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed:.1f}s")

    # --- Scraping ---

    async def _scrape_torgi(
        self,
        session: AsyncSession,
        region_code: str = None,
        days_back: int = 30,
    ):
        """Scrape and store torgi.gov.ru listings."""
        log_entry = ScrapeLog(source=SourceType.TORGIGOV, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            with TorgiGovScraper() as scraper:
                listings = scraper.scrape_listings(
                    region_code=region_code,
                    days_back=days_back,
                )

            new_count, update_count = await self._upsert_listings(session, listings)

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new_count
            log_entry.items_updated = update_count
            log_entry.status = "success"
            await session.flush()

            logger.info(f"[torgi.gov.ru] Stored: {new_count} new, {update_count} updated")

        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[torgi.gov.ru] Scrape failed: {e}")

    async def _scrape_etp(self, session: AsyncSession, days_back: int = 30):
        """Scrape and store ETP listings (supplementary)."""
        log_entry = ScrapeLog(source=SourceType.GOSPLAN, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            total_new = 0
            total_update = 0

            for platform in ["lot-online", "fabrikant"]:
                try:
                    with EtpScraper(platform=platform) as scraper:
                        listings = scraper.scrape_listings(days_back=days_back)

                    new_count, update_count = await self._upsert_listings(session, listings)
                    total_new += new_count
                    total_update += update_count
                except Exception as e:
                    logger.warning(f"[ETP:{platform}] Failed: {e}")

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_new = total_new
            log_entry.items_updated = total_update
            log_entry.status = "success"
            await session.flush()

            logger.info(f"[ETP] Stored: {total_new} new, {total_update} updated")

        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[ETP] Scrape failed: {e}")

    async def _upsert_listings(
        self,
        session: AsyncSession,
        listings: list[dict],
    ) -> tuple[int, int]:
        """Insert or update listings. Returns (new_count, update_count)."""
        new_count = 0
        update_count = 0

        for listing_data in listings:
            existing = await session.execute(
                select(AuctionProperty).where(
                    AuctionProperty.source == listing_data["source"],
                    AuctionProperty.source_id == listing_data["source_id"],
                )
            )
            existing_prop = existing.scalar_one_or_none()

            if existing_prop:
                for key, value in listing_data.items():
                    if key not in ("source", "source_id", "raw_data") and value is not None:
                        setattr(existing_prop, key, value)
                existing_prop.updated_at = datetime.utcnow()
                update_count += 1
            else:
                new_prop = AuctionProperty(**listing_data)
                session.add(new_prop)
                new_count += 1

        await session.flush()
        return new_count, update_count

    # --- Geocoding ---

    async def _geocode_properties(self, session: AsyncSession):
        """Geocode properties that don't have coordinates yet."""
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_geocoded == False,
                AuctionProperty.address.isnot(None),
                AuctionProperty.address != "",
            )
            .limit(200)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need geocoding")
            return

        logger.info(f"Geocoding {len(properties)} properties")

        geocoded = 0
        for prop in properties:
            try:
                coords = geocoder.geocode(prop.address, prop.city)
                if coords:
                    prop.latitude = coords[0]
                    prop.longitude = coords[1]
                    prop.is_geocoded = True
                    geocoded += 1
                else:
                    # Mark as attempted (don't retry forever)
                    prop.is_geocoded = True
            except Exception as e:
                logger.warning(f"Geocode error for '{prop.address[:50]}': {e}")

            time.sleep(0.5)

        await session.flush()
        logger.info(f"Geocoded {geocoded}/{len(properties)}")

    # --- Market Appraisal ---

    async def _estimate_market_prices(self, session: AsyncSession):
        """Estimate market prices for properties without appraisal."""
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_market_appraised == False,
                AuctionProperty.total_area.isnot(None),
                AuctionProperty.start_price.isnot(None),
                AuctionProperty.property_type.in_(["apartment", "house", "room"]),
            )
            .limit(50)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need market appraisal")
            return

        logger.info(f"Estimating market prices for {len(properties)} properties")

        estimated = 0
        with CianScraper() as cian:
            for i, prop in enumerate(properties):
                prop_data = {
                    "city": prop.city or "Москва",
                    "property_type": prop.property_type,
                    "rooms": prop.rooms,
                    "total_area": prop.total_area,
                    "address": prop.address,
                }

                estimation = cian.estimate_market_price(prop_data)

                if estimation:
                    est_per_sqm = estimation.get("price_per_sqm")
                    if est_per_sqm and prop.total_area:
                        prop.market_price = est_per_sqm * prop.total_area

                    if prop.start_price and prop.market_price and prop.market_price > 0:
                        prop.discount_pct = round(
                            (1 - prop.start_price / prop.market_price) * 100, 1
                        )

                    estimated += 1
                    logger.info(
                        f"[CIAN] {prop.title[:40]}: "
                        f"auction={prop.start_price:,.0f}, "
                        f"market={prop.market_price:,.0f}, "
                        f"discount={prop.discount_pct}%"
                    )

                prop.is_market_appraised = True

                # Rotate session every 10 properties
                if (i + 1) % 10 == 0:
                    cian._rotate_session()
                    cian._session = None
                    time.sleep(5)

        await session.flush()
        logger.info(f"Market appraisal: {estimated}/{len(properties)} estimated")


enrichment_service = EnrichmentService()
