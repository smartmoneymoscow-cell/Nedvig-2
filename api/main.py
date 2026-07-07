"""FastAPI API Service."""

import logging
import secrets
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

# Admin API key auth
_admin_api_key = settings.ADMIN_API_KEY


def verify_admin_key(request: Request):
    if not _admin_api_key:
        if not settings.DEBUG:
            raise HTTPException(status_code=500, detail="ADMIN_API_KEY not configured")
        return True  # Dev mode only
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        raise HTTPException(status_code=401, detail="API key required (use Authorization: Bearer <key>)")
    if not secrets.compare_digest(token, _admin_api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security checks
    if not settings.DEBUG:
        if not settings.JWT_SECRET:
            log.error("❌ JWT_SECRET not set in production mode!")
        if not settings.ADMIN_API_KEY:
            log.error("❌ ADMIN_API_KEY not set in production mode!")
        if "*" in settings.CORS_ORIGINS:
            log.warning("⚠️  CORS_ORIGINS=* in production — restrict to your domain")

    log.info("Initializing database...")
    await init_db()
    log.info("✅ Database initialized")
    yield


app = FastAPI(
    title="Nedvig API",
    description="Агрегатор торгов по недвижимости",
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

# Middleware
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# Routes
app.include_router(properties_router)
app.include_router(auth_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/")
async def root():
    return {
        "name": "Nedvig API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    from sqlalchemy import text
    checks = {"status": "ok", "version": "2.0.0"}
    try:
        from database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"
    return checks


@app.post("/api/scrape/trigger")
async def trigger_scrape(request: Request, _auth: bool = Depends(verify_admin_key)):
    """Trigger scraper worker via HTTP."""
    import httpx
    worker_url = settings.SCRAPER_WORKER_URL if hasattr(settings, "SCRAPER_WORKER_URL") else None
    if not worker_url:
        return {"status": "no_worker", "message": "Scraper worker URL not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{worker_url}/internal/scrape")
            return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
