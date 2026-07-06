from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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
        return self.DATABASE_URL

    @property
    def effective_db_url_sync(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite:///{self.SQLITE_PATH}"
        return self.DATABASE_URL_SYNC

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
