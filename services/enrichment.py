"""Enrichment service — orchestrates scraping, geocoding, and market appraisal."""

import time
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuctionProperty, ScrapeLog, SourceType
from scrapers import TorgiGovScraper, CianScraper, GosPlanScraper, ProxyManager
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

        torgi_listings = await self._scrape_torgi(session, region_code, days_back)

        # Step 1b: Scrape GosPlan
        logger.info("=" * 60)
        logger.info("STEP 1b: Scraping GosPlan")
        logger.info("=" * 60)
        await self._scrape_gosplan(session, days_back)

        # Step 2: Geocode new properties
        logger.info("=" * 60)
        logger.info("STEP 2: Geocoding addresses")
        logger.info("=" * 60)

        await self._geocode_properties(session)

        # Step 3: Market price estimation via CIAN
        logger.info("=" * 60)
        logger.info("STEP 3: Market price estimation (CIAN)")
        logger.info("=" * 60)

        await self._estimate_market_prices(session)

        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed:.1f}s")

    async def _scrape_torgi(
        self,
        session: AsyncSession,
        region_code: str = None,
        days_back: int = 30,
    ) -> list[AuctionProperty]:
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
                    # Update existing
                    for key, value in listing_data.items():
                        if key not in ("source", "source_id", "raw_data") and value is not None:
                            setattr(existing_prop, key, value)
                    existing_prop.updated_at = datetime.utcnow()
                    update_count += 1
                else:
                    # Create new
                    new_prop = AuctionProperty(**listing_data)
                    session.add(new_prop)
                    new_count += 1

            await session.flush()

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new_count
            log_entry.items_updated = update_count
            log_entry.status = "success"
            await session.flush()

            logger.info(f"[torgi.gov.ru] Stored: {new_count} new, {update_count} updated")
            return []

        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[torgi.gov.ru] Scrape failed: {e}")
            return []

    async def _scrape_gosplan(self, session: AsyncSession, days_back: int = 30):
        """Scrape and store GosPlan listings."""
        log_entry = ScrapeLog(source=SourceType.GOSPLAN, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            with GosPlanScraper() as scraper:
                listings = scraper.scrape_listings(days_back=days_back)

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

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new_count
            log_entry.items_updated = update_count
            log_entry.status = "success"
            await session.flush()

            logger.info(f"[GosPlan] Stored: {new_count} new, {update_count} updated")

        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[GosPlan] Scrape failed: {e}")

    async def _geocode_properties(self, session: AsyncSession):
        """Geocode properties that don't have coordinates yet."""
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_geocoded == False,
                AuctionProperty.address.isnot(None),
                AuctionProperty.address != "",
            )
            .limit(100)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need geocoding")
            return

        logger.info(f"Geocoding {len(properties)} properties")

        for prop in properties:
            coords = geocoder.geocode(prop.address, prop.city)
            if coords:
                prop.latitude = coords[0]
                prop.longitude = coords[1]
                prop.is_geocoded = True
            time.sleep(0.5)  # Rate limit

        await session.flush()
        logger.info(f"Geocoded {sum(1 for p in properties if p.is_geocoded)}/{len(properties)}")

    async def _estimate_market_prices(self, session: AsyncSession):
        """Estimate market prices for properties without appraisal."""
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_market_appraised == False,
                AuctionProperty.total_area.isnot(None),
                AuctionProperty.start_price.isnot(None),
            )
            .limit(20)  # Batch size
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need market appraisal")
            return

        logger.info(f"Estimating market prices for {len(properties)} properties")

        with CianScraper() as cian:
            for prop in properties:
                prop_data = {
                    "city": prop.city or "Москва",
                    "property_type": prop.property_type,
                    "rooms": prop.rooms,
                    "total_area": prop.total_area,
                    "address": prop.address,
                }

                estimation = cian.estimate_market_price(prop_data)

                if estimation:
                    prop.market_price = estimation.get("market_price")
                    if prop.total_area and prop.total_area > 0:
                        est_per_sqm = estimation.get("price_per_sqm")
                        if est_per_sqm:
                            prop.market_price = est_per_sqm * prop.total_area

                    # Calculate discount
                    if prop.start_price and prop.market_price and prop.market_price > 0:
                        prop.discount_pct = round(
                            (1 - prop.start_price / prop.market_price) * 100, 1
                        )

                    prop.is_market_appraised = True
                    logger.info(
                        f"[CIAN] {prop.title[:50]}: "
                        f"auction={prop.start_price:,.0f}, "
                        f"market={prop.market_price:,.0f}, "
                        f"discount={prop.discount_pct}%"
                    )
                else:
                    prop.is_market_appraised = True  # Mark as attempted

        await session.flush()
        logger.info(
            f"Market appraisal: {sum(1 for p in properties if p.market_price)}/{len(properties)} estimated"
        )


enrichment_service = EnrichmentService()
