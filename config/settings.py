"""Unified configuration for both API and Scraper Worker (root level / tests)."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

log = logging.getLogger("nedvig-config")


class Settings(BaseSettings):
    # ─── Database (individual components, for local dev) ────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "estate_auction"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    # ─── Database (full URL, Render provides this) ─────────
    DATABASE_URL: str = ""

    @property
    def effective_db_url(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        if self.DATABASE_URL:
            return self._ensure_async_prefix(self.DATABASE_URL)
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def effective_db_url_sync(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite:///{self.SQLITE_PATH}"
        if self.DATABASE_URL:
            return self._ensure_sync_prefix(self.DATABASE_URL)
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @staticmethod
    def _ensure_async_prefix(url: str) -> str:
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @staticmethod
    def _ensure_sync_prefix(url: str) -> str:
        if url.startswith("postgresql+psycopg2://"):
            return url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)
        return url

    # ─── Security ──────────────────────────────────────────
    ADMIN_API_KEY: str = ""
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # ─── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "*"

    # ─── Scraper Worker ────────────────────────────────────
    SCRAPER_WORKER_URL: str = ""

    # ─── Scraping ──────────────────────────────────────────
    SCRAPE_INTERVAL_HOURS: int = 6
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0
    CIAN_REQUEST_DELAY_MIN: float = 3.0
    CIAN_REQUEST_DELAY_MAX: float = 8.0

    # ─── Proxy ─────────────────────────────────────────────
    PROXY_LIST: str = ""
    PROXY_ROTATION_INTERVAL: int = 300
    USE_TOR: bool = False

    # ─── Geocoding ─────────────────────────────────────────
    YANDEX_MAPS_API_KEY: str = ""

    # ─── App ───────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # ─── Dev mode ──────────────────────────────────────────
    USE_SQLITE: bool = False
    SQLITE_PATH: str = "estate_auction.db"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    def validate_production(self) -> None:
        """Warn about insecure settings in production."""
        if not self.DEBUG:
            if not self.ADMIN_API_KEY:
                self.ADMIN_API_KEY = secrets.token_urlsafe(32)
                log.warning(
                    "ADMIN_API_KEY not set — auto-generated: %s... (save this!)",
                    self.ADMIN_API_KEY[:8],
                )
            if not self.JWT_SECRET or self.JWT_SECRET == "change-me-in-production":
                self.JWT_SECRET = secrets.token_urlsafe(32)
                log.warning(
                    "JWT_SECRET not set — auto-generated (sessions will invalidate on restart)"
                )
            if self.CORS_ORIGINS == "*":
                log.warning("CORS_ORIGINS='*' — this is insecure in production!")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.validate_production()
