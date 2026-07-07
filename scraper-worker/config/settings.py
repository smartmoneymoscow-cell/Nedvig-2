"""Scraper Worker configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — individual components (for local dev)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "estate_auction"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    # Database — full URL (Render provides this)
    DATABASE_URL: str = ""

    @property
    def effective_db_url(self) -> str:
        """Return async DB URL. Prefers DATABASE_URL if set."""
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
        """Return sync DB URL."""
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

    # Scraping
    SCRAPE_INTERVAL_HOURS: int = 6
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0

    # Proxy
    PROXY_LIST: str = ""
    USE_TOR: bool = False

    # Geocoding
    YANDEX_MAPS_API_KEY: str = ""

    # Dev
    USE_SQLITE: bool = False
    SQLITE_PATH: str = "estate_auction.db"
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
