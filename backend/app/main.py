from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import VerifiedUser
from app.auth.router import router as auth_router
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import RequestContextMiddleware
from app.dependencies.rate_limit import enforce_compliance_rate_limit
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.modules.admin.router import router as admin_router
from app.modules.documents.router import router as documents_router
from app.modules.dsar.router import router as dsar_router
from app.modules.email.router import router as email_router
from app.modules.enrichment.router import router as enrich_router
from app.modules.health.router import router as health_router
from app.modules.job_matching.router import router as job_matching_router
from app.modules.job_swipe.router import router as job_swipe_router
from app.modules.opt_out.router import router as opt_out_router
from app.modules.outreach.router import router as outreach_router
from app.modules.portfolio.router import public_router as portfolio_public_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.practice_audio.router import router as practice_audio_router
from app.modules.questions.router import router as questions_router
from app.modules.sessions.router import router as sessions_router
from app.modules.signals.router import list_router as signals_list_router
from app.modules.signals.router import webhook_router as signals_webhook_router


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

# CORS configuration for frontend
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL] if settings.FRONTEND_URL else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Public routes (no auth required)
app.include_router(health_router)
app.include_router(opt_out_router, dependencies=[Depends(enforce_compliance_rate_limit)])

# Auth routes (authentication itself)
app.include_router(auth_router)

# Protected routes (require verified user)
app.include_router(admin_router, dependencies=[Depends(current_verified_user)])
app.include_router(documents_router, dependencies=[Depends(current_verified_user)])
app.include_router(enrich_router, dependencies=[Depends(current_verified_user)])
app.include_router(email_router, dependencies=[Depends(current_verified_user)])
app.include_router(sessions_router, dependencies=[Depends(current_verified_user)])
app.include_router(questions_router, dependencies=[Depends(current_verified_user)])
app.include_router(practice_audio_router, dependencies=[Depends(current_verified_user)])
app.include_router(job_matching_router, dependencies=[Depends(current_verified_user)])
app.include_router(portfolio_router, dependencies=[Depends(current_verified_user)])
app.include_router(portfolio_public_router)
app.include_router(job_swipe_router, dependencies=[Depends(current_verified_user)])
app.include_router(outreach_router, dependencies=[Depends(current_verified_user)])
app.include_router(
    dsar_router,
    dependencies=[Depends(current_verified_user), Depends(enforce_compliance_rate_limit)],
)
app.include_router(signals_webhook_router)
app.include_router(signals_list_router, dependencies=[Depends(current_verified_user)])
