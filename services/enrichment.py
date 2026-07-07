"""Enrichment service — orchestrates scraping, geocoding, and market appraisal."""

import asyncio
import time
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuctionProperty, ScrapeLog, SourceType


class EnrichmentService:
    async def run_full_pipeline(self, session: AsyncSession, region_code: str = None, days_back: int = 30):
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("STEP 1: Scraping torgi.gov.ru")
        logger.info("=" * 60)
        await self._scrape_torgi(session, region_code, days_back)

        logger.info("=" * 60)
        logger.info("STEP 2: Scraping Fedresurs (bankruptcy)")
        logger.info("=" * 60)
        await self._scrape_fedresurs(session, days_back)

        logger.info("=" * 60)
        logger.info("STEP 3: Scraping ETP platforms")
        logger.info("=" * 60)
        await self._scrape_etp(session, days_back)

        logger.info("=" * 60)
        logger.info("STEP 4: Geocoding addresses")
        logger.info("=" * 60)
        await self._geocode_properties(session)

        logger.info("=" * 60)
        logger.info("STEP 5: Market price estimation (CIAN)")
        logger.info("=" * 60)
        await self._estimate_market_prices(session)

        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed:.1f}s")

    async def _scrape_torgi(self, session: AsyncSession, region_code: str = None, days_back: int = 30):
        log_entry = ScrapeLog(source=SourceType.TORGIGOV, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            def _run():
                from scrapers.torgi_gov import TorgiGovScraper
                with TorgiGovScraper() as scraper:
                    return scraper.scrape_listings(region_code=region_code, days_back=days_back)

            listings = await asyncio.to_thread(_run)
            new, updated = await self._upsert_listings(session, listings)

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new
            log_entry.items_updated = updated
            log_entry.status = "success"
            await session.flush()
            logger.info(f"[torgi.gov.ru] {new} new, {updated} updated")
        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)[:500]
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[torgi.gov.ru] Failed: {e}")

    async def _scrape_fedresurs(self, session: AsyncSession, days_back: int = 30):
        log_entry = ScrapeLog(source=SourceType.FEDRESURS, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            def _run():
                from scrapers.fedresurs import FedresursScraper
                with FedresursScraper() as scraper:
                    return scraper.scrape_listings(days_back=days_back)

            listings = await asyncio.to_thread(_run)
            new, updated = await self._upsert_listings(session, listings)

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new
            log_entry.items_updated = updated
            log_entry.status = "success"
            await session.flush()
            logger.info(f"[Fedresurs] {new} new, {updated} updated")
        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)[:500]
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[Fedresurs] Failed: {e}")

    async def _scrape_etp(self, session: AsyncSession, days_back: int = 30):
        log_entry = ScrapeLog(source=SourceType.ETP, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            total_new = 0
            total_update = 0
            for platform in ["lot-online", "fabrikant"]:
                try:
                    def _run(platform=platform):
                        from scrapers.etp import EtpScraper
                        with EtpScraper(platform=platform) as scraper:
                            return scraper.scrape_listings(days_back=days_back)

                    listings = await asyncio.to_thread(_run)
                    new, updated = await self._upsert_listings(session, listings)
                    total_new += new
                    total_update += updated
                except Exception as e:
                    logger.warning(f"[ETP:{platform}] Failed: {e}")

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_new = total_new
            log_entry.items_updated = total_update
            log_entry.status = "success"
            await session.flush()
        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)[:500]
            log_entry.finished_at = datetime.utcnow()
            await session.flush()

    async def _upsert_listings(self, session: AsyncSession, listings: list[dict]) -> tuple[int, int]:
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
                # Recalculate price_per_sqm on update
                if existing_prop.start_price and existing_prop.total_area and existing_prop.total_area > 0:
                    existing_prop.price_per_sqm = existing_prop.start_price / existing_prop.total_area
                existing_prop.updated_at = datetime.utcnow()
                update_count += 1
            else:
                # Calculate price_per_sqm on insert
                if listing_data.get("start_price") and listing_data.get("total_area") and listing_data["total_area"] > 0:
                    listing_data.setdefault("price_per_sqm", listing_data["start_price"] / listing_data["total_area"])
                new_prop = AuctionProperty(**listing_data)
                session.add(new_prop)
                new_count += 1

        await session.flush()
        return new_count, update_count

    async def _geocode_properties(self, session: AsyncSession, batch_size: int = 200):
        result = await session.execute(
            select(AuctionProperty)
            .where(AuctionProperty.is_geocoded == False, AuctionProperty.address.isnot(None), AuctionProperty.address != "")
            .limit(batch_size)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need geocoding")
            return

        from services.geocoder import geocoder
        geocoded = 0
        for prop in properties:
            try:
                coords = geocoder.geocode(prop.address, prop.city)
                if coords:
                    prop.latitude = coords[0]
                    prop.longitude = coords[1]
                    geocoded += 1
                prop.is_geocoded = True
            except Exception as e:
                logger.warning(f"Geocode error: {e}")
            await asyncio.sleep(0.5)

        await session.flush()
        logger.info(f"Geocoded {geocoded}/{len(properties)}")

    async def _estimate_market_prices(self, session: AsyncSession, batch_size: int = 50):
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_market_appraised == False,
                AuctionProperty.total_area.isnot(None),
                AuctionProperty.start_price.isnot(None),
            )
            .limit(batch_size)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need market appraisal")
            return

        def _run_cian(properties_list):
            results = []
            from scrapers.cian import CianScraper
            with CianScraper() as cian:
                for prop in properties_list:
                    estimation = cian.estimate_market_price({
                        "city": prop.city or "Москва",
                        "property_type": prop.property_type,
                        "rooms": prop.rooms,
                        "total_area": prop.total_area,
                    })
                    results.append((prop, estimation))
            return results

        results = await asyncio.to_thread(_run_cian, properties)

        estimated = 0
        for prop, estimation in results:
            if estimation:
                est_per_sqm = estimation.get("price_per_sqm")
                if est_per_sqm and prop.total_area:
                    prop.market_price = est_per_sqm * prop.total_area
                if prop.start_price and prop.market_price and prop.market_price > 0:
                    prop.discount_pct = round((1 - prop.start_price / prop.market_price) * 100, 1)
                estimated += 1
            prop.is_market_appraised = True

        await session.flush()
        logger.info(f"Market appraisal: {estimated}/{len(properties)}")


enrichment_service = EnrichmentService()
