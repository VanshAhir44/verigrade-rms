from functools import lru_cache
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    """Normalizes postgres:// or postgresql:// URLs and sslmode params for SQLAlchemy asyncpg."""
    cleaned = url.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql+asyncpg://" + cleaned[len("postgres://") :]
    elif cleaned.startswith("postgresql://"):
        cleaned = "postgresql+asyncpg://" + cleaned[len("postgresql://") :]

    if cleaned.startswith("postgresql+asyncpg://"):
        parts = urlsplit(cleaned)
        query_items = dict(parse_qsl(parts.query, keep_blank_values=True))
        if "sslmode" in query_items:
            sslmode = query_items.pop("sslmode")
            if sslmode and sslmode != "disable" and "ssl" not in query_items:
                query_items["ssl"] = "require"
        query_items.pop("channel_binding", None)
        cleaned = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment)
        )
    return cleaned


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Verified Student Result Management System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = ""

    DATABASE_URL: str = ""

    JWT_SIGNING_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    BLOCKCHAIN_RPC_URL: str = ""
    BLOCKCHAIN_CHAIN_ID: int = 31337
    RESULT_REGISTRY_CONTRACT_ADDRESS: str = ""

    PUBLIC_VERIFY_BASE_URL: str = ""

    @property
    def async_database_url(self) -> str:
        return normalize_async_database_url(self.DATABASE_URL)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
