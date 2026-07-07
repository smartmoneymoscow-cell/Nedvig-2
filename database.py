"""Database connection and session management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config import settings
from models import Base


def _get_engine_kwargs(is_sqlite: bool = False) -> dict:
    if is_sqlite:
        return {"echo": False}
    return {
        "echo": settings.DEBUG,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    }


is_sqlite = settings.USE_SQLITE
db_url = settings.effective_db_url

async_engine = create_async_engine(db_url, **_get_engine_kwargs(is_sqlite))

if is_sqlite:
    @event.listens_for(async_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(settings.effective_db_url_sync, echo=False)
SyncSession = sessionmaker(bind=sync_engine)


async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
