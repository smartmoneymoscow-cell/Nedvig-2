from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — Render injects DATABASE_URL; fallback to individual vars for local dev
    DATABASE_URL: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "estate_auction"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    @property
    def _resolved_db_url(self) -> str:
        """Return raw postgresql:// URL: prefer DATABASE_URL env var, else build from parts."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        url = self._resolved_db_url
        if "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def DATABASE_URL_SYNC(self) -> str:
        url = self._resolved_db_url
        if "+psycopg2" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
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

    @property
    def effective_db_url(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return self.DATABASE_URL_ASYNC

    @property
    def effective_db_url_sync(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite:///{self.SQLITE_PATH}"
        return self.DATABASE_URL_SYNC

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
