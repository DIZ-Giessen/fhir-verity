from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings


settings = get_settings() 

engine = create_async_engine(
    settings.DATABASE_URL,
    echo= settings.ENVIRONMENT == "development",                      
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

class Base(DeclarativeBase):
    """Abstract base for all models."""
    pass

# Dependency für FastAPI
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()