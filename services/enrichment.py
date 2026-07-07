"""Enrichment service — orchestrates scraping, geocoding, and market appraisal.

Improvements over original:
- Generic _run_scraper_pipeline() eliminates duplicate UPSERT logic
- Larger batch sizes for geocoding (500) and market appraisal (100)
- Differential retry for geocoding (permanent vs temporary failures)
- ScrapeLog cleanup (TTL 90 days)
- price_per_sqm recalculated on update
- Better error isolation between scrapers
"""

import asyncio
import time
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuctionProperty, ScrapeLog, SourceType


class EnrichmentService:
    """Orchestrates the full data enrichment pipeline."""

    async def run_full_pipeline(
        self,
        session: AsyncSession,
        region_code: str = None,
        days_back: int = 30,
    ):
        """Run the complete enrichment pipeline."""
        start_time = time.time()

        # ── Step 1: Scrape torgi.gov.ru ──────────────────────
        logger.info("=" * 60)
        logger.info("STEP 1/6: Scraping torgi.gov.ru")
        logger.info("=" * 60)
        await self._run_scraper_pipeline(
            session,
            source_type=SourceType.TORGIGOV,
            scraper_factory=lambda: self._create_torgi_scraper(),
            scrape_kwargs={"region_code": region_code, "days_back": days_back},
        )

        # ── Step 2: Scrape Fedresurs ─────────────────────────
        logger.info("=" * 60)
        logger.info("STEP 2/6: Scraping Fedresurs (bankruptcy)")
        logger.info("=" * 60)
        await self._run_scraper_pipeline(
            session,
            source_type=SourceType.FEDRESURS,
            scraper_factory=lambda: self._create_fedresurs_scraper(),
            scrape_kwargs={"days_back": days_back},
        )

        # ── Step 3: Scrape ETP ───────────────────────────────
        logger.info("=" * 60)
        logger.info("STEP 3/6: Scraping ETP platforms")
        logger.info("=" * 60)
        for platform in ["lot-online", "fabrikant"]:
            await self._run_scraper_pipeline(
                session,
                source_type=SourceType.ETP,
                scraper_factory=lambda p=platform: self._create_etp_scraper(p),
                scrape_kwargs={"days_back": days_back},
                source_label=f"ETP:{platform}",
            )

        # ── Step 4: Geocode addresses ────────────────────────
        logger.info("=" * 60)
        logger.info("STEP 4/6: Geocoding addresses")
        logger.info("=" * 60)
        await self._geocode_properties(session, batch_size=500)

        # ── Step 5: Market price estimation ───────────────────
        logger.info("=" * 60)
        logger.info("STEP 5/6: Market price estimation (CIAN)")
        logger.info("=" * 60)
        await self._estimate_market_prices(session, batch_size=100)

        # ── Step 6: Cleanup old logs ──────────────────────────
        logger.info("=" * 60)
        logger.info("STEP 6/6: Cleanup old ScrapeLogs")
        logger.info("=" * 60)
        await self._cleanup_old_logs(session, ttl_days=90)

        elapsed = time.time() - start_time
        logger.info(f"✅ Full pipeline completed in {elapsed:.1f}s")

    # ─── Generic scraper pipeline ─────────────────────────────

    async def _run_scraper_pipeline(
        self,
        session: AsyncSession,
        source_type: SourceType,
        scraper_factory,
        scrape_kwargs: dict = None,
        source_label: str = None,
    ) -> tuple[int, int]:
        """Generic pipeline: scrape → upsert → log. Works for any scraper."""
        label = source_label or source_type.value
        log_entry = ScrapeLog(source=source_type, status="running")
        session.add(log_entry)
        await session.flush()

        try:
            def _run():
                scraper = scraper_factory()
                with scraper:
                    return scraper.scrape_listings(**(scrape_kwargs or {}))

            listings = await asyncio.to_thread(_run)
            new, updated = await self._upsert_listings(session, listings)

            log_entry.finished_at = datetime.utcnow()
            log_entry.items_found = len(listings)
            log_entry.items_new = new
            log_entry.items_updated = updated
            log_entry.status = "success"
            await session.flush()
            logger.info(f"[{label}] ✅ {new} new, {updated} updated, {len(listings)} total")
            return new, updated

        except Exception as e:
            log_entry.status = "error"
            log_entry.errors = str(e)[:500]
            log_entry.finished_at = datetime.utcnow()
            await session.flush()
            logger.error(f"[{label}] ❌ Failed: {e}")
            return 0, 0

    # ─── Scraper factories ────────────────────────────────────

    @staticmethod
    def _create_torgi_scraper():
        from scrapers.torgi_gov import TorgiGovScraper
        return TorgiGovScraper()

    @staticmethod
    def _create_fedresurs_scraper():
        from scrapers.fedresurs import FedresursScraper
        return FedresursScraper()

    @staticmethod
    def _create_etp_scraper(platform: str):
        from scrapers.etp import EtpScraper
        return EtpScraper(platform=platform)

    # ─── UPSERT logic ────────────────────────────────────────

    async def _upsert_listings(
        self,
        session: AsyncSession,
        listings: list[dict],
    ) -> tuple[int, int]:
        """Insert new listings or update existing ones."""
        new_count = 0
        update_count = 0

        for listing_data in listings:
            source = listing_data.get("source")
            source_id = listing_data.get("source_id")
            if not source or not source_id:
                continue

            existing = await session.execute(
                select(AuctionProperty).where(
                    AuctionProperty.source == source,
                    AuctionProperty.source_id == source_id,
                )
            )
            existing_prop = existing.scalar_one_or_none()

            if existing_prop:
                # Update existing
                for key, value in listing_data.items():
                    if key not in ("source", "source_id", "raw_data") and value is not None:
                        setattr(existing_prop, key, value)
                # Recalculate price_per_sqm on update
                if (existing_prop.start_price and
                    existing_prop.total_area and
                    existing_prop.total_area > 0):
                    existing_prop.price_per_sqm = (
                        existing_prop.start_price / existing_prop.total_area
                    )
                existing_prop.updated_at = datetime.utcnow()
                update_count += 1
            else:
                # Insert new
                if (listing_data.get("start_price") and
                    listing_data.get("total_area") and
                    listing_data["total_area"] > 0):
                    listing_data.setdefault(
                        "price_per_sqm",
                        listing_data["start_price"] / listing_data["total_area"],
                    )
                new_prop = AuctionProperty(**listing_data)
                session.add(new_prop)
                new_count += 1

        await session.flush()
        return new_count, update_count

    # ─── Geocoding ────────────────────────────────────────────

    async def _geocode_properties(
        self,
        session: AsyncSession,
        batch_size: int = 500,
    ):
        """Geocode properties that haven't been geocoded yet."""
        result = await session.execute(
            select(AuctionProperty)
            .where(
                AuctionProperty.is_geocoded == False,
                AuctionProperty.address.isnot(None),
                AuctionProperty.address != "",
            )
            .limit(batch_size)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No properties need geocoding")
            return

        from services.geocoder import geocoder
        geocoded = 0
        permanent_failures = 0

        for prop in properties:
            try:
                coords = geocoder.geocode(prop.address, prop.city)
                if coords:
                    prop.latitude = coords[0]
                    prop.longitude = coords[1]
                    geocoded += 1
                    prop.is_geocoded = True
                else:
                    # No result — mark as geocoded to avoid retrying
                    # (address might be invalid or not found)
                    prop.is_geocoded = True
                    permanent_failures += 1
            except Exception as e:
                # Temporary failure (network, rate limit) — don't mark,
                # will retry next run
                logger.debug(f"Geocode temp error: {e}")

            await asyncio.sleep(0.5)  # Rate limit

        await session.flush()
        logger.info(
            f"Geocoded {geocoded}/{len(properties)} "
            f"({permanent_failures} permanent failures)"
        )

    # ─── Market price estimation ──────────────────────────────

    async def _estimate_market_prices(
        self,
        session: AsyncSession,
        batch_size: int = 100,
    ):
        """Estimate market prices using CIAN."""
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
                    prop.discount_pct = round(
                        (1 - prop.start_price / prop.market_price) * 100, 1
                    )
                estimated += 1
            # Mark as appraised regardless (avoid re-processing failed items)
            prop.is_market_appraised = True

        await session.flush()
        logger.info(f"Market appraisal: {estimated}/{len(properties)}")

    # ─── Cleanup ──────────────────────────────────────────────

    async def _cleanup_old_logs(
        self,
        session: AsyncSession,
        ttl_days: int = 90,
    ):
        """Delete ScrapeLog entries older than ttl_days."""
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        result = await session.execute(
            delete(ScrapeLog).where(ScrapeLog.started_at < cutoff)
        )
        deleted = result.rowcount
        if deleted:
            await session.flush()
            logger.info(f"Cleaned up {deleted} old ScrapeLog entries (>{ttl_days}d)")
        else:
            logger.debug("No old ScrapeLog entries to clean up")


enrichment_service = EnrichmentService()
