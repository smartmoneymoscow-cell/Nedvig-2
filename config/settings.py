from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "estate_auction"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Yandex Maps
    YANDEX_MAPS_API_KEY: str = ""

    # Proxy (comma-separated list of proxy URLs)
    PROXY_LIST: str = ""
    PROXY_ROTATION_INTERVAL: int = 300  # seconds

    # Scraping
    SCRAPE_INTERVAL_HOURS: int = 6
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0
    CIAN_REQUEST_DELAY_MIN: float = 3.0
    CIAN_REQUEST_DELAY_MAX: float = 8.0

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Dev mode (SQLite fallback)
    USE_SQLITE: bool = False
    SQLITE_PATH: str = "estate_auction.db"

    @property
    def EFFECTIVE_DB_URL(self) -> str:
        """Return SQLite or PostgreSQL URL depending on config."""
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return self.DATABASE_URL

    @property
    def EFFECTIVE_DB_URL_SYNC(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite:///{self.SQLITE_PATH}"
        return self.DATABASE_URL_SYNC

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
