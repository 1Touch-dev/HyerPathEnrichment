from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
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
    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: SecretStr = Field(default=SecretStr(""), alias="R2_SECRET_ACCESS_KEY")
    linkedin_photo_ttl_seconds: int = Field(default=86400, alias="LINKEDIN_PHOTO_TTL_SECONDS")
    username_lookup_ttl_seconds: int = Field(default=3600, alias="USERNAME_LOOKUP_TTL_SECONDS")
    business_lookup_ttl_seconds: int = Field(default=3600, alias="BUSINESS_LOOKUP_TTL_SECONDS")
    job_lookup_ttl_seconds: int = Field(default=1800, alias="JOB_LOOKUP_TTL_SECONDS")
    max_sync_requests_per_minute: int = Field(default=10, alias="MAX_SYNC_REQUESTS_PER_MINUTE")
    max_async_requests_per_minute: int = Field(default=30, alias="MAX_ASYNC_REQUESTS_PER_MINUTE")
    max_compliance_requests_per_minute: int = Field(
        default=20, alias="MAX_COMPLIANCE_REQUESTS_PER_MINUTE"
    )

    # Provider mode switches (Phase 0): the only flags that flip free -> paid.
    # Defaults = fully free / self-hosted. See app/providers/.
    proxy_mode: str = Field(default="none", alias="PROXY_MODE")  # none|scrapoxy|paid
    browser_mode: str = Field(default="local", alias="BROWSER_MODE")  # local|multilogin
    llm_mode: str = Field(default="stub", alias="LLM_MODE")  # stub|ollama|litellm
    email_verify_level: str = Field(default="basic", alias="EMAIL_VERIFY_LEVEL")  # basic|smtp
    enable_tier1: bool = Field(default=False, alias="ENABLE_TIER1")

    # Worker queue routing
    worker_queue_mode: Literal["single", "per_tier"] = Field(
        default="single",
        alias="WORKER_QUEUE_MODE",
        description="Queue routing: 'single' (default) or 'per_tier' (tier1 + tier234 queues)",
    )
    worker_target_queue: str | None = Field(
        default=None,
        alias="WORKER_TARGET_QUEUE",
        description="For per_tier mode: which queue this worker listens to (tier1 or tier234)",
    )

    # Parallel tier execution settings
    enricher_max_retries: int = Field(default=3, alias="ENRICHER_MAX_RETRIES")
    enricher_retry_backoff: float = Field(default=2.0, alias="ENRICHER_RETRY_BACKOFF")
    max_parallel_tiers: int = Field(default=4, alias="MAX_PARALLEL_TIERS")
    tier1_max_concurrent: int = Field(default=1, alias="TIER1_MAX_CONCURRENT")
    tier2_max_concurrent: int = Field(default=3, alias="TIER2_MAX_CONCURRENT")
    tier3_max_concurrent: int = Field(default=4, alias="TIER3_MAX_CONCURRENT")
    tier4_max_concurrent: int = Field(default=2, alias="TIER4_MAX_CONCURRENT")

    # Tier 1 — LinkedIn photo (Multilogin + Selenium)
    multilogin_api_url: str = Field(
        default="https://api.multilogin.com", alias="MULTILOGIN_API_URL"
    )
    multilogin_launcher_url: str = Field(
        default="https://launcher.mlx.yt:45001/api/v2", alias="MULTILOGIN_LAUNCHER_URL"
    )
    multilogin_email: str = Field(default="", alias="MULTILOGIN_EMAIL")
    multilogin_password: SecretStr = Field(default=SecretStr(""), alias="MULTILOGIN_PASSWORD")
    multilogin_folder_id: str = Field(default="", alias="MULTILOGIN_FOLDER_ID")
    multilogin_workspace_id: str = Field(default="", alias="MULTILOGIN_WORKSPACE_ID")
    multilogin_profile_id: str = Field(default="", alias="MULTILOGIN_PROFILE_ID")
    multilogin_profile_pool_size: int = Field(default=0, alias="MULTILOGIN_PROFILE_POOL_SIZE")
    multilogin_daily_view_limit: int = Field(default=22, alias="MULTILOGIN_DAILY_VIEW_LIMIT")
    multilogin_profile_cooldown_seconds: int = Field(
        default=86_400, alias="MULTILOGIN_PROFILE_COOLDOWN_SECONDS"
    )
    multilogin_rate_limit_cooldown_seconds: int = Field(
        default=3_600, alias="MULTILOGIN_RATE_LIMIT_COOLDOWN_SECONDS"
    )
    tier1_placeholder_denylist: str = Field(default="", alias="TIER1_PLACEHOLDER_DENYLIST")
    tier1_skip_login_if_session_valid: bool = Field(
        default=True, alias="TIER1_SKIP_LOGIN_IF_SESSION_VALID"
    )
    multilogin_selenium_host: str = Field(
        default="http://127.0.0.1", alias="MULTILOGIN_SELENIUM_HOST"
    )
    linkedin_bot_email: str = Field(default="", alias="LINKEDIN_BOT_EMAIL")
    linkedin_bot_password: SecretStr = Field(default=SecretStr(""), alias="LINKEDIN_BOT_PASSWORD")
    tier1_browser_timeout_seconds: int = Field(default=45, alias="TIER1_BROWSER_TIMEOUT_SECONDS")
    tier1_max_concurrent_browsers: int = Field(default=1, alias="TIER1_MAX_CONCURRENT_BROWSERS")
    # Legacy Playwright CDP attach (local dev); production uses Selenium via MLX launcher port.
    multilogin_cdp_url: str = Field(default="", alias="MULTILOGIN_CDP_URL")

    # Tier 2 — handle hunt. Sidecar URLs default empty -> empty fragment.
    social_analyzer_url: str = Field(default="", alias="SOCIAL_ANALYZER_URL")
    sherlock_timeout_seconds: int = Field(default=60, alias="SHERLOCK_TIMEOUT_SECONDS")
    maigret_timeout_seconds: int = Field(default=180, alias="MAIGRET_TIMEOUT_SECONDS")

    # Tier 3 — OSINT + email
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    gitrecon_script: str = Field(default="", alias="GITRECON_SCRIPT")
    # GitHub API throttle around gitrecon CLI (prefer GITHUB_TOKEN for higher limits).
    gitrecon_max_per_minute: int = Field(default=10, alias="GITRECON_MAX_PER_MINUTE")
    gitrecon_rate_limit_backoff_seconds: float = Field(
        default=5.0, alias="GITRECON_RATE_LIMIT_BACKOFF_SECONDS"
    )
    gitrecon_cooldown_seconds: int = Field(default=60, alias="GITRECON_COOLDOWN_SECONDS")
    theharvester_timeout_seconds: int = Field(default=120, alias="THEHARVESTER_TIMEOUT_SECONDS")
    crosslinked_timeout_seconds: int = Field(default=120, alias="CROSSLINKED_TIMEOUT_SECONDS")
    crosslinked_search_engines: str = Field(default="yahoo", alias="CROSSLINKED_SEARCH_ENGINES")
    email_sleuth_bin: str = Field(default="email-sleuth", alias="EMAIL_SLEUTH_BIN")
    email_verifier_url: str = Field(default="", alias="EMAIL_VERIFIER_URL")
    reacher_url: str = Field(default="", alias="REACHER_URL")
    reacher_from_email: str = Field(default="", alias="REACHER_FROM_EMAIL")
    email_verify_max_per_job: int = Field(default=10, alias="EMAIL_VERIFY_MAX_PER_JOB")
    email_verify_smtp_delay_seconds: int = Field(default=6, alias="EMAIL_VERIFY_SMTP_DELAY_SECONDS")

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

    # OpenAI API (for CV extraction, embeddings, etc.)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

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
    notify_webhook_url: str = Field(default="", alias="NOTIFY_WEBHOOK_URL")

    # Structured logging (stdlib; see app/core/logging.py + ADR 0007)
    # LOG_FORMAT empty = auto (json when APP_ENV is staging|production, else text)
    log_format: str = Field(default="", alias="LOG_FORMAT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_service: str = Field(default="hyrepath-enrichment", alias="LOG_SERVICE")

    # Central error tracking (Sentry-compatible; GlitchTip or Sentry SaaS)
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="", alias="SENTRY_ENVIRONMENT")
    sentry_release: str = Field(default="", alias="SENTRY_RELEASE")
    sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_send_default_pii: bool = Field(default=False, alias="SENTRY_SEND_DEFAULT_PII")
    enable_error_tracking_probe: bool = Field(default=False, alias="ENABLE_ERROR_TRACKING_PROBE")

    # Compliance
    audit_log_retention_years: int = Field(default=5, alias="AUDIT_LOG_RETENTION_YEARS")

    # Email Service (SendGrid)
    sendgrid_api_key: SecretStr = Field(default=SecretStr(""), alias="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(default="noreply@hyrepath.com", alias="SENDGRID_FROM_EMAIL")
    sendgrid_from_name: str = Field(default="Hyrepath Enrichment", alias="SENDGRID_FROM_NAME")
    sendgrid_reply_to: str = Field(default="support@hyrepath.com", alias="SENDGRID_REPLY_TO")
    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
    email_test_mode: bool = Field(default=True, alias="EMAIL_TEST_MODE")

    # Authentication
    SECRET_KEY: str = Field(
        default="change-me-in-production-use-openssl-rand-hex-32",
        alias="SECRET_KEY",
        description="Secret key for JWT signing (generate with: openssl rand -hex 32)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # OAuth (Google)
    GOOGLE_OAUTH_CLIENT_ID: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr = Field(
        default=SecretStr(""), alias="GOOGLE_OAUTH_CLIENT_SECRET"
    )
    GOOGLE_OAUTH_REDIRECT_URL: str = Field(
        default="http://localhost:3000/callback/google",
        alias="GOOGLE_OAUTH_REDIRECT_URL",
    )

    # Frontend URL (for email links)
    FRONTEND_URL: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Cookie settings
    COOKIE_SECURE: bool = Field(default=False, alias="COOKIE_SECURE")
    COOKIE_DOMAIN: str | None = Field(default=None, alias="COOKIE_DOMAIN")

    # RQ job timeout (seconds) — must accommodate full all-tier enrichment (20-30 min)
    rq_job_timeout_seconds: int = Field(default=3000, alias="RQ_JOB_TIMEOUT_SECONDS")


_TIER1_PROD_ENVS = frozenset({"production", "staging"})


def validate_tier1_settings(settings: Settings | None = None) -> None:
    """Fail fast when Tier 1 is enabled without required credentials.

    Raises RuntimeError listing missing env key *names* only (never secret values).
    No-op when ``enable_tier1`` is false. Staging/production also require R2.
    """
    cfg = settings if settings is not None else get_settings()
    if not cfg.enable_tier1:
        return

    missing: list[str] = []
    if cfg.browser_mode.strip().lower() == "multilogin":
        if not cfg.multilogin_email.strip():
            missing.append("MULTILOGIN_EMAIL")
        if not cfg.multilogin_password.get_secret_value().strip():
            missing.append("MULTILOGIN_PASSWORD")
        if not cfg.multilogin_folder_id.strip():
            missing.append("MULTILOGIN_FOLDER_ID")
        if not cfg.linkedin_bot_email.strip():
            missing.append("LINKEDIN_BOT_EMAIL")
        if not cfg.linkedin_bot_password.get_secret_value().strip():
            missing.append("LINKEDIN_BOT_PASSWORD")

    if cfg.app_env.strip().lower() in _TIER1_PROD_ENVS:
        if not (
            cfg.r2_account_id.strip()
            and cfg.r2_access_key_id.strip()
            and cfg.r2_secret_access_key.get_secret_value().strip()
            and cfg.r2_bucket.strip()
        ):
            missing.extend(
                [
                    "R2_ACCOUNT_ID",
                    "R2_ACCESS_KEY_ID",
                    "R2_SECRET_ACCESS_KEY",
                    "R2_BUCKET",
                ]
            )

    if missing:
        seen: set[str] = set()
        ordered: list[str] = []
        for key in missing:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        raise RuntimeError(
            "ENABLE_TIER1=true but required settings are missing: " + ", ".join(ordered)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
