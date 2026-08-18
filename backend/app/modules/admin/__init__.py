"""Admin module for cost monitoring and system administration."""

from fastapi import APIRouter

from app.modules.admin.analytics_router import router as analytics_router
from app.modules.admin.audit_router import router as audit_router
from app.modules.admin.flags_router import router as flags_router
from app.modules.admin.health_router import router as health_router
from app.modules.admin.impersonation_router import router as impersonation_router
from app.modules.admin.mfa_router import router as mfa_router
from app.modules.admin.queues_router import router as queues_router
from app.modules.admin.roles_router import router as roles_router
from app.modules.admin.router import router as costs_router
from app.modules.admin.users_router import router as users_router

router = APIRouter()
router.include_router(costs_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(audit_router)
router.include_router(flags_router)
router.include_router(queues_router)
router.include_router(health_router)
router.include_router(analytics_router)
router.include_router(mfa_router)
router.include_router(impersonation_router)
