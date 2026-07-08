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

    # Security
    ADMIN_API_KEY: str = ""
    JWT_SECRET: str = ""  # REQUIRED in production — empty = startup warning
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "*"

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # Dev mode
    USE_SQLITE: bool = False
    SQLITE_PATH: str = "estate_auction.db"

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

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
