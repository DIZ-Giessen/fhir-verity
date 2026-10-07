"""Database setup"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    # Proactively drop connections that have sat idle in the pool too long,
    # rather than relying solely on pool_pre_ping: if a firewall/NAT/VPN
    # silently blackholes an idle connection (no RST/FIN), the pre_ping's
    # "SELECT 1" hangs until the OS TCP timeout instead of failing fast -
    # this is what causes the very slow first request after an overnight
    # idle period. Recycling well before that can happen avoids hitting
    # a dead socket in the first place.
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    # If a connection/query does hang despite the above, fail fast (seconds,
    # not minutes) so SQLAlchemy can discard it and retry on a fresh one.
    connect_args={"timeout": 10, "command_timeout": 10},
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
