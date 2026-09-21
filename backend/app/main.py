from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import VerifiedUser
from app.auth.router import identity_router as auth_identity_router
from app.auth.router import router as auth_router
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.cors import CORS_ORIGINS
from app.core.errors import UnauthorizedError
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import RequestContextMiddleware
from app.core.openapi import install_envelope_openapi
from app.dependencies.rate_limit import enforce_compliance_rate_limit
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.modules.admin import router as admin_router
from app.modules.admin.audit import AdminAuditFallbackMiddleware
from app.modules.admin.impersonation_router import router as impersonation_router
from app.modules.admin.mfa_router import router as mfa_router
from app.modules.admin.permissions import require_staff
from app.modules.application_tracker.router import router as application_tracker_router
from app.modules.billing.mock_router import router as billing_mock_router
from app.modules.billing.router import router as billing_router
from app.modules.billing.webhook_router import router as billing_webhook_router
from app.modules.brands.assignment_router import router as recruiter_assignments_router
from app.modules.brands.deactivation_router import router as brand_deactivation_router
from app.modules.brands.public_router import public_router as brands_public_router
from app.modules.brands.router import router as brands_router
from app.modules.demand_intelligence.router import router as demand_intelligence_router
from app.modules.documents.router import router as documents_router
from app.modules.dsar.router import router as dsar_router
from app.modules.email.router import router as email_router
from app.modules.enrichment.router import router as enrich_router
from app.modules.health.router import router as health_router
from app.modules.interview_scheduling.router import router as interview_scheduling_router
from app.modules.jd_practice.router import router as jd_practice_router
from app.modules.job_matching.router import router as job_matching_router
from app.modules.job_swipe.router import router as job_swipe_router
from app.modules.linkedin_sourcing.router import router as linkedin_sourcing_router
from app.modules.manual_jobs.router import router as manual_jobs_router
from app.modules.opt_out.router import router as opt_out_router
from app.modules.outreach.linkedin_send_router import router as linkedin_send_router
from app.modules.outreach.router import router as outreach_router
from app.modules.portfolio.router import public_router as portfolio_public_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.practice_audio.router import router as practice_audio_router
from app.modules.questions.router import router as questions_router
from app.modules.recruiter_actions.router import router as recruiter_actions_router
from app.modules.recruiter_actions.router import users_router as recruiter_action_mode_router
from app.modules.resume_tailoring.router import router as resume_tailoring_router
from app.modules.sessions.router import router as sessions_router
from app.modules.signals.router import list_router as signals_list_router
from app.modules.signals.router import webhook_router as signals_webhook_router
from app.modules.staff_invites.router import public_router as staff_invites_public_router
from app.modules.staff_invites.router import router as staff_invites_router


async def verify_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Legacy API token verification (deprecated, use auth instead)."""
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise UnauthorizedError("unauthorized")


async def current_verified_user(user: VerifiedUser) -> VerifiedUser:
    """Require authenticated and verified user (replacement for verify_token)."""
    return user


app = FastAPI(
    title="Hyrepath Enrichment Backend",
    version="0.1.0",
    lifespan=lifespan,
    route_class=EnvelopeAPIRoute,
)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AdminAuditFallbackMiddleware)

# CORS configuration for frontend. `CORS_ORIGINS` is the same list object
# `app/core/lifespan.py`'s startup sequence mutates in place once active
# brands' custom_domain values are resolved (machine-1-tenancy-core/04);
# CORSMiddleware only ever reads from it, so it picks up that update even
# though the middleware itself is constructed once, here, at import time.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    # Actual verb set used across app/modules/*/router.py + OPTIONS for preflight.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Only headers a browser-based client needs to send; server-side-only headers
    # (X-Forwarded-For, X-Real-IP, User-Agent, X-Request-ID) don't need to be listed here.
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["*"],
    # Cache preflight responses for 10 minutes to cut down on repeated OPTIONS round-trips.
    max_age=600,
)

# Register exception handlers
register_exception_handlers(app)

# Public routes (no auth required)
app.include_router(health_router)
app.include_router(opt_out_router, dependencies=[Depends(enforce_compliance_rate_limit)])

# Auth routes (authentication itself)
app.include_router(auth_router)
app.include_router(auth_identity_router)

# Protected routes (require verified user)
app.include_router(
    admin_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(mfa_router, dependencies=[Depends(current_verified_user)])
app.include_router(impersonation_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    brand_deactivation_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(
    brands_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(
    recruiter_assignments_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(documents_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    enrich_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(email_router, dependencies=[Depends(current_verified_user)])
app.include_router(sessions_router, dependencies=[Depends(current_verified_user)])
app.include_router(questions_router, dependencies=[Depends(current_verified_user)])
app.include_router(practice_audio_router, dependencies=[Depends(current_verified_user)])
app.include_router(job_matching_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    demand_intelligence_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(billing_router, dependencies=[Depends(current_verified_user)])
app.include_router(billing_webhook_router)
# Always include mock checkout/portal pages (no cookie auth). Endpoints 404 unless
# stripe_mode=mock at request time — get_settings() is lru_cached and the app is
# built at import, so TestClient monkeypatches after import would miss an
# import-time gate.
app.include_router(billing_mock_router)
app.include_router(application_tracker_router, dependencies=[Depends(current_verified_user)])
app.include_router(interview_scheduling_router, dependencies=[Depends(current_verified_user)])
app.include_router(jd_practice_router, dependencies=[Depends(current_verified_user)])
app.include_router(portfolio_router, dependencies=[Depends(current_verified_user)])
app.include_router(portfolio_public_router)
app.include_router(brands_public_router)
app.include_router(job_swipe_router, dependencies=[Depends(current_verified_user)])
app.include_router(outreach_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    linkedin_send_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(
    linkedin_sourcing_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(recruiter_actions_router, dependencies=[Depends(current_verified_user)])
app.include_router(recruiter_action_mode_router, dependencies=[Depends(current_verified_user)])
app.include_router(resume_tailoring_router, dependencies=[Depends(current_verified_user)])
app.include_router(manual_jobs_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    dsar_router,
    dependencies=[Depends(current_verified_user), Depends(enforce_compliance_rate_limit)],
)
app.include_router(signals_webhook_router)
app.include_router(
    signals_list_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(
    staff_invites_router,
    dependencies=[Depends(current_verified_user), Depends(require_staff)],
)
app.include_router(staff_invites_public_router)

install_envelope_openapi(app)
