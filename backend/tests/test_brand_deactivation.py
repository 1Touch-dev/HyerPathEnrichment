"""Brand deactivation/reactivation tests (post-tenancy-features/
03-org-offboarding-and-deletion.md).

Covers: `backend/app/modules/brands/deactivation_router.py` +
`deactivation_service.py` (deactivate/reactivate flip `Brand.is_active` and
write an `admin_audit_logs` row via `record_admin_action`), 404 handling for
unknown brands, and the `("brands", "delete")` permission gate seeded by
`057_seed_brands_delete_permission.py` (granted to `team_owner`, NOT granted
to `recruiter` — see that migration's own docstring for why the grant was a
follow-up fix after an initial review found the permission missing).

Item 1 below is release-blocking per the task spec: a Brand is
presentation-only (docs/adr/0019-tenancy-model.md) and deactivating one must
have zero cascading effect on any other domain table, even when a candidate's
`signup_brand_id` points at the brand being deactivated.

Post-HTTP-call verification queries use a fresh `SessionLocal()` session
(matching test_admin_audit.py's convention), not the `db_session` fixture's
session — the HTTP call runs the real endpoint against its own session (via
`get_db_session` dependency injection), so re-querying with a fresh session
avoids ever touching a stale/expired identity-mapped object from the fixture
session (e.g. `superuser`, `brand`) after the commit.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.admin.models import AdminAuditLog, Role
from app.modules.brands.models import Brand
from app.modules.documents.models import CandidateDocument
from tests.conftest import SQLITE_ROLE_UUID_DASH_BUG_REASON, USING_POSTGRES

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — matches the
# convention in test_admin_rbac.py / test_admin_audit.py. pyproject.toml's
# asyncio_mode = "auto" already runs `async def` tests without the marker.


async def _make_brand(db_session, **overrides) -> Brand:
    defaults = {
        "id": uuid4(),
        "name": f"Test Brand {uuid4().hex[:8]}",
        "slug": f"test-brand-{uuid4().hex[:10]}",
        "is_active": True,
    }
    defaults.update(overrides)
    brand = Brand(**defaults)
    db_session.add(brand)
    await db_session.commit()
    await db_session.refresh(brand)
    return brand


async def _make_user_with_role(db_session, role_name: str, /, **overrides):
    """Persist a user assigned the seeded role named `role_name` (e.g.
    `team_owner`, `recruiter` — both seeded by 047_seed_system_roles.py)."""
    from tests.conftest import _make_persisted_user

    result = await db_session.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one()
    return await _make_persisted_user(db_session, role_id=role.id, **overrides)


class TestDeactivateFlipsIsActiveAndAudits:
    async def test_deactivate_flips_is_active_false_and_writes_audit_row(
        self, client, superuser, auth_headers, db_session
    ):
        from app.database.session import SessionLocal

        brand = await _make_brand(db_session)
        brand_id = brand.id
        superuser_id = superuser.id
        assert brand.is_active is True

        response = client.post(
            f"/api/admin/brands/{brand_id}/deactivate",
            json={"reason": "no longer operating"},
            headers=auth_headers(superuser_id),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["is_active"] is False

        async with SessionLocal() as verify_session:
            result = await verify_session.execute(select(Brand).where(Brand.id == brand_id))
            refreshed = result.scalar_one()
            assert refreshed.is_active is False

            audit_result = await verify_session.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_type == "brand",
                    AdminAuditLog.action == "brand.deactivate",
                    AdminAuditLog.target_id == str(brand_id),
                )
            )
            audit_rows = audit_result.scalars().all()
            assert len(audit_rows) == 1
            assert audit_rows[0].actor_user_id == superuser_id
            assert audit_rows[0].before == {"is_active": True}
            assert audit_rows[0].after == {"is_active": False, "reason": "no longer operating"}

    async def test_reactivate_flips_is_active_true_and_writes_own_audit_row(
        self, client, superuser, auth_headers, db_session
    ):
        from app.database.session import SessionLocal

        brand = await _make_brand(db_session, is_active=False)
        brand_id = brand.id
        superuser_id = superuser.id

        response = client.post(
            f"/api/admin/brands/{brand_id}/reactivate",
            headers=auth_headers(superuser_id),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["is_active"] is True

        async with SessionLocal() as verify_session:
            result = await verify_session.execute(select(Brand).where(Brand.id == brand_id))
            refreshed = result.scalar_one()
            assert refreshed.is_active is True

            audit_result = await verify_session.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_type == "brand",
                    AdminAuditLog.action == "brand.reactivate",
                    AdminAuditLog.target_id == str(brand_id),
                )
            )
            audit_rows = audit_result.scalars().all()
            assert len(audit_rows) == 1
            assert audit_rows[0].before == {"is_active": False}
            assert audit_rows[0].after == {"is_active": True}

    async def test_deactivate_then_reactivate_writes_two_distinct_audit_rows(
        self, client, superuser, auth_headers, db_session
    ):
        """Sanity check that the two actions log independently (distinct
        `action` values), not as a single toggle entry."""
        from app.database.session import SessionLocal

        brand = await _make_brand(db_session)
        brand_id = brand.id
        superuser_id = superuser.id

        deactivate_response = client.post(
            f"/api/admin/brands/{brand_id}/deactivate",
            json={},
            headers=auth_headers(superuser_id),
        )
        assert deactivate_response.status_code == 200

        reactivate_response = client.post(
            f"/api/admin/brands/{brand_id}/reactivate",
            headers=auth_headers(superuser_id),
        )
        assert reactivate_response.status_code == 200

        async with SessionLocal() as verify_session:
            audit_result = await verify_session.execute(
                select(AdminAuditLog.action)
                .where(
                    AdminAuditLog.target_type == "brand", AdminAuditLog.target_id == str(brand_id)
                )
                .order_by(AdminAuditLog.created_at)
            )
            actions = [row[0] for row in audit_result.all()]
            assert actions == ["brand.deactivate", "brand.reactivate"]


class TestNotFound:
    async def test_deactivate_unknown_brand_id_returns_404(self, client, superuser, auth_headers):
        response = client.post(
            f"/api/admin/brands/{uuid4()}/deactivate",
            json={},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404

    async def test_reactivate_unknown_brand_id_returns_404(self, client, superuser, auth_headers):
        response = client.post(
            f"/api/admin/brands/{uuid4()}/reactivate",
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404

    async def test_404_on_unknown_brand_does_not_write_audit_row(
        self, client, superuser, auth_headers
    ):
        """404s must be raised before any flip/audit write is attempted — the
        service looks the brand up first and raises immediately on a miss."""
        from app.database.session import SessionLocal

        unknown_id = uuid4()
        response = client.post(
            f"/api/admin/brands/{unknown_id}/deactivate",
            json={},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404

        async with SessionLocal() as verify_session:
            audit_result = await verify_session.execute(
                select(AdminAuditLog).where(AdminAuditLog.target_id == str(unknown_id))
            )
            assert audit_result.scalars().all() == []


class TestPermissionGating:
    """`("brands", "delete")` is seeded by 057_seed_brands_delete_permission.py
    and granted only to `team_owner` (not `recruiter`, which has `brands:read`
    but no `brands:delete` — see 056_seed_brands_permissions.py). These tests
    exercise the real HTTP-level `require_permission("brands", "delete")`
    dependency chain end-to-end, not just the migration's row-level grant.

    xfail'd (strict) on SQLite per SQLITE_ROLE_UUID_DASH_BUG_REASON — role-based
    (non-superuser) permission checks are known-broken there because
    migration-seeded role UUIDs are dashed while ORM-written `users.role_id`
    values are undashed on SQLite; verified to pass for real on Postgres.
    """

    @pytest.mark.xfail(
        condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
    )
    async def test_team_owner_can_deactivate_brand(self, client, auth_headers, db_session):
        brand = await _make_brand(db_session)
        team_owner_user = await _make_user_with_role(db_session, "team_owner")

        response = client.post(
            f"/api/admin/brands/{brand.id}/deactivate",
            json={},
            headers=auth_headers(team_owner_user.id),
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False

    @pytest.mark.xfail(
        condition=not USING_POSTGRES, reason=SQLITE_ROLE_UUID_DASH_BUG_REASON, strict=True
    )
    async def test_team_owner_can_reactivate_brand(self, client, auth_headers, db_session):
        brand = await _make_brand(db_session, is_active=False)
        team_owner_user = await _make_user_with_role(db_session, "team_owner")

        response = client.post(
            f"/api/admin/brands/{brand.id}/reactivate",
            headers=auth_headers(team_owner_user.id),
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is True

    async def test_role_without_brands_delete_gets_403_on_deactivate(
        self, client, auth_headers, db_session
    ):
        """`recruiter` has `brands:read` (056_seed_brands_permissions.py) but
        not `brands:delete` — must be denied. Unlike the team_owner tests
        above, this is a straightforward deny-path check: `user_has_permission`
        returning False for a real (non-None) `role_id` doesn't depend on the
        role-based lookup actually finding a matching row, so it is not subject
        to the SQLite dashed/undashed UUID join bug the same way an allow-path
        assertion would be. It's exercised here as a plain (non-xfail) test.
        """
        brand = await _make_brand(db_session)
        recruiter_user = await _make_user_with_role(db_session, "recruiter")

        response = client.post(
            f"/api/admin/brands/{brand.id}/deactivate",
            json={},
            headers=auth_headers(recruiter_user.id),
        )
        assert response.status_code == 403

    async def test_role_without_brands_delete_gets_403_on_reactivate(
        self, client, auth_headers, db_session
    ):
        brand = await _make_brand(db_session, is_active=False)
        recruiter_user = await _make_user_with_role(db_session, "recruiter")

        response = client.post(
            f"/api/admin/brands/{brand.id}/reactivate",
            headers=auth_headers(recruiter_user.id),
        )
        assert response.status_code == 403

    async def test_user_with_no_role_gets_403(self, client, auth_headers, regular_user):
        """`regular_user` has `role_id is None` — `user_has_permission` denies
        without a DB lookup, so this path is unaffected by the SQLite bug."""
        response = client.post(
            f"/api/admin/brands/{uuid4()}/deactivate",
            json={},
            headers=auth_headers(regular_user.id),
        )
        assert response.status_code == 403  # permission check runs before the 404 lookup


class TestDeactivationHasZeroCascadingEffect:
    """RELEASE-BLOCKING: deactivating a brand must change ZERO rows in any
    other domain table. A Brand is presentation-only
    (docs/adr/0019-tenancy-model.md) — it is never a data-isolation boundary,
    so flipping `Brand.is_active` must not touch candidates, their documents,
    or anything else, even when a candidate's `signup_brand_id` points
    directly at the brand being deactivated.
    """

    async def test_deactivate_does_not_touch_other_tables(
        self, client, superuser, auth_headers, db_session
    ):
        from app.auth.models import User
        from app.database.session import SessionLocal

        brand = await _make_brand(db_session)
        brand_id = brand.id
        brand_name = brand.name
        brand_slug = brand.slug
        superuser_id = superuser.id

        candidate = User(
            id=uuid4(),
            email=f"candidate-{uuid4().hex[:10]}@example.com",
            first_name="Cand",
            last_name="Idate",
            is_active=True,
            is_verified=True,
            signup_brand_id=brand_id,
        )
        db_session.add(candidate)
        await db_session.commit()
        await db_session.refresh(candidate)

        document = CandidateDocument(
            id=uuid4(),
            user_id=candidate.id,
            document_type="cv",
            original_filename="resume.pdf",
            storage_path="/tmp/resume.pdf",
            file_hash="deadbeef" * 8,
            file_size_bytes=1024,
            processing_status="completed",
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)
        await db_session.refresh(candidate)

        candidate_id = candidate.id
        document_id = document.id

        # Snapshot every field of the rows that touch the brand-under-test,
        # other than Brand.is_active itself, before deactivation.
        pre_candidate_snapshot = {
            "id": candidate.id,
            "email": candidate.email,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "is_active": candidate.is_active,
            "is_verified": candidate.is_verified,
            "is_superuser": candidate.is_superuser,
            "role_id": candidate.role_id,
            "signup_brand_id": candidate.signup_brand_id,
            "deleted_at": candidate.deleted_at,
        }
        pre_document_snapshot = {
            "id": document.id,
            "user_id": document.user_id,
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "storage_path": document.storage_path,
            "mime_type": document.mime_type,
            "file_hash": document.file_hash,
            "file_size_bytes": document.file_size_bytes,
            "raw_text": document.raw_text,
            "extracted_data": document.extracted_data,
            "processing_status": document.processing_status,
            "deleted_at": document.deleted_at,
        }

        pre_user_count = (await db_session.execute(select(User.id))).scalars().all()
        pre_document_count = (
            (await db_session.execute(select(CandidateDocument.id))).scalars().all()
        )
        pre_audit_count = len((await db_session.execute(select(AdminAuditLog.id))).scalars().all())

        response = client.post(
            f"/api/admin/brands/{brand_id}/deactivate",
            json={"reason": "cascade check"},
            headers=auth_headers(superuser_id),
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False

        # Verify against a fresh session (not `db_session`) — see module
        # docstring for why: the HTTP call committed via its own session, and
        # this avoids ever touching a stale/expired object from the fixture
        # session.
        async with SessionLocal() as verify_session:
            # Only Brand.is_active should have changed.
            brand_result = await verify_session.execute(select(Brand).where(Brand.id == brand_id))
            refreshed_brand = brand_result.scalar_one()
            assert refreshed_brand.is_active is False
            assert refreshed_brand.name == brand_name
            assert refreshed_brand.slug == brand_slug

            # Candidate row: byte-for-byte unchanged (including
            # signup_brand_id, which still points at the now-deactivated brand).
            candidate_result = await verify_session.execute(
                select(User).where(User.id == candidate_id)
            )
            refreshed_candidate = candidate_result.scalar_one()
            post_candidate_snapshot = {
                "id": refreshed_candidate.id,
                "email": refreshed_candidate.email,
                "first_name": refreshed_candidate.first_name,
                "last_name": refreshed_candidate.last_name,
                "is_active": refreshed_candidate.is_active,
                "is_verified": refreshed_candidate.is_verified,
                "is_superuser": refreshed_candidate.is_superuser,
                "role_id": refreshed_candidate.role_id,
                "signup_brand_id": refreshed_candidate.signup_brand_id,
                "deleted_at": refreshed_candidate.deleted_at,
            }
            assert post_candidate_snapshot == pre_candidate_snapshot

            # Document row: byte-for-byte unchanged.
            document_result = await verify_session.execute(
                select(CandidateDocument).where(CandidateDocument.id == document_id)
            )
            refreshed_document = document_result.scalar_one()
            post_document_snapshot = {
                "id": refreshed_document.id,
                "user_id": refreshed_document.user_id,
                "document_type": refreshed_document.document_type,
                "original_filename": refreshed_document.original_filename,
                "storage_path": refreshed_document.storage_path,
                "mime_type": refreshed_document.mime_type,
                "file_hash": refreshed_document.file_hash,
                "file_size_bytes": refreshed_document.file_size_bytes,
                "raw_text": refreshed_document.raw_text,
                "extracted_data": refreshed_document.extracted_data,
                "processing_status": refreshed_document.processing_status,
                "deleted_at": refreshed_document.deleted_at,
            }
            assert post_document_snapshot == pre_document_snapshot

            # Row counts in users/candidate_documents tables are unchanged
            # (no cascading delete, no row created/removed as a side effect).
            post_user_count = (await verify_session.execute(select(User.id))).scalars().all()
            post_document_count = (
                (await verify_session.execute(select(CandidateDocument.id))).scalars().all()
            )
            assert set(post_user_count) == set(pre_user_count)
            assert set(post_document_count) == set(pre_document_count)

            # The audit log is the one table expected to change. At minimum,
            # the explicit target_type="brand"/action="brand.deactivate" row
            # from TestDeactivateFlipsIsActiveAndAudits must be new here too.
            # Not asserted as an exact "+1": AdminAuditFallbackMiddleware
            # (app/modules/admin/audit.py) also unconditionally writes a
            # second, generic "unclassified" fallback row for this same
            # request even though the explicit call above already ran — see
            # this module's final report for why (pre-existing contextvar-
            # propagation limitation of Starlette's BaseHTTPMiddleware,
            # shared admin-audit infra, not owned by the BD track). What
            # matters for THIS release-blocking check is that no OTHER
            # domain table gained/lost rows, which is asserted above.
            post_audit_count = len(
                (await verify_session.execute(select(AdminAuditLog.id))).scalars().all()
            )
            assert post_audit_count > pre_audit_count

            new_brand_audit_result = await verify_session.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_type == "brand",
                    AdminAuditLog.action == "brand.deactivate",
                    AdminAuditLog.target_id == str(brand_id),
                )
            )
            assert len(new_brand_audit_result.scalars().all()) == 1
