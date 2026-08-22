# Machine 1, Chunk 3 — Auth: `org_id` JWT Claim

## Depends on

Chunk `02`'s `users.org_id` column and `Organization` table must already exist (migration
`047_create_organizations_and_user_org_id` applied).

## Files to edit

- `backend/app/auth/router.py`
- `backend/app/auth/dependencies.py`

## Files to create

- None. This chunk is a pure retrofit of existing auth code.

## `backend/app/auth/router.py` — `create_access_token`

Current signature (verified, lines 70-94):

```python
def create_access_token(user_id: str, email: str) -> tuple[str, str]:
    ...
    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "exp": datetime.now(UTC) + expires_delta,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti
```

Change to:

```python
def create_access_token(user_id: str, email: str, org_id: str | None = None) -> tuple[str, str]:
    """
    Create JWT access token.

    Args:
        user_id: User UUID as string
        email: User email
        org_id: Tenant org UUID as string, or None for a user with no org
            (docs/adr/0018-tenancy-model.md). Additive claim — tokens issued before
            this change simply lack "org_id" in their payload, and callers that use
            payload.get("org_id") (not payload["org_id"]) keep working unchanged.

    Returns:
        Tuple of (token, jti)
    """
    settings = get_settings()
    jti = f"{user_id}:{uuid4().hex}"
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "email": email,
        "org_id": org_id,
        "jti": jti,
        "exp": datetime.now(UTC) + expires_delta,
        "iat": datetime.now(UTC),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti
```

**Find every call site of `create_access_token(` in `backend/app/auth/router.py`** (login,
signup, OAuth callback, token-refresh flows — there are multiple; search the file rather than
assuming a count) and update each to pass `org_id=str(user.org_id) if user.org_id else None`.
Do the same for the equivalent impersonation-token issuance in
`backend/app/modules/admin/` if it calls `create_access_token` directly (check
`impersonation`-related admin service/router files for a direct `jwt.encode` call or a call into
this function) — impersonation tokens should carry the **target** user's `org_id`, not the
admin's, consistent with how `sub` already carries the target user's id per the existing `imp`
claim convention (`backend/app/auth/dependencies.py` lines 82-87).

## `backend/app/auth/dependencies.py` — decode side and new dependency

In `get_current_user_from_cookie` (lines 38-136), after the existing `impersonated_by` extraction
block (lines 85-87), add:

```python
        org_id_claim: str | None = payload.get("org_id")
        if org_id_claim:
            request.state.org_id = UUID(org_id_claim)
        else:
            request.state.org_id = None
```

This mirrors the existing `request.state.user_id = user.id` pattern (line 134) — making `org_id`
available to ASGI-level code (middleware, chunk `04`'s rate-limit retrofit) without re-decoding
the JWT.

Add a new dependency, placed after `require_verified_user` (after line 159) and before the
`# Aliases` block:

```python
async def require_org_member(
    request: Request,
    user: User = Depends(require_verified_user),
) -> User:
    """
    Require the authenticated user to belong to an organization (tenant).

    Used by routes that only make sense for placement-agency recruiters, not
    direct candidates (org_id IS NULL). See docs/adr/0018-tenancy-model.md.

    Raises:
        HTTPException: 403 if user.org_id is None
    """
    if user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires membership in an organization",
        )
    return user
```

Add the alias, next to the existing `CurrentUser`/`VerifiedUser` aliases (lines 162-165):

```python
OrgScopedUser = Annotated[User, Depends(require_org_member)]
```

## Org bootstrap on signup — where to wire it

Locate the signup handler in `backend/app/auth/router.py` (the route that creates a new `User`
row). This chunk does **not** force every new signup into an org (direct-candidate signups keep
`org_id = None` per the ADR). Only wire org assignment for an **org-invite signup path** if one
already exists or is added by `machine-2-parallel-tracks/04-rbac-admin-platform.md`; if no
invite-based signup flow exists yet at implementation time, leave standard signup producing
`org_id = None` and note in the PR description that org-scoped signup/invite is deferred to
`04-rbac-admin-platform.md`. Do not invent an invite system in this chunk — that is out of scope
here.

## Do not touch

- Do not modify `backend/app/main.py` or `backend/app/dependencies/rate_limit.py` in this chunk
  — that is chunk `04`.
- Do not modify `backend/app/modules/orgs/` (created in chunk `02`) beyond importing from it if
  strictly needed for a type hint — no new methods added to that module here.
- Do not touch any non-auth router/service files.

## Verification

- Existing auth tests: locate and run the auth test module (likely
  `backend/tests/auth/` or `backend/tests/test_auth*.py` — check `backend/tests/` structure
  before assuming the path) after this change; all existing login/signup/refresh tests must
  still pass with tokens now carrying an additive `org_id: null` claim.
- Add at least one new test asserting: (a) a token for a user with `org_id = None` decodes with
  `org_id` claim `None` and `require_org_member` raises 403 for that user; (b) a token for a user
  with a real `org_id` decodes with that value and `require_org_member` returns the user without
  raising.
