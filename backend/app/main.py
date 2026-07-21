from fastapi import Depends, FastAPI, Header

from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import RequestContextMiddleware
from app.dependencies.rate_limit import enforce_compliance_rate_limit
from app.modules.dsar.router import router as dsar_router
from app.modules.enrichment.router import router as enrich_router
from app.modules.health.router import router as health_router
from app.modules.opt_out.router import router as opt_out_router
from app.modules.signals.router import list_router as signals_list_router
from app.modules.signals.router import webhook_router as signals_webhook_router


async def verify_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise UnauthorizedError("unauthorized")


app = FastAPI(
    title="Hyrepath Enrichment Backend",
    version="0.1.0",
    lifespan=lifespan,
    route_class=EnvelopeAPIRoute,
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(enrich_router, dependencies=[Depends(verify_token)])
_compliance_deps = [Depends(enforce_compliance_rate_limit)]
app.include_router(opt_out_router, dependencies=_compliance_deps)
app.include_router(dsar_router, dependencies=_compliance_deps)
app.include_router(signals_webhook_router)
app.include_router(signals_list_router, dependencies=[Depends(verify_token)])
