"""Database setup"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async Session Local
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Dependency für FastAPI
async def get_db() -> AsyncSession:
    """Yield a session per request and close it afterwards."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            try:
                await session.close()
            except Exception:
                pass
