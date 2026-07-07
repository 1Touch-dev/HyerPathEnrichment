from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Hyrepath Enrichment Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_token: str = Field(default="change-me", alias="API_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///./hyrepath.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    r2_bucket: str = Field(default="hyrepath-assets", alias="R2_BUCKET")
    r2_public_base_url: str = Field(default="https://cdn.example.com", alias="R2_PUBLIC_BASE_URL")
    linkedin_photo_ttl_seconds: int = Field(default=86400, alias="LINKEDIN_PHOTO_TTL_SECONDS")
    username_lookup_ttl_seconds: int = Field(default=3600, alias="USERNAME_LOOKUP_TTL_SECONDS")
    business_lookup_ttl_seconds: int = Field(default=3600, alias="BUSINESS_LOOKUP_TTL_SECONDS")
    job_lookup_ttl_seconds: int = Field(default=1800, alias="JOB_LOOKUP_TTL_SECONDS")
    max_sync_requests_per_minute: int = Field(default=10, alias="MAX_SYNC_REQUESTS_PER_MINUTE")
    max_async_requests_per_minute: int = Field(default=30, alias="MAX_ASYNC_REQUESTS_PER_MINUTE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
