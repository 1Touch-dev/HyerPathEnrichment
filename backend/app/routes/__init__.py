from app.modules.dsar.router import router as dsar_router
from app.modules.enrichment.router import router as enrich_router
from app.modules.health.router import router as health_router
from app.modules.opt_out.router import router as opt_out_router
from app.modules.signals.router import list_router as signals_list_router
from app.modules.signals.router import webhook_router as signals_webhook_router

__all__ = [
    "dsar_router",
    "enrich_router",
    "health_router",
    "opt_out_router",
    "signals_list_router",
    "signals_webhook_router",
]
