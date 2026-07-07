"""Scraper Worker — standalone service for periodic data collection.

Runs scrapers on a schedule and stores results in PostgreSQL.
Can also be triggered via HTTP webhook from the API service.
"""

import asyncio
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from config import settings
from database import init_db, async_session_factory
from services.enrichment import enrichment_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scraper Worker starting...")
    await init_db()
    logger.info("✅ Database initialized")

    # Start periodic scraping
    if settings.SCRAPE_INTERVAL_HOURS > 0:
        task = asyncio.create_task(_periodic_scrape())
        logger.info(f"Periodic scraping every {settings.SCRAPE_INTERVAL_HOURS}h")

    yield

    logger.info("Scraper Worker shutting down")


app = FastAPI(title="Nedvig Scraper Worker", lifespan=lifespan)


async def _periodic_scrape():
    while True:
        try:
            logger.info("⏰ Starting scheduled scrape...")
            await _run_pipeline()
        except Exception as e:
            logger.error(f"Scheduled scrape failed: {e}")
        await asyncio.sleep(settings.SCRAPE_INTERVAL_HOURS * 3600)


async def _run_pipeline():
    start = time.time()
    async with async_session_factory() as session:
        try:
            await enrichment_service.run_full_pipeline(session)
            await session.commit()
            elapsed = time.time() - start
            logger.info(f"✅ Pipeline completed in {elapsed:.1f}s")
        except Exception as e:
            await session.rollback()
            logger.error(f"Pipeline failed: {e}")
            raise


@app.post("/internal/scrape")
async def trigger_scrape():
    """Manual trigger from API service."""
    asyncio.create_task(_run_pipeline())
    return {"status": "started", "message": "Scrape task started"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "scraper-worker"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker:app", host="0.0.0.0", port=8001)
