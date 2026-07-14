from app.routes.dsar import router as dsar_router
from app.routes.enrich import router as enrich_router
from app.routes.health import router as health_router
from app.routes.opt_out import router as opt_out_router
from app.routes.signals import router as signals_router

__all__ = ["dsar_router", "enrich_router", "health_router", "opt_out_router", "signals_router"]
