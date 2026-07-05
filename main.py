"""Main FastAPI application."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from config import settings
from database import init_db, async_session_factory
from api.routes import router as api_router
from services.enrichment import enrichment_service


scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    """Periodic scraping task."""
    logger.info("Starting scheduled scrape...")
    try:
        async with async_session_factory() as session:
            await enrichment_service.run_full_pipeline(session)
            await session.commit()
        logger.info("Scheduled scrape completed")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    logger.info("Initializing database...")
    await init_db()

    # Start scheduler
    if settings.SCRAPE_INTERVAL_HOURS > 0:
        scheduler.add_job(
            scheduled_scrape,
            "interval",
            hours=settings.SCRAPE_INTERVAL_HOURS,
            id="main_scrape",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Scheduler started: scraping every {settings.SCRAPE_INTERVAL_HOURS}h")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Application shutdown")


app = FastAPI(
    title="Estate Auction Tracker",
    description="Агрегатор торгов по недвижимости с рыночной оценкой",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main map page."""
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "yandex_maps_key": settings.YANDEX_MAPS_API_KEY or "",
        },
    )


@app.post("/api/scrape/trigger")
async def trigger_scrape():
    """Manually trigger a scrape run."""
    asyncio.create_task(scheduled_scrape())
    return {"status": "started", "message": "Scrape task started in background"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
