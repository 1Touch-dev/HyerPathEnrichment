from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Hyrepath Enrichment Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_token: str = Field(default="change-me", alias="API_TOKEN")
    metrics_token: str = Field(
        default="",
        alias="METRICS_TOKEN",
        description="Optional scrape token for /metrics; falls back to API_TOKEN when empty",
    )
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
    max_auth_requests_per_minute: int = Field(default=5, alias="MAX_AUTH_REQUESTS_PER_MINUTE")
    max_auth_refresh_requests_per_minute: int = Field(
        default=30, alias="MAX_AUTH_REFRESH_REQUESTS_PER_MINUTE"
    )
    max_documents_upload_requests_per_minute: int = Field(
        default=10, alias="MAX_DOCUMENTS_UPLOAD_REQUESTS_PER_MINUTE"
    )
    max_signals_webhook_requests_per_minute: int = Field(
        default=30, alias="MAX_SIGNALS_WEBHOOK_REQUESTS_PER_MINUTE"
    )
    max_job_matching_scan_requests_per_minute: int = Field(
        default=5, alias="MAX_JOB_MATCHING_SCAN_REQUESTS_PER_MINUTE"
    )

    # Admin module rate limits (Step 5: brute-force/abuse-sensitive admin endpoints).
    max_admin_impersonation_start_requests_per_minute: int = Field(
        default=5, alias="MAX_ADMIN_IMPERSONATION_START_REQUESTS_PER_MINUTE"
    )
    max_admin_mfa_verify_requests_per_minute: int = Field(
        default=5, alias="MAX_ADMIN_MFA_VERIFY_REQUESTS_PER_MINUTE"
    )
    max_admin_review_queue_decide_requests_per_minute: int = Field(
        default=30, alias="MAX_ADMIN_REVIEW_QUEUE_DECIDE_REQUESTS_PER_MINUTE"
    )
    max_admin_moderation_requests_per_minute: int = Field(
        default=30, alias="MAX_ADMIN_MODERATION_REQUESTS_PER_MINUTE"
    )

    # Module 3/4 rate limits (Step 5). Distinct per-minute caps from any existing
    # daily/quota-style caps enforced in the service layer.
    max_questions_requests_per_minute: int = Field(
        default=20, alias="MAX_QUESTIONS_REQUESTS_PER_MINUTE"
    )
    max_practice_audio_upload_requests_per_minute: int = Field(
        default=10, alias="MAX_PRACTICE_AUDIO_UPLOAD_REQUESTS_PER_MINUTE"
    )
    max_jd_practice_requests_per_minute: int = Field(
        default=20, alias="MAX_JD_PRACTICE_REQUESTS_PER_MINUTE"
    )
    max_application_tracker_status_update_requests_per_minute: int = Field(
        default=30, alias="MAX_APPLICATION_TRACKER_STATUS_UPDATE_REQUESTS_PER_MINUTE"
    )
    max_interview_scheduling_requests_per_minute: int = Field(
        default=20, alias="MAX_INTERVIEW_SCHEDULING_REQUESTS_PER_MINUTE"
    )
    max_manual_job_entry_create_requests_per_minute: int = Field(
        default=20, alias="MAX_MANUAL_JOB_ENTRY_CREATE_REQUESTS_PER_MINUTE"
    )
    max_outreach_send_requests_per_minute: int = Field(
        default=20, alias="MAX_OUTREACH_SEND_REQUESTS_PER_MINUTE"
    )
    max_job_matching_apply_requests_per_minute: int = Field(
        default=30, alias="MAX_JOB_MATCHING_APPLY_REQUESTS_PER_MINUTE"
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
    job_source_provider: str = Field(
        default="jobspy", alias="JOB_SOURCE_PROVIDER"
    )  # "jobspy" | "jsearch"
    jsearch_api_key: str = Field(default="", alias="JSEARCH_API_KEY")
    jsearch_api_host: str = Field(default="jsearch.p.rapidapi.com", alias="JSEARCH_API_HOST")
    jsearch_num_pages: int = Field(default=1, alias="JSEARCH_NUM_PAGES")
    jsearch_timeout_seconds: float = Field(default=20.0, alias="JSEARCH_TIMEOUT_SECONDS")
    gmaps_scraper_url: str = Field(default="", alias="GMAPS_SCRAPER_URL")
    gmaps_job_timeout_seconds: int = Field(default=300, alias="GMAPS_JOB_TIMEOUT_SECONDS")
    gmaps_job_poll_seconds: int = Field(default=10, alias="GMAPS_JOB_POLL_SECONDS")

    # Module 1: AI Job Matching & Notifications
    job_matching_enabled: bool = Field(default=True, alias="JOB_MATCHING_ENABLED")
    job_matching_scan_cron: str = Field(default="0 6 * * *", alias="JOB_MATCHING_SCAN_CRON")
    job_matching_max_postings_per_scan: int = Field(
        default=50, alias="JOB_MATCHING_MAX_POSTINGS_PER_SCAN"
    )
    job_matching_similarity_threshold: float = Field(
        default=0.5, alias="JOB_MATCHING_SIMILARITY_THRESHOLD"
    )
    job_matching_top_n_explanations: int = Field(default=5, alias="JOB_MATCHING_TOP_N_EXPLANATIONS")
    job_matching_inactive_after_days: int = Field(
        default=14, alias="JOB_MATCHING_INACTIVE_AFTER_DAYS"
    )
    job_matching_explanation_max_retries: int = Field(
        default=3, alias="JOB_MATCHING_EXPLANATION_MAX_RETRIES"
    )
    notify_sms_enabled: bool = Field(default=False, alias="NOTIFY_SMS_ENABLED")

    # Web push (browser notifications) — VAPID keypair, generate once via `vapid_gen_keys`
    # or the `py-vapid` CLI (ops step, not committed with real values).
    vapid_public_key: str = Field(default="", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str = Field(default="", alias="VAPID_PRIVATE_KEY")
    vapid_subject: str = Field(default="mailto:ops@example.com", alias="VAPID_SUBJECT")

    # LLM disambiguation
    disambiguation_threshold: float = Field(default=0.7, alias="DISAMBIGUATION_THRESHOLD")
    ollama_base_url: str = Field(default="", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")
    litellm_api_base: str = Field(default="", alias="LITELLM_API_BASE")
    litellm_api_key: str = Field(default="", alias="LITELLM_API_KEY")
    litellm_model: str = Field(default="gpt-4o-mini", alias="LITELLM_MODEL")
    litellm_fallbacks: str = Field(default="", alias="LITELLM_FALLBACKS")

    # Module 2: Tinder-Style Job Board + CV Management (portfolio public URL)
    # NOTE: all Module 2 §7 settings have now landed with the chunks that
    # consume them (Phase B) — portfolio/service.py, cv_chat_service.py,
    # feedback_generator.generate_cv_improvement() (§8.8), and
    # clients/perplexity.py + modules/outreach/service.py (§8.12-8.14) all
    # read the fields below and need them to be non-blocking per the
    # reviewer gate.
    portfolio_public_base_url: str = Field(default="", alias="PORTFOLIO_PUBLIC_BASE_URL")
    app_public_base_url: str = Field(default="", alias="APP_PUBLIC_BASE_URL")
    cv_chat_max_turns: int = Field(default=12, alias="CV_CHAT_MAX_TURNS")
    cv_feedback_model: str = Field(default="gpt-4o-mini", alias="CV_FEEDBACK_MODEL")

    # Module 2 §5.9/§8.12: Perplexity Sonar client + outreach drafting (Decision 5/7)
    # — added here because app/clients/perplexity.py and modules/outreach/service.py
    # already read these and need them to be non-blocking.
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")
    perplexity_api_base: str = Field(
        default="https://api.perplexity.ai", alias="PERPLEXITY_API_BASE"
    )
    outreach_enabled: bool = Field(default=True, alias="OUTREACH_ENABLED")

    # Company-tier-driven outreach drafting (machine-2/03): append a tier-specific
    # tone instruction (see _COMPANY_TIER_INSTRUCTIONS in
    # app/workers/tasks/outreach.py) to the drafting prompt when the target
    # employer has a manually-set EmployerCompanyTier row. Default False:
    # unlike strategy/role_type/seniority (recruiter-opted-in per draft, shipped
    # unconditionally), this is an always-on-once-enabled behavior change for
    # every draft to a tiered employer, and the tier->prompt-fragment mechanism
    # itself has no published precedent — ship it off, human-review a small
    # batch of real drafts, then enable broadly.
    enable_company_tier_in_outreach_drafting: bool = Field(
        default=False, alias="ENABLE_COMPANY_TIER_IN_OUTREACH_DRAFTING"
    )

    # CAN-SPAM (backend/app/modules/outreach/service.py's footer): the platform's
    # registered postal address, included in every outbound email-type outreach
    # message. Required by law, not cosmetic — leave unset only in environments
    # where OUTREACH_ENABLED is also False. No default value: an empty address
    # must not silently ship in a real send (enforced by validate_outreach_settings
    # below).
    outreach_physical_address: str = Field(default="", alias="OUTREACH_PHYSICAL_ADDRESS")

    # OpenAI API (for CV extraction, embeddings, etc.)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    enable_embeddings: bool = Field(default=True, alias="ENABLE_EMBEDDINGS")

    # Interview practice (Phase 2, Module 3) — question generation + voice tone.
    hume_api_key: str = Field(default="", alias="HUME_API_KEY")
    hume_prosody_timeout_seconds: int = Field(default=30, alias="HUME_PROSODY_TIMEOUT_SECONDS")
    question_generation_daily_limit_per_user: int = Field(
        default=10, alias="QUESTION_GENERATION_DAILY_LIMIT_PER_USER"
    )
    practice_audio_max_upload_mb: int = Field(default=25, alias="PRACTICE_AUDIO_MAX_UPLOAD_MB")
    embedding_chunk_size: int = Field(
        default=512,
        alias="EMBEDDING_CHUNK_SIZE",
        description="Maximum tokens per text chunk for embeddings",
    )
    embedding_chunk_overlap: int = Field(
        default=50,
        alias="EMBEDDING_CHUNK_OVERLAP",
        description="Token overlap between consecutive chunks",
    )

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

    # CORS allowlist — comma-separated origins, e.g. "https://app.example.com,https://admin.example.com".
    # Optional/opt-in: when unset, falls back to FRONTEND_URL (or localhost) so existing
    # single-origin deployments keep working unchanged. See cors_allowed_origins below.
    CORS_ALLOWED_ORIGINS: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Parsed CORS allowlist, falling back to FRONTEND_URL (or localhost) when unset."""
        origins = [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
        if origins:
            return origins
        return [self.FRONTEND_URL] if self.FRONTEND_URL else ["http://localhost:3000"]

    # Brand (docs/adr/0019-tenancy-model.md): include active brands' custom_domain
    # values in the CORS allow-list at startup, in addition to
    # CORS_ALLOWED_ORIGINS/FRONTEND_URL. Default False so existing deployments are
    # unaffected until opted in. Purely a routing/presentation concern -- Brand never
    # gates data access, so this flag has no security implication beyond "which
    # origins may make credentialed requests," identical in kind to the existing
    # CORS_ALLOWED_ORIGINS behavior it extends.
    enable_brand_cors_origins: bool = Field(default=False, alias="ENABLE_BRAND_CORS_ORIGINS")

    # Cookie settings
    COOKIE_SECURE: bool = Field(default=False, alias="COOKIE_SECURE")
    COOKIE_DOMAIN: str | None = Field(default=None, alias="COOKIE_DOMAIN")

    # RQ job timeout (seconds) — must accommodate full all-tier enrichment (20-30 min)
    rq_job_timeout_seconds: int = Field(default=3000, alias="RQ_JOB_TIMEOUT_SECONDS")

    # Budget monitoring
    DAILY_COST_THRESHOLD_USD: float = Field(default=100.0, alias="DAILY_COST_THRESHOLD_USD")
    MONTHLY_COST_THRESHOLD_USD: float = Field(default=2000.0, alias="MONTHLY_COST_THRESHOLD_USD")
    ENABLE_BUDGET_ALERTS: bool = Field(default=True, alias="ENABLE_BUDGET_ALERTS")

    # Admin Module: RBAC, audit log, feature flags, cached aggregates, MFA, impersonation
    # (phase2_admin_module.md §7) — only admin_aggregate_cache_ttl_seconds is read by
    # this chunk's files (cache.py); the rest are added now since core/config.py is a
    # single shared file and later phases' service.py/mfa.py/impersonation.py need them.
    admin_audit_log_retention_days: int = Field(
        default=1825, alias="ADMIN_AUDIT_LOG_RETENTION_DAYS"
    )
    admin_aggregate_cache_ttl_seconds: int = Field(
        default=300, alias="ADMIN_AGGREGATE_CACHE_TTL_SECONDS"
    )
    admin_default_page_size: int = Field(default=20, alias="ADMIN_DEFAULT_PAGE_SIZE")
    admin_max_page_size: int = Field(default=100, alias="ADMIN_MAX_PAGE_SIZE")
    admin_mfa_issuer_name: str = Field(default="Hyrepath Admin", alias="ADMIN_MFA_ISSUER_NAME")
    admin_impersonation_max_duration_minutes: int = Field(
        default=30, alias="ADMIN_IMPERSONATION_MAX_DURATION_MINUTES"
    )
    prometheus_query_url: str = Field(default="", alias="PROMETHEUS_QUERY_URL")

    # Module A — job matching fallback relaxation
    job_matching_min_results: int = Field(default=10, alias="JOB_MATCHING_MIN_RESULTS")

    # Module B — apply-click tracking / redirect
    apply_redirect_base_url: str = Field(default="", alias="APPLY_REDIRECT_BASE_URL")
    # empty => derive from app_public_base_url; see Module B §5.3

    # Module C — application tracker (no new settings; reuses existing pagination/limit conventions)

    # Module D — interview scheduling, calendar, notifications
    interview_reminder_hours_before: int = Field(
        default=24, alias="INTERVIEW_REMINDER_HOURS_BEFORE"
    )
    interview_ics_organizer_email: str = Field(
        default="", alias="INTERVIEW_ICS_ORGANIZER_EMAIL"
    )  # falls back to sendgrid_from_email if empty

    # Module E — JD-aware interview practice
    jd_question_generation_daily_limit_per_user: int = Field(
        default=10, alias="JD_QUESTION_GENERATION_DAILY_LIMIT_PER_USER"
    )  # separate budget from question_generation_daily_limit_per_user (Module 3) since
    # JD-tailored generation always bypasses the shared bank (§9.3) and is therefore
    # more expensive per request; kept as an independent knob rather than reusing
    # question_generation_daily_limit_per_user so ops can tune them independently.

    # Module F — manual job entry (no new settings)

    # Module G — multi-channel outreach messages
    outreach_linkedin_inmail_body_max_chars: int = Field(
        default=1900, alias="OUTREACH_LINKEDIN_INMAIL_BODY_MAX_CHARS"
    )
    outreach_linkedin_inmail_subject_max_chars: int = Field(
        default=200, alias="OUTREACH_LINKEDIN_INMAIL_SUBJECT_MAX_CHARS"
    )
    outreach_linkedin_connection_note_max_chars: int = Field(
        default=300, alias="OUTREACH_LINKEDIN_CONNECTION_NOTE_MAX_CHARS"
    )

    # Demand intelligence -> outreach integration (machine-2/07): inject a short,
    # factual country-demand context line into outreach-draft prompts when the
    # candidate has desired_roles populated and demand data exists for one of them.
    # Default False — additive, low-risk, but off until validated against real drafts;
    # also has no effect unless enable_demand_intelligence (02's flag) is also True,
    # since there is no snapshot data to inject without it.
    enable_demand_intelligence_in_outreach: bool = Field(
        default=False, alias="ENABLE_DEMAND_INTELLIGENCE_IN_OUTREACH"
    )

    # Demand intelligence -> resume-tailoring integration (machine-2/10): inject a
    # short, factual country-demand context line into the resume-tailoring prompt
    # when a target role (or, absent that, one of the candidate's desired_roles) has
    # CountryDemandSnapshot data. Mirrors enable_demand_intelligence_in_outreach's
    # contract exactly (07-demand-intelligence-resume-integration.md). Default False
    # — additive, low-risk, but off until validated against real tailored output;
    # also has no effect unless enable_demand_intelligence (02's flag) is also True.
    enable_demand_intelligence_in_resume_tailoring: bool = Field(
        default=False, alias="ENABLE_DEMAND_INTELLIGENCE_IN_RESUME_TAILORING"
    )

    # Demand intelligence (machine-2/02): enable the daily country/role posting-count
    # aggregation job. Default True — launch-relevant: recruiter market-research
    # prioritization (Tier 1/2/3 methodology) and resume-tailoring's country-specific
    # personalization (enable_demand_intelligence_in_resume_tailoring above) both depend
    # on this data being live at launch, not bolted on later.
    enable_demand_intelligence: bool = Field(default=True, alias="ENABLE_DEMAND_INTELLIGENCE")

    # Billing (docs/adr/0020-billing-provider.md): Stripe integration. Default disabled --
    # no billing enforcement until an operator explicitly opts in with real Stripe keys.
    enable_billing: bool = Field(default=False, alias="ENABLE_BILLING")
    stripe_secret_key: SecretStr = Field(default=SecretStr(""), alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: SecretStr = Field(default=SecretStr(""), alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id_premium: str = Field(default="", alias="STRIPE_PRICE_ID_PREMIUM")


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


def validate_outreach_settings(settings: Settings | None = None) -> None:
    """Fail fast when outreach is enabled without a CAN-SPAM-required physical address.

    Raises RuntimeError naming the missing env key. No-op when outreach_enabled is False.
    """
    cfg = settings if settings is not None else get_settings()
    if not cfg.outreach_enabled:
        return
    if not cfg.outreach_physical_address.strip():
        raise RuntimeError("OUTREACH_PHYSICAL_ADDRESS is required when OUTREACH_ENABLED is true")


def validate_billing_settings(settings: Settings | None = None) -> None:
    """Fail fast when billing is enabled without required Stripe credentials.

    Raises RuntimeError listing missing env key *names* only (never secret values).
    No-op when ``enable_billing`` is false.
    """
    cfg = settings if settings is not None else get_settings()
    if not cfg.enable_billing:
        return

    missing: list[str] = []
    if not cfg.stripe_secret_key.get_secret_value().strip():
        missing.append("STRIPE_SECRET_KEY")
    if not cfg.stripe_webhook_secret.get_secret_value().strip():
        missing.append("STRIPE_WEBHOOK_SECRET")
    if not cfg.stripe_price_id_premium.strip():
        missing.append("STRIPE_PRICE_ID_PREMIUM")

    if missing:
        raise RuntimeError(
            "ENABLE_BILLING=true but required settings are missing: " + ", ".join(missing)
        )


_INSECURE_SECRET_KEYS = frozenset(
    {
        "change-me-in-production-use-openssl-rand-hex-32",
        "change-me",
        "secret",
        "changeme",
    }
)
_INSECURE_API_TOKENS = frozenset({"change-me", "changeme", "dev-token", "dev-token-123"})
_PROD_LIKE_ENVS = frozenset({"production", "staging"})


def validate_production_security_settings(settings: Settings | None = None) -> None:
    """Refuse to start staging/production with insecure auth or cookie settings.

    Development remains permissive so local defaults keep working.
    """
    cfg = settings if settings is not None else get_settings()
    if cfg.app_env.strip().lower() not in _PROD_LIKE_ENVS:
        return

    problems: list[str] = []
    secret = cfg.SECRET_KEY.strip()
    if not secret or secret.lower() in _INSECURE_SECRET_KEYS or len(secret) < 32:
        problems.append(
            "SECRET_KEY must be set to a unique value of at least 32 characters "
            "(generate with: openssl rand -hex 32)"
        )
    api_token = cfg.api_token.strip()
    if not api_token or api_token.lower() in _INSECURE_API_TOKENS:
        problems.append("API_TOKEN must be set to a non-default production value")
    if not cfg.COOKIE_SECURE:
        problems.append("COOKIE_SECURE must be true when APP_ENV is staging or production")
    if not cfg.changedetection_api_key.strip():
        problems.append("CHANGEDETECTION_API_KEY must be set (signals webhook must not be open)")

    if problems:
        raise RuntimeError(
            "Refusing to start with insecure production settings: " + "; ".join(problems)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
