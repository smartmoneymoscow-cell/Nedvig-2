"""FastAPI API Service — Nedvig-2."""

import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routes.properties import router as properties_router
from routes.auth import router as auth_router
from middleware.rate_limiter import rate_limit_middleware, security_headers_middleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nedvig-api")

# ─── Startup time ────────────────────────────────────────────
_startup_time = time.time()

# ─── Admin API key auth ─────────────────────────────────────
_admin_api_key = settings.ADMIN_API_KEY


def verify_admin_key(request: Request) -> bool:
    """Verify admin API key for sensitive endpoints."""
    if not _admin_api_key:
        return True  # dev mode
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


# ─── Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Nedvig API starting...")
    log.info("  Version:    2.0.0")
    log.info("  Debug:      %s", settings.DEBUG)
    log.info("  CORS:       %s", settings.CORS_ORIGINS)
    log.info("  Worker URL: %s", settings.SCRAPER_WORKER_URL or "(not configured)")
    log.info("  Admin Key:  %s", "configured" if settings.ADMIN_API_KEY else "OPEN (dev mode)")
    log.info("=" * 60)

    await init_db()
    log.info("✅ Database initialized")

    yield

    log.info("Nedvig API shutting down")


# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Nedvig API",
    description="Агрегатор торгов по недвижимости с рыночной оценкой и отображением на карте",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Custom middleware
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# Routes
app.include_router(properties_router)
app.include_router(auth_router)


# ─── Global exception handler ────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ─── Root / Health ───────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": "Nedvig API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check with dependency status."""
    checks: dict = {
        "status": "ok",
        "version": "2.0.0",
        "uptime_seconds": int(time.time() - _startup_time),
    }
    # DB check
    try:
        from sqlalchemy import text
        from database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    return checks


# ─── Scrape trigger (proxies to scraper-worker) ─────────────
@app.post("/api/scrape/trigger")
async def trigger_scrape(request: Request, _auth: bool = Depends(verify_admin_key)):
    """Trigger scraper worker via HTTP webhook."""
    if not settings.SCRAPER_WORKER_URL:
        return JSONResponse(
            status_code=503,
            content={"status": "no_worker", "message": "Scraper worker URL not configured"},
        )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{settings.SCRAPER_WORKER_URL}/internal/scrape")
            return resp.json()
    except Exception as e:
        log.error("Failed to trigger scraper: %s", e)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Cannot reach scraper worker: {e}"},
        )


# ─── Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
