from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.config import Settings, get_settings
from app.routes import (
    dsar_router,
    enrich_router,
    health_router,
    opt_out_router,
    signals_list_router,
    signals_webhook_router,
)
from app.routes.rate_limit import enforce_compliance_rate_limit
from app.storage.db import init_db
from app.storage.redis_client import close_redis, get_redis_client


async def verify_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    get_redis_client()
    yield
    await close_redis()


app = FastAPI(title="Hyrepath Enrichment Backend", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(enrich_router, dependencies=[Depends(verify_token)])
_compliance_deps = [Depends(enforce_compliance_rate_limit)]
app.include_router(opt_out_router, dependencies=_compliance_deps)
app.include_router(dsar_router, dependencies=_compliance_deps)
app.include_router(signals_webhook_router)
app.include_router(signals_list_router, dependencies=[Depends(verify_token)])
