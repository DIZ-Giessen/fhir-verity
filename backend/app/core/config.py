from pydantic_settings import BaseSettings 
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    ENVIRONMENT: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra ="ignore"

@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()