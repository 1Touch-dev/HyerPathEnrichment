"""Erase user-owned product data on account deletion (P1 cascade)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import CandidateDocument, CvChatSession
from app.modules.linkedin_sourcing.models import SourcedCandidateLead
from app.modules.outreach.models import OutreachMessage

logger = logging.getLogger(__name__)


async def erase_user_owned_data(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """Delete or scrub product rows owned by ``user_id``.

    Document CASCADE removes jobs/embeddings/chat children. Outreach messages
    are deleted. Sourced leads keep the row but scrub PII and null actor FKs.
    """
    counts = {"documents": 0, "outreach": 0, "sourced_leads_scrubbed": 0}

    doc_result = await db.execute(
        select(CandidateDocument.id).where(CandidateDocument.user_id == user_id)
    )
    doc_ids = list(doc_result.scalars().all())
    if doc_ids:
        # Explicit chat session delete is redundant if CASCADE is wired from
        # documents, but CvChatSession is keyed by user_id as well.
        await db.execute(delete(CvChatSession).where(CvChatSession.user_id == user_id))
        await db.execute(delete(CandidateDocument).where(CandidateDocument.user_id == user_id))
        counts["documents"] = len(doc_ids)

    outreach_ids = list(
        (await db.execute(select(OutreachMessage.id).where(OutreachMessage.user_id == user_id)))
        .scalars()
        .all()
    )
    if outreach_ids:
        await db.execute(delete(OutreachMessage).where(OutreachMessage.user_id == user_id))
    counts["outreach"] = len(outreach_ids)

    lead_result = await db.execute(
        select(SourcedCandidateLead).where(
            (SourcedCandidateLead.sourced_by == user_id)
            | (SourcedCandidateLead.reviewed_by == user_id)
        )
    )
    leads = list(lead_result.scalars().all())
    for lead in leads:
        if lead.sourced_by == user_id:
            lead.sourced_by = None
        if lead.reviewed_by == user_id:
            lead.reviewed_by = None
        # Scrub PII if this user was the sole actor on the lead.
        if lead.sourced_by is None and lead.reviewed_by is None:
            lead.full_name = "[redacted]"
            lead.headline = None
            lead.location = None
            lead.linkedin_profile_url = "https://www.linkedin.com/in/redacted"
            lead.notes = None
            lead.target_role = None
            counts["sourced_leads_scrubbed"] += 1

    await db.flush()
    logger.info("erase_user_owned_data user_id=%s counts=%s", user_id, counts)
    return counts
