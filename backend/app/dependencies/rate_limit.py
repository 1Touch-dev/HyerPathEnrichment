import hashlib
import logging

from fastapi import Depends, Header, Request
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitError
from app.infrastructure.redis import check_rate_limit, get_redis_client

logger = logging.getLogger(__name__)


def _client_id(authorization: str | None) -> str:
    """Stable per-caller id without logging the raw token."""
    token = (authorization or "anonymous").removeprefix("Bearer ").strip()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _host_client_id(request: Request) -> str:
    """Stable per-IP id for unauthenticated compliance routes."""
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:16]


def _request_client_id(request: Request, authorization: str | None = None) -> str:
    """Prefer Bearer, else access_token cookie + IP (cookie-auth browsers)."""
    bearer = (authorization or "").removeprefix("Bearer ").strip()
    if bearer:
        material = f"bearer:{bearer}"
    else:
        cookie = (request.cookies.get("access_token") or "").strip()
        host = request.client.host if request.client else "unknown"
        material = f"cookie:{cookie}|ip:{host}" if cookie else f"ip:{host}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


async def _enforce(scope: str, limit: int) -> None:
    try:
        allowed = await check_rate_limit(get_redis_client(), scope, limit)
    except RedisError:
        # Fail open: rate limiting is protection, not correctness. A Redis
        # outage must not block legitimate enrichment traffic.
        logger.warning("redis unavailable during rate limit check; allowing request")
        return
    if not allowed:
        raise RateLimitError(
            "rate limit exceeded",
            meta={"scope": scope.split(":", 1)[0], "limit_per_minute": limit},
        )


async def enforce_sync_rate_limit(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(f"sync:{_client_id(authorization)}", settings.max_sync_requests_per_minute)


async def enforce_async_rate_limit(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(f"async:{_client_id(authorization)}", settings.max_async_requests_per_minute)


async def enforce_compliance_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"compliance:{_host_client_id(request)}",
        settings.max_compliance_requests_per_minute,
    )


async def enforce_auth_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"auth:{_host_client_id(request)}",
        settings.max_auth_requests_per_minute,
    )


async def enforce_auth_refresh_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"auth_refresh:{_host_client_id(request)}",
        settings.max_auth_refresh_requests_per_minute,
    )


async def enforce_documents_upload_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"documents:{_request_client_id(request, authorization)}",
        settings.max_documents_upload_requests_per_minute,
    )


async def enforce_signals_webhook_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"signals:{_host_client_id(request)}",
        settings.max_signals_webhook_requests_per_minute,
    )


async def enforce_job_matching_scan_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"job_matching:{_request_client_id(request, authorization)}",
        settings.max_job_matching_scan_requests_per_minute,
    )


# Admin module (Step 5): brute-force/abuse-sensitive admin endpoints.


async def enforce_admin_impersonation_start_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"admin_impersonation_start:{_request_client_id(request, authorization)}",
        settings.max_admin_impersonation_start_requests_per_minute,
    )


async def enforce_admin_mfa_verify_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"admin_mfa_verify:{_request_client_id(request, authorization)}",
        settings.max_admin_mfa_verify_requests_per_minute,
    )


async def enforce_admin_review_queue_decide_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"admin_review_queue_decide:{_request_client_id(request, authorization)}",
        settings.max_admin_review_queue_decide_requests_per_minute,
    )


async def enforce_admin_moderation_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Shared scope for admin moderation mutating endpoints (documents, outreach,
    portfolio, job_postings) — a moderator hitting one moderation router hard
    shares the same abuse budget as hitting another, rather than each domain
    getting its own independent allowance."""
    await _enforce(
        f"admin_moderation:{_request_client_id(request, authorization)}",
        settings.max_admin_moderation_requests_per_minute,
    )


# Module 3/4 (Step 5): distinct per-minute caps from any existing daily/quota-style
# caps enforced in the service layer.


async def enforce_questions_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"questions:{_request_client_id(request, authorization)}",
        settings.max_questions_requests_per_minute,
    )


async def enforce_practice_audio_upload_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"practice_audio_upload:{_request_client_id(request, authorization)}",
        settings.max_practice_audio_upload_requests_per_minute,
    )


async def enforce_jd_practice_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"jd_practice:{_request_client_id(request, authorization)}",
        settings.max_jd_practice_requests_per_minute,
    )


async def enforce_application_tracker_status_update_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"application_tracker_status_update:{_request_client_id(request, authorization)}",
        settings.max_application_tracker_status_update_requests_per_minute,
    )


async def enforce_interview_scheduling_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"interview_scheduling:{_request_client_id(request, authorization)}",
        settings.max_interview_scheduling_requests_per_minute,
    )


async def enforce_manual_job_entry_create_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"manual_job_entry_create:{_request_client_id(request, authorization)}",
        settings.max_manual_job_entry_create_requests_per_minute,
    )


async def enforce_outreach_send_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(
        f"outreach_send:{_request_client_id(request, authorization)}",
        settings.max_outreach_send_requests_per_minute,
    )


async def enforce_job_matching_apply_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Shared scope for the apply-redirect and mark-applied routes — both are
    candidate-initiated application-lifecycle actions on the same abuse budget."""
    await _enforce(
        f"job_matching_apply:{_request_client_id(request, authorization)}",
        settings.max_job_matching_apply_requests_per_minute,
    )
