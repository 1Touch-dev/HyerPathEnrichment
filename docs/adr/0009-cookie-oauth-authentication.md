# ADR 0009: Cookie-based OAuth authentication with FastAPI-Users

**Status:** Accepted

**Date:** 2026-07-31

## Context

The application needs user authentication to:

- Associate enrichment jobs with users
- Control access to job results
- Track usage and provide personalized experiences
- Support compliance features (DSAR/opt-out require auth)

Requirements:

- Cookie-based sessions (HttpOnly, Secure, SameSite)
- Social login (Google OAuth)
- Email/password registration with verification
- JWT access tokens (15min) + refresh tokens (7d) with rotation
- Token revocation on logout
- Scalable to 10,000+ concurrent users
- Email verification flow before account activation
- Soft delete for account deletion
- PostgreSQL for persistence, Redis for blacklist/cache

## Decision

Use **FastAPI-Users** with cookie transport, JWT strategy, and custom extensions — chosen over pure stateless JWT and over database-backed sessions (see Alternatives Considered below) because it gives us cookie-based sessions, OAuth, and Redis-backed logout revocation without a second backend stack.

## Architecture

```
┌─────────────┐
│  Next.js    │  ← BFF API routes proxy auth requests
│  Frontend   │  ← Stores HttpOnly cookies automatically
└──────┬──────┘
       │
       ↓ HTTPS (cookies)
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend                                    │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │ Auth Module                                 │  │
│  │                                             │  │
│  │  • FastAPI-Users (cookie transport + JWT)  │  │
│  │  • Custom password hashing (bcrypt)        │  │
│  │  • Email verification service              │  │
│  │  • Token blacklist (Redis + PostgreSQL)    │  │
│  │  • Audit logging                           │  │
│  │  • Rate limiting (slowapi)                 │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────┐     ┌────────────┐              │
│  │ PostgreSQL   │     │   Redis    │              │
│  │              │     │            │              │
│  │ • users      │     │ • blacklist│              │
│  │ • oauth_acct │     │ • rate lmt │              │
│  │ • tokens     │     │            │              │
│  └──────────────┘     └────────────┘              │
└─────────────────────────────────────────────────────┘
```

## Key Components

### 1. User Model

- UUID primary key
- Email (unique, indexed, NOT NULL, validated with regex)
- Bcrypt password hash
- `first_name`, `last_name` for profile
- `is_verified` (email verification required)
- `deleted_at` (soft delete timestamp)
- OAuth provider fields

### 2. Token Strategy

**Access Token (JWT in HttpOnly cookie):**
- 15-minute expiry
- Contains user ID, email, JTI (unique token ID)
- Checked against Redis blacklist on every request
- User activity and database-backed RBAC are resolved on every request; role
  and permission changes therefore take effect on the next request without
  waiting for token expiry.

**Impersonation extension:**
- Impersonation tokens retain `sub` (effective candidate), `jti` (session
  token), and `imp` (real actor).
- Every impersonated request validates the JTI against
  `impersonation_sessions`, including active/unexpired/unrevoked state, the
  real actor's active state, and the real actor's current permission.
- Only roleless, non-superuser candidates may be targets. Scope is
  `view_only`; all mutations except ending impersonation are denied.
- Revocation or session end invalidates the impersonation JTI immediately.
  Ordinary authenticated requests do not query this table.

**Refresh Token:**
- 7-day expiry
- Stored in PostgreSQL with rotation tracking
- One-time use (marked `used=true` after rotation)
- Parent-child chain for security audit

**Token Blacklist (Dual Store):**
- **Redis**: Fast lookup (`is_token_logged_out(jti)`)
- **PostgreSQL**: Durable audit trail + sync on restart
- TTL matches token expiry (auto-cleanup)

### 3. Email Verification Flow

1. User registers → `is_verified=false`
2. Backend generates verification token (24h TTL)
3. SendGrid sends email with verification link
4. User clicks link → Frontend auto-submits verification
5. Backend validates token → `is_verified=true`
6. Redirect to home page

Unverified users: Allowed only opt-out API (public). All other endpoints require `is_verified=true`.

### 4. Logout & Account Deletion

**Logout:**
- Add token JTI to blacklist (Redis + PostgreSQL)
- Clear HttpOnly cookies
- Token remains blacklisted until natural expiry

**Account Deletion (Sign Out):**
- Same as logout (blacklist token)
- Set `user.deleted_at = now()`
- Login blocked for deleted accounts

### 5. Security Features

- **Rate limiting**: `slowapi` on `/auth/login`, `/auth/register` (5 req/min)
- **Audit logging**: All auth events → `auth_audit_logs` table
- **Permission freshness**: RBAC grants are database-resolved per request;
  frontend identity caches are advisory and refresh after role changes or an
  authorization failure.
- **Security headers**: CSP, HSTS, X-Frame-Options
- **CORS**: `credentials=true` for cookies, restrict origins
- **Refresh token rotation**: Each refresh invalidates old token

## Alternatives Considered

### Option A: Pure JWT (stateless)

**Pros:**
- No server-side session storage
- Horizontal scaling trivial

**Cons:**
- ❌ Cannot revoke tokens on logout (user reported this as critical flaw)
- ❌ Stolen token valid until expiry
- ❌ No real-time access control changes

**Rejected:** Logout revocation is a requirement.

### Option B: Database Sessions (no JWT)

**Pros:**
- Full control over session lifecycle
- Immediate revocation

**Cons:**
- Database hit on every request (high load at 10K users)
- No offline token validation
- Requires sticky sessions or session replication

**Rejected:** Does not scale to 10K concurrent users without Redis anyway, and JWT + Redis blacklist is more performant.

### Option C: Passport.js + Express (Node.js)

**Pros:**
- Familiar to user (mentioned Passport.js)
- Rich ecosystem

**Cons:**
- Adds Node.js backend (duplicate stack)
- Team expertise is Python/FastAPI
- No benefit over FastAPI-Users for this use case

**Rejected:** Stay within Python ecosystem.

## Chosen: FastAPI-Users + Cookie Transport + Blacklist

**Pros:**
- ✅ Cookie-based (HttpOnly, Secure, SameSite)
- ✅ Built-in OAuth (Google)
- ✅ JWT with revocation via Redis blacklist
- ✅ Scales to 10K+ users (Redis is fast)
- ✅ Familiar FastAPI patterns (dependencies, routers)
- ✅ Extensible (custom password hashing, verification emails)

**Cons:**
- Requires Redis for blacklist (acceptable, already in stack)
- Slightly more complex than pure stateless JWT (acceptable tradeoff)

## Tradeoffs

| Aspect | Tradeoff |
|--------|----------|
| **Security vs Complexity** | Blacklist adds complexity but solves logout revocation |
| **Scalability** | Redis required for 10K users; PostgreSQL alone would bottleneck |
| **Developer Experience** | FastAPI-Users abstracts boilerplate; custom extensions needed for verification |
| **Operational** | Redis must be available; adds dependency but provides caching benefits too |

## Scalability Notes

**10,000 concurrent users:**

- **API instances**: 4-6 instances (2.5K users each)
- **PostgreSQL**: Connection pool 20-30 per instance; read replicas for `/users/me`
- **Redis**: Single instance handles 100K ops/sec (sufficient)
- **Token blacklist size**: ~1-2 MB (10K entries × 100 bytes)

**Performance:**
- Cookie auth: ~1ms (Redis lookup)
- Login: ~200ms (bcrypt + DB write)
- Refresh: ~50ms (DB update + Redis write)

## Implementation Checklist

- [x] Define User, OAuthAccount, RefreshToken, TokenBlacklist, LoggedOutToken models
- [x] Add `user_id` FK to `jobs` table (nullable, indexed)
- [x] Alembic migration for auth tables
- [ ] Install `fastapi-users`, `httpx-oauth`, `slowapi`, `passlib[bcrypt]`
- [ ] Configure `CookieTransport`, `JWTStrategy`, `GoogleOAuth2`
- [ ] Implement `hash_password`, `verify_password`, `needs_rehash`
- [ ] Implement email verification service (SendGrid integration)
- [ ] Implement dual blacklist (Redis + PostgreSQL)
- [ ] Add rate limiting middleware
- [ ] Add security headers middleware
- [ ] Update `main.py` with auth routers and CORS
- [ ] Frontend: AuthProvider context, BFF routes, auth pages
- [ ] E2E tests: register → verify → login → job → refresh → logout

## References

- FastAPI-Users docs: https://fastapi-users.github.io/fastapi-users/
- ADR 0005: Redis cache pattern (applied here for blacklist)
- ADR 0002: PostgreSQL for durable storage
- OAuth 2.0 RFC: https://tools.ietf.org/html/rfc6749
- JWT RFC: https://tools.ietf.org/html/rfc7519

## Notes

- Email verification token expiry: 24 hours
- Access token expiry: 15 minutes
- Refresh token expiry: 7 days
- Bcrypt cost factor: 12 (production)
- Rate limit: 5 login attempts per minute per IP
- Frontend uses BFF pattern (Next.js API routes) to avoid CORS preflight overhead
