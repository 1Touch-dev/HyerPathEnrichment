"""Admin module for cost monitoring and system administration."""

from fastapi import APIRouter

from app.modules.admin.ai_supervision_router import router as ai_supervision_router
from app.modules.admin.analytics_router import router as analytics_router
from app.modules.admin.applications_router import router as applications_router
from app.modules.admin.audit_router import router as audit_router
from app.modules.admin.documents_router import router as documents_router
from app.modules.admin.flags_router import router as flags_router
from app.modules.admin.health_router import router as health_router
from app.modules.admin.interview_schedules_router import router as interview_schedules_router
from app.modules.admin.job_postings_router import router as job_postings_router
from app.modules.admin.job_swipe_router import router as job_swipe_router
from app.modules.admin.manual_job_entries_router import router as manual_job_entries_router
from app.modules.admin.outreach_router import router as outreach_router
from app.modules.admin.portfolio_router import router as portfolio_router
from app.modules.admin.practice_audio_router import router as practice_audio_router
from app.modules.admin.questions_router import router as questions_router
from app.modules.admin.queues_router import router as queues_router
from app.modules.admin.review_queue_router import router as review_queue_router
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
router.include_router(job_swipe_router)
router.include_router(portfolio_router)
router.include_router(job_postings_router)
router.include_router(documents_router)
router.include_router(outreach_router)
router.include_router(questions_router)
router.include_router(practice_audio_router)
router.include_router(review_queue_router)
router.include_router(applications_router)
router.include_router(interview_schedules_router)
router.include_router(manual_job_entries_router)
router.include_router(ai_supervision_router)
