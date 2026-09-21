"""Data-access layer for staff invites. Plain async functions, not a class --
matches app/modules/portfolio/repository.py's style."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.errors import AppError
from app.core.secret_box import open_secret_strict, seal_secret
from app.modules.admin import privileged_operations_repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.models import PrivilegedIdempotencyRecord, Role
from app.modules.staff_invites.models import StaffInvite

_ISSUE_OPERATION = "staff_invite.issued"


def _issue_request_hash(email: str, role_name: str) -> str:
    canonical = json.dumps(
        {
            "email_digest": hashlib.sha256(email.casefold().encode("utf-8")).hexdigest(),
            "role_name": role_name,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


async def _replay_completed_invite(
    db: AsyncSession,
    *,
    record: PrivilegedIdempotencyRecord,
    request_hash: str,
) -> tuple[StaffInvite, str | None]:
    if record.request_hash != request_hash:
        raise AppError(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency key was already used for a different request",
            409,
        )
    if record.completed_at is None:
        raise AppError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "An equivalent request is already in progress",
            409,
        )
    if _aware(record.expires_at) <= datetime.now(UTC):
        raise AppError(
            "IDEMPOTENCY_REPLAY_EXPIRED",
            "The idempotent response replay window has expired",
            409,
        )
    response_body = record.response_body or {}
    invite_id = response_body.get("invite_id")
    try:
        replay = await db.get(StaffInvite, UUID(str(invite_id)))
    except (TypeError, ValueError):
        replay = None
    if replay is None:
        raise AppError(
            "IDEMPOTENCY_REPLAY_UNAVAILABLE",
            "The idempotent response cannot be replayed",
            409,
        )
    sealed_token = response_body.get("sealed_invite_token")
    if sealed_token is None:
        return replay, None
    if not isinstance(sealed_token, str):
        raise AppError(
            "IDEMPOTENCY_REPLAY_UNAVAILABLE",
            "The idempotent response cannot be replayed",
            409,
        )
    try:
        plaintext_token = open_secret_strict(sealed_token)
    except InvalidToken:
        raise AppError(
            "IDEMPOTENCY_REPLAY_UNAVAILABLE",
            "The idempotent response cannot be replayed",
            409,
        ) from None
    expected_digest = hashlib.sha256(plaintext_token.encode("utf-8")).hexdigest()
    if replay.token_digest is None or expected_digest != replay.token_digest:
        raise AppError(
            "IDEMPOTENCY_REPLAY_UNAVAILABLE",
            "The idempotent response cannot be replayed",
            409,
        )
    return replay, plaintext_token


async def _record_successful_post(
    db: AsyncSession,
    *,
    invited_by: UUID,
    invite: StaffInvite,
    request_id: str,
    ip_address: str | None,
    result: str,
) -> None:
    """Audit one successful POST attempt in the transaction returning it."""
    action = {
        "issued": _ISSUE_OPERATION,
        "replayed": "staff_invite.replayed",
        "reused": "staff_invite.reused",
        "conflict_winner": "staff_invite.conflict_winner",
    }[result]
    await record_admin_action(
        db,
        actor_user_id=invited_by,
        action=action,
        target_type="staff_invite",
        target_id=str(invite.id),
        after={"role_name": "recruiter", "result": result},
        ip_address=ip_address,
        request_id=request_id,
        outcome="success",
    )


async def get_invite_by_token(
    db: AsyncSession,
    token: str,
    *,
    lock_for_update: bool = False,
) -> StaffInvite | None:
    """Resolve by digest, with a narrowly bounded restored-schema fallback.

    The plaintext comparison is permitted only when ``token_digest IS NULL``,
    which can occur after data restoration or interrupted recovery. Revision
    065 backfills every pre-existing row and all current writes populate the
    digest. The fallback never broadens lookup to a row that already has a
    digest, and acknowledged cleanup backfills then removes it. It is not
    compatibility for a pre-hardening API binary, which deployment policy
    prohibits from serving invite traffic.
    """
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    digest_query = select(StaffInvite).where(StaffInvite.token_digest == token_digest)
    if lock_for_update:
        digest_query = digest_query.with_for_update()
    result = await db.execute(digest_query)
    invite = result.scalar_one_or_none()
    if invite is not None:
        if invite.invited_by is None:
            return None
        inviter_query = select(User.id).where(
            User.id == invite.invited_by,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        if lock_for_update:
            inviter_query = inviter_query.with_for_update()
        inviter_exists = await db.scalar(inviter_query)
        if inviter_exists is None:
            return None
        return invite

    legacy_query = select(StaffInvite).where(
        StaffInvite.token_digest.is_(None),
        StaffInvite.token == token,
        StaffInvite.accepted_at.is_(None),
        StaffInvite.revoked_at.is_(None),
        StaffInvite.expires_at >= datetime.now(UTC),
        StaffInvite.role_name == "recruiter",
        StaffInvite.role_id.is_not(None),
        StaffInvite.invited_by.is_not(None),
    )
    if lock_for_update:
        legacy_query = legacy_query.with_for_update()
    legacy_result = await db.execute(legacy_query)
    legacy_invite = legacy_result.scalar_one_or_none()
    if legacy_invite is None:
        return None

    role = await db.get(
        Role,
        legacy_invite.role_id,
        with_for_update=lock_for_update,
    )
    if role is None or role.name != "recruiter":
        return None
    inviter_query = select(User.id).where(
        User.id == legacy_invite.invited_by,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if lock_for_update:
        inviter_query = inviter_query.with_for_update()
    inviter_id = await db.scalar(inviter_query)
    if inviter_id is None:
        return None
    return legacy_invite


async def get_pending_invite_for_email(db: AsyncSession, email: str) -> StaffInvite | None:
    """Pending (accepted_at IS NULL) and unexpired invite for this email, if any.
    Backs the resend-upsert edge case -- do not create a second row for the
    same still-pending, unexpired email."""
    result = await db.execute(
        select(StaffInvite)
        .join(Role, StaffInvite.role_id == Role.id)
        .join(User, StaffInvite.invited_by == User.id)
        .where(
            func.lower(StaffInvite.email) == email.lower(),
            StaffInvite.accepted_at.is_(None),
            StaffInvite.revoked_at.is_(None),
            StaffInvite.expires_at >= datetime.now(UTC),
            StaffInvite.role_name == "recruiter",
            Role.name == "recruiter",
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def create_invite(
    db: AsyncSession,
    *,
    email: str,
    role_name: str,
    invited_by: UUID,
    request_id: str,
    idempotency_key: str,
    ip_address: str | None = None,
) -> tuple[StaffInvite, str | None]:
    """Issue or reuse a recruiter invite in one transaction.

    Expired active rows are revoked and flushed before insertion so the
    partial active-email uniqueness index cannot reject a legitimate reissue.
    The plaintext token is returned only for a newly created invite.
    """
    if role_name != "recruiter":
        raise ValueError("Staff invites are recruiter-only")
    if invited_by is None:
        raise ValueError("An authenticated actor is required to issue a staff invite")
    if not request_id or not request_id.strip():
        raise ValueError("A request ID is required to issue a staff invite")
    request_id = request_id.strip()
    idempotency_key = idempotency_key.strip() if idempotency_key else ""
    if not idempotency_key:
        raise ValueError("An Idempotency-Key is required to issue a staff invite")

    now = datetime.now(UTC)
    role_result = await db.execute(select(Role).where(Role.name == "recruiter"))
    recruiter_role = role_result.scalar_one_or_none()
    if recruiter_role is None:
        raise RuntimeError("Seeded recruiter role is required to create an invite")
    actor_exists = await db.scalar(
        select(User.id).where(
            User.id == invited_by,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if actor_exists is None:
        raise ValueError("An active authenticated actor is required to issue a staff invite")

    normalized_email = email.casefold()
    request_hash = _issue_request_hash(normalized_email, role_name)
    existing_record = await privileged_operations_repository.get_idempotency_record(
        db,
        caller_user_id=invited_by,
        operation=_ISSUE_OPERATION,
        idempotency_key=idempotency_key,
    )
    if existing_record is not None:
        try:
            replay, replay_token = await _replay_completed_invite(
                db,
                record=existing_record,
                request_hash=request_hash,
            )
            await _record_successful_post(
                db,
                invited_by=invited_by,
                invite=replay,
                request_id=request_id,
                ip_address=ip_address,
                result="replayed",
            )
            await db.commit()
            return replay, replay_token
        except Exception:
            await db.rollback()
            raise

    try:
        try:
            idempotency_record = await privileged_operations_repository.create_idempotency_record(
                db,
                caller_user_id=invited_by,
                operation=_ISSUE_OPERATION,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                request_id=request_id,
            )
        except IntegrityError:
            await db.rollback()
            concurrent = await privileged_operations_repository.get_idempotency_record(
                db,
                caller_user_id=invited_by,
                operation=_ISSUE_OPERATION,
                idempotency_key=idempotency_key,
            )
            if concurrent is None:
                raise
            replay, replay_token = await _replay_completed_invite(
                db,
                record=concurrent,
                request_hash=request_hash,
            )
            await _record_successful_post(
                db,
                invited_by=invited_by,
                invite=replay,
                request_id=request_id,
                ip_address=ip_address,
                result="replayed",
            )
            await db.commit()
            return replay, replay_token

        result = await db.execute(
            select(StaffInvite).where(
                func.lower(StaffInvite.email) == normalized_email,
                StaffInvite.accepted_at.is_(None),
                StaffInvite.revoked_at.is_(None),
            )
        )
        active_invites = result.scalars().all()
        for existing in active_invites:
            expires_at = existing.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            inviter_exists = False
            if existing.invited_by is not None:
                inviter_exists = (
                    await db.scalar(
                        select(User.id).where(
                            User.id == existing.invited_by,
                            User.is_active.is_(True),
                            User.deleted_at.is_(None),
                        )
                    )
                    is not None
                )
            if (
                expires_at >= now
                and existing.role_name == "recruiter"
                and existing.role_id == recruiter_role.id
                and inviter_exists
            ):
                await privileged_operations_repository.complete_idempotency_record(
                    db,
                    idempotency_record,
                    response_status=201,
                    response_body={"invite_id": str(existing.id)},
                )
                await _record_successful_post(
                    db,
                    invited_by=invited_by,
                    invite=existing,
                    request_id=request_id,
                    ip_address=ip_address,
                    result="reused",
                )
                await db.commit()
                return existing, None
            existing.revoked_at = now
        await db.flush()

        plaintext_token = secrets.token_urlsafe(32)
        invite = StaffInvite(
            id=uuid4(),
            email=normalized_email,
            role_name="recruiter",
            role_id=recruiter_role.id,
            invited_by=invited_by,
            token=None,
            token_digest=hashlib.sha256(plaintext_token.encode("utf-8")).hexdigest(),
        )
        try:
            async with db.begin_nested():
                db.add(invite)
                await db.flush()
        except IntegrityError:
            winner_result = await db.execute(
                select(StaffInvite).where(
                    func.lower(StaffInvite.email) == normalized_email,
                    StaffInvite.accepted_at.is_(None),
                    StaffInvite.revoked_at.is_(None),
                    StaffInvite.role_name == "recruiter",
                    StaffInvite.role_id == recruiter_role.id,
                )
            )
            winner = winner_result.scalar_one_or_none()
            if winner is None:
                raise
            await privileged_operations_repository.complete_idempotency_record(
                db,
                idempotency_record,
                response_status=201,
                response_body={"invite_id": str(winner.id)},
            )
            await _record_successful_post(
                db,
                invited_by=invited_by,
                invite=winner,
                request_id=request_id,
                ip_address=ip_address,
                result="conflict_winner",
            )
            await db.commit()
            return winner, None

        await _record_successful_post(
            db,
            invited_by=invited_by,
            invite=invite,
            request_id=request_id,
            ip_address=ip_address,
            result="issued",
        )
        await privileged_operations_repository.complete_idempotency_record(
            db,
            idempotency_record,
            response_status=201,
            response_body={
                "invite_id": str(invite.id),
                "sealed_invite_token": seal_secret(plaintext_token),
            },
        )
        await db.commit()
        await db.refresh(invite)
        return invite, plaintext_token
    except Exception:
        await db.rollback()
        raise


async def clear_legacy_plaintext_tokens(
    db: AsyncSession,
    *,
    include_active: bool = False,
    now: datetime | None = None,
) -> int:
    """Clear legacy plaintext credentials without losing resolvability.

    The default mode clears accepted, expired, or revoked rows after the
    maintenance drain is acknowledged. Once restored-schema recovery closes,
    operators use ``include_active=True`` to backfill recovery rows and remove
    all remaining plaintext.
    """
    cutoff = now or datetime.now(UTC)
    result = await db.execute(
        select(StaffInvite).where(StaffInvite.token.is_not(None)).with_for_update()
    )
    cleared = 0
    for invite in result.scalars():
        plaintext_token = invite.token
        if plaintext_token is None:
            continue
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        eligible = (
            include_active
            or invite.accepted_at is not None
            or invite.revoked_at is not None
            or expires_at < cutoff
        )
        if not eligible:
            continue
        if invite.token_digest is None:
            invite.token_digest = hashlib.sha256(plaintext_token.encode("utf-8")).hexdigest()
        invite.token = None
        cleared += 1
    await db.commit()
    return cleared
