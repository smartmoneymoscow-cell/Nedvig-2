"""Main FastAPI application."""

import asyncio
import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from config import settings
from database import init_db, async_session_factory
from api.routes import router as api_router
from services.enrichment import enrichment_service


scheduler = AsyncIOScheduler()

# --- Simple API key auth for admin endpoints ---
# In production, use proper JWT auth. This is a lightweight MVP solution.
_admin_api_key = settings.ADMIN_API_KEY if hasattr(settings, 'ADMIN_API_KEY') else ""

def verify_admin_key(request: Request):
    """Verify admin API key for sensitive endpoints."""
    if not _admin_api_key:
        return True  # No key configured = open access (dev mode)

    # Check Authorization header or query param
    auth_header = request.headers.get("Authorization", "")
    api_key = request.query_params.get("api_key", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif api_key:
        token = api_key
    else:
        raise HTTPException(status_code=401, detail="API key required")

    if not secrets.compare_digest(token, _admin_api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# --- Rate limiting middleware ---
class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_second: float = 10.0):
        self.requests_per_second = requests_per_second
        self._requests: dict[str, list[float]] = {}
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()

        # Periodic cleanup
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        # Remove old requests
        window_start = now - 1.0
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]

        if len(self._requests[client_ip]) >= self.requests_per_second:
            return False

        self._requests[client_ip].append(now)
        return True

    def _cleanup(self, now: float):
        """Remove stale entries."""
        cutoff = now - 60
        self._requests = {
            ip: times for ip, times in self._requests.items()
            if times and times[-1] > cutoff
        }
        self._last_cleanup = now


rate_limiter = RateLimiter(requests_per_second=10.0)
rate_limiter_scrape = RateLimiter(requests_per_second=0.5)  # 1 per 2 seconds


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
    logger.info("Initializing database...")
    await init_db()

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

    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Application shutdown")


app = FastAPI(
    title="Estate Auction Tracker",
    description="Агрегатор торгов по недвижимости с рыночной оценкой",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Middleware ---

# CORS (restrictive by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if hasattr(settings, 'CORS_ORIGINS') else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    client_ip = request.client.host if request.client else "unknown"

    # Scrape trigger endpoint has stricter limits
    if request.url.path == "/api/scrape/trigger":
        if not rate_limiter_scrape.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded for scrape endpoint"},
                headers={"Retry-After": "2"},
            )
    else:
        if not rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "1"},
            )

    response = await call_next(request)
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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
async def trigger_scrape(
    request: Request,
    _auth: bool = Depends(verify_admin_key),
):
    """Manually trigger a scrape run. Requires admin API key in production."""
    asyncio.create_task(scheduled_scrape())
    return {"status": "started", "message": "Scrape task started in background"}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
