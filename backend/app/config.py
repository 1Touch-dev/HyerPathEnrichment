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

    # Provider mode switches (Phase 0): the only flags that flip free -> paid.
    # Defaults = fully free / self-hosted. See app/providers/.
    proxy_mode: str = Field(default="none", alias="PROXY_MODE")  # none|scrapoxy|paid
    browser_mode: str = Field(default="local", alias="BROWSER_MODE")  # local|multilogin
    llm_mode: str = Field(default="stub", alias="LLM_MODE")  # stub|ollama|litellm
    email_verify_level: str = Field(default="basic", alias="EMAIL_VERIFY_LEVEL")  # basic|smtp
    enable_tier1: bool = Field(default=False, alias="ENABLE_TIER1")

    # Tier 1 — LinkedIn photo (paid-later)
    multilogin_cdp_url: str = Field(default="", alias="MULTILOGIN_CDP_URL")

    # Tier 2 — handle hunt. Sidecar URLs default empty -> empty fragment.
    social_analyzer_url: str = Field(default="", alias="SOCIAL_ANALYZER_URL")
    sherlock_timeout_seconds: int = Field(default=60, alias="SHERLOCK_TIMEOUT_SECONDS")
    maigret_timeout_seconds: int = Field(default=90, alias="MAIGRET_TIMEOUT_SECONDS")

    # Tier 3 — OSINT + email
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    gitrecon_script: str = Field(default="", alias="GITRECON_SCRIPT")
    theharvester_timeout_seconds: int = Field(default=120, alias="THEHARVESTER_TIMEOUT_SECONDS")
    crosslinked_timeout_seconds: int = Field(default=90, alias="CROSSLINKED_TIMEOUT_SECONDS")
    email_sleuth_bin: str = Field(default="email-sleuth", alias="EMAIL_SLEUTH_BIN")
    email_verifier_url: str = Field(default="", alias="EMAIL_VERIFIER_URL")
    reacher_url: str = Field(default="", alias="REACHER_URL")
    reacher_from_email: str = Field(default="", alias="REACHER_FROM_EMAIL")

    # Tier 4 — jobs + business
    jobspy_results_per_board: int = Field(default=15, alias="JOBSPY_RESULTS_PER_BOARD")
    gmaps_scraper_url: str = Field(default="", alias="GMAPS_SCRAPER_URL")
    gmaps_job_timeout_seconds: int = Field(default=300, alias="GMAPS_JOB_TIMEOUT_SECONDS")
    gmaps_job_poll_seconds: int = Field(default=10, alias="GMAPS_JOB_POLL_SECONDS")

    # LLM disambiguation
    disambiguation_threshold: float = Field(default=0.7, alias="DISAMBIGUATION_THRESHOLD")
    ollama_base_url: str = Field(default="", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")
    litellm_api_base: str = Field(default="", alias="LITELLM_API_BASE")
    litellm_api_key: str = Field(default="", alias="LITELLM_API_KEY")
    litellm_model: str = Field(default="gpt-4o-mini", alias="LITELLM_MODEL")
    litellm_fallbacks: str = Field(default="", alias="LITELLM_FALLBACKS")

    # Proxies (paid-later)
    scrapoxy_url: str = Field(default="", alias="SCRAPOXY_URL")
    scrapoxy_username: str = Field(default="", alias="SCRAPOXY_USERNAME")
    scrapoxy_password: str = Field(default="", alias="SCRAPOXY_PASSWORD")

    # Observability + signals (free self-host)
    langfuse_host: str = Field(default="", alias="LANGFUSE_HOST")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    changedetection_url: str = Field(default="", alias="CHANGEDETECTION_URL")
    changedetection_api_key: str = Field(default="", alias="CHANGEDETECTION_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
