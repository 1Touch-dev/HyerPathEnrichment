# Authentication Guide

Complete guide to the Hyrepath Enrichment authentication system.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup](#setup)
4. [User Flows](#user-flows)
5. [API Endpoints](#api-endpoints)
6. [Security Features](#security-features)
7. [Troubleshooting](#troubleshooting)
8. [Development](#development)
9. [Production Deployment](#production-deployment)

---

## Overview

Hyrepath Enrichment uses **cookie-based authentication** with JWT tokens for secure, scalable user management.

### Key Features

- **Cookie-based sessions** (HttpOnly, Secure, SameSite)
- **Google OAuth2** integration
- **Email/password** registration with verification
- **Email verification** (24-hour token expiry)
- **JWT access tokens** (15-minute expiry)
- **Refresh token rotation** (7-day expiry)
- **Token blacklisting** (logout revocation)
- **Soft delete** for account deletion
- **Rate limiting** on auth endpoints
- **Audit logging** for all auth events
- **Scalable** to 10,000+ concurrent users

### Access Control Model

**PUBLIC (no auth required):**
- `/api/opt-out` - Compliance endpoint
- `/health`, `/ready` - Health checks
- `/metrics` - Prometheus metrics (if exposed)

**AUTHENTICATED (verified not required):**
- `/auth/me` - Current user info, role, and permission pairs
- `/auth/resend-verification` - Resend verification email
- `/auth/logout` - End session
- `/auth/delete-account` - Sign out (soft delete)

**AUTHENTICATED + VERIFIED:**
- `/api/dsar` - Data subject access request
- `/api/jobs/*` - Job management
- Candidate product endpoints

**STAFF (verified and either assigned a role or superuser):**
- `/enrich/*` - All enrichment endpoints
- Staff API modules mounted behind the staff boundary
- Frontend OSINT (`/osint/*`) and Desk (`/desk/*`) product doors

---

## Architecture

### Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  User Browser                                                │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ HTTPS (HttpOnly cookies)
┌──────────────────────────────────────────────────────────────┐
│  Next.js Frontend (BFF Pattern)                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Routes (BFF Layer)                               │  │
│  │ • /api/auth/login                                    │  │
│  │ • /api/auth/register                                 │  │
│  │ • /api/auth/logout                                   │  │
│  │ • /api/auth/verify-email                             │  │
│  │ • /api/auth/resend-verification                      │  │
│  │ • /api/auth/delete-account                           │  │
│  │ • /api/auth/me                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Auth Components                                       │  │
│  │ • AuthProvider (context)                             │  │
│  │ • AuthGuard (route protection)                       │  │
│  │ • VerificationBanner (unverified users)              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ HTTP (forwards cookies)
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend                                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Auth Module (app/auth/)                              │  │
│  │ • FastAPI-Users (cookie transport + JWT strategy)    │  │
│  │ • Password hashing (bcrypt, 12 rounds)               │  │
│  │ • Email verification service                         │  │
│  │ • Token blacklist (Redis + PostgreSQL)               │  │
│  │ • Audit logging                                      │  │
│  │ • Rate limiting (slowapi)                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────┐     ┌──────────────────────────────┐  │
│  │ PostgreSQL      │     │ Redis                         │  │
│  │                 │     │                               │  │
│  │ • users         │     │ • blacklist:{jti} (fast)      │  │
│  │ • oauth_accts   │     │ • rate_limit:{ip}            │  │
│  │ • refresh_tokens│     │                               │  │
│  │ • email_verif   │     │                               │  │
│  │ • logged_out    │     │                               │  │
│  │ • audit_logs    │     │                               │  │
│  └─────────────────┘     └──────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Email Worker (SendGrid)                              │  │
│  │ • Verification emails                                 │  │
│  │ • Welcome emails                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                     │
                     ↓ OAuth redirect
┌──────────────────────────────────────────────────────────────┐
│  Google OAuth 2.0                                            │
│  • User consent                                              │
│  • Profile data (email, name, avatar)                        │
└──────────────────────────────────────────────────────────────┘
```

### Token Strategy

**Access Token (JWT in HttpOnly cookie):**
- Lifetime: 15 minutes
- Contains: `user_id`, `email`, `jti` (unique token ID)
- Checked against Redis blacklist on every request (~1ms)
- Cannot be accessed by JavaScript (XSS protection)

**Refresh Token:**
- Lifetime: 7 days
- Stored in PostgreSQL with rotation tracking
- One-time use (marked `used=true` after rotation)
- Parent-child chain for security audit
- Automatic rotation near expiry

**Token Blacklist (Dual Store):**
- **Redis**: Fast lookup (`<1ms`), auto-expires with TTL
- **PostgreSQL**: Durable audit trail, synced on startup
- Tokens added on logout and account deletion
- Security alerts for reuse after logout

---

## Setup

### Prerequisites

1. **PostgreSQL** database
2. **Redis** instance
3. **SendGrid** account (for email verification)
4. **Google OAuth** credentials (optional, for social login)

### Backend Configuration

Create `backend/.env` with:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hyrepath

# Redis
REDIS_URL=redis://localhost:6379/0

# Authentication
SECRET_KEY=your-256-bit-secret-key-here  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Cookies
COOKIE_SECURE=false  # Set to true in production (HTTPS only)
COOKIE_DOMAIN=  # Leave empty for localhost; set to .yourdomain.com in production

# Google OAuth (optional)
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REDIRECT_URL=http://localhost:3000/callback/google

# Email (SendGrid)
SENDGRID_API_KEY=SG.your-api-key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_FROM_NAME=Hyrepath Enrichment

# Frontend URL
FRONTEND_URL=http://localhost:3000

# Rate Limiting
MAX_LOGIN_ATTEMPTS_PER_MINUTE=5
MAX_REGISTER_ATTEMPTS_PER_HOUR=3
MAX_VERIFICATION_RESEND_MINUTES=5
```

### Frontend Configuration

Create `frontend/.env.local` with:

```bash
BACKEND_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Generate Secret Key

```bash
# Generate a secure SECRET_KEY
openssl rand -hex 32
```

### Database Migration

Run Alembic migrations to create auth tables:

```bash
cd backend
alembic upgrade head
```

This creates:
- `users` table (with UUID PKs, email unique/indexed)
- `oauth_accounts` table
- `refresh_tokens` table
- `email_verification_tokens` table
- `logged_out_tokens` table
- `auth_audit_logs` table
- Adds `user_id` FK to `jobs` table

### Google OAuth Setup

See [Google OAuth Setup Guide](./google-oauth-setup.md) for detailed instructions.

---

## User Flows

### Registration Flow (Email/Password)

1. User fills registration form with:
   - Email (validated with regex)
   - Password (min 8 characters)
   - First name
   - Last name

2. Backend validates inputs:
   - Email format check
   - Password strength check
   - Duplicate email check

3. Backend creates user:
   - Hashes password with bcrypt (12 rounds)
   - Sets `is_verified=false`
   - Generates verification token (24h expiry)
   - Queues verification email via SendGrid

4. User redirected to `/verify-email-pending`:
   - Shows "Check your email" message
   - "Open Email App" button
   - "Resend verification" option

5. User clicks verification link in email:
   - Frontend redirects to `/verify-email?token=...`
   - Backend validates token
   - Sets `user.is_verified=true`
   - Redirects to home page

6. User can now log in and access all features

### Login Flow

1. User submits email + password
2. Backend validates:
   - Email exists
   - Account not deleted (`deleted_at IS NULL`)
   - Password matches (bcrypt verify)
3. Backend generates tokens:
   - Access token (JWT, 15min)
   - Refresh token (7d)
4. Backend sets HttpOnly cookies:
   - `access_token` cookie
   - `refresh_token` cookie
5. Frontend receives user data
6. User is redirected to the role-appropriate product home

### Google OAuth Flow

1. User clicks "Sign in with Google"
2. Frontend redirects to `/auth/google/authorize`
3. Backend redirects to Google OAuth consent screen
4. User authorizes app
5. Google redirects to `/auth/google/callback`
6. Backend:
   - Exchanges code for OAuth tokens
   - Creates or links user account
   - Sets `is_verified=true` (OAuth emails pre-verified)
   - Issues access + refresh tokens
7. User redirected to home page

### Email Verification Flow

**For unverified users:**

1. Unverified user sees yellow banner at top:
   - "Please verify your email to access all features"
   - "Resend email" button

2. User clicks "Resend email":
   - Backend checks rate limit (5min cooldown)
   - Generates new verification token
   - Queues email
   - Shows success message

3. User clicks verification link:
   - Token validated (24h expiry)
   - `is_verified` set to `true`
   - Banner disappears
   - Full feature access granted

**Access restrictions:**
- ❌ Unverified: Cannot access enrichment or DSAR
- ✅ Unverified: Can access opt-out (public)
- ✅ Verified: Can access all features

### Logout Flow

1. User clicks "Logout" in settings
2. Frontend calls `/api/auth/logout`
3. Backend:
   - Extracts token JTI from cookie
   - Adds to blacklist (Redis + PostgreSQL)
   - Logs logout event in audit table
4. Backend clears cookies
5. User redirected to login page

**Security:** Token reuse after logout triggers security alert.

### Account Deletion Flow (Sign Out)

1. User clicks "Delete Account" in settings (Danger Zone)
2. Frontend shows confirmation dialog:
   - Warning: "This cannot be undone"
   - Requires explicit confirmation

3. User confirms deletion

4. Backend:
   - Blacklists current token (same as logout)
   - Sets `user.deleted_at = now()`
   - Logs account deletion event
   - Clears cookies

5. User redirected to login page with message:
   - "Account deleted. Contact support to restore."

**Soft delete:** User data retained for compliance but account marked deleted. Login blocked unless admin restores (`deleted_at = NULL`).

### Token Refresh Flow (Automatic)

1. Access token nears expiry (~13 minutes)
2. Frontend automatically calls `/api/auth/refresh`
3. Backend:
   - Validates refresh token
   - Checks not already used (security)
   - Marks old refresh token `used=true`
   - Issues new access + refresh tokens
4. New tokens set in cookies
5. User session continues seamlessly

**Security:** Refresh token reuse (already marked `used`) triggers security response (revoke all user tokens).

---

## API Endpoints

### Public Endpoints (No auth)

#### POST /auth/register
Register new user with email/password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:** 201 Created
```json
{
  "success": true,
  "message": "User registered. Please check your email for verification."
}
```

**Validations:**
- Email format (regex)
- Password min 8 characters
- Email unique (not already registered)

**Rate limit:** 3 requests/hour per IP

---

#### POST /auth/login
Login with email/password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** 200 OK (sets cookies)
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_verified": true,
    "role_id": null,
    "role_name": null,
    "permissions": []
  }
}
```

**Errors:**
- 401: Invalid credentials
- 403: Account deleted

**Rate limit:** 5 requests/minute per IP

---

#### POST /auth/verify-email
Verify email with token from email.

**Request:**
```json
{
  "token": "verification-token-from-email"
}
```

**Response:** 200 OK
```json
{
  "success": true,
  "message": "Email verified successfully"
}
```

**Errors:**
- 400: Invalid or expired token

---

### Authenticated Endpoints (Requires login)

#### GET /auth/me
Get the current user identity used for product-door routing.

**Response:** 200 OK
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_verified": true,
    "oauth_provider": null,
    "role_id": "uuid-or-null",
    "role_name": "recruiter",
    "permissions": [
      {
        "resource": "brands",
        "action": "read"
      }
    ]
  }
}
```

---

#### POST /auth/resend-verification
Resend verification email (unverified users only).

**Response:** 200 OK
```json
{
  "success": true,
  "message": "Verification email sent"
}
```

**Errors:**
- 400: Email already verified
- 429: Rate limit (wait 5 minutes)

**Rate limit:** 1 request per 5 minutes per user

---

#### POST /auth/logout
End current session (blacklist token).

**Response:** 200 OK
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

**Effect:**
- Token added to blacklist
- Cookies cleared
- Audit log created

---

#### POST /auth/delete-account
Sign out (soft delete account).

**Response:** 200 OK
```json
{
  "success": true,
  "message": "Account deleted successfully. Contact support to restore."
}
```

**Effect:**
- Token blacklisted
- `deleted_at` timestamp set
- Cannot login again (unless admin restores)
- User data retained for compliance

---

### Authenticated + Verified Endpoints

All enrichment and DSAR endpoints require `is_verified=true`.

**Blocked response (403):**
```json
{
  "success": false,
  "error": "Email verification required. Please check your email."
}
```

---

## Security Features

### Password Hashing

- **Algorithm:** bcrypt
- **Cost factor:** 12 (2^12 = 4096 iterations)
- **Salt:** Automatic, unique per password
- **Constant-time comparison:** Prevents timing attacks
- **Rehashing:** Detects old hashes and upgrades on login

**Performance:** ~100-300ms per hash (intentionally slow to prevent brute force)

### Token Security

**Access Token:**
- HttpOnly cookie (JavaScript cannot access)
- Secure flag in production (HTTPS only)
- SameSite=Lax (CSRF protection)
- Short-lived (15 minutes)
- Blacklist checked on every request

**Refresh Token:**
- Stored in database (not exposed to frontend)
- One-time use (rotation detection)
- Parent-child chain for audit
- Revoked on logout

### Logged-Out Token Detection

**Purpose:** Detect stolen tokens used after logout.

**Flow:**
1. User logs out → token JTI added to blacklist
2. Attacker tries to use stolen token
3. Backend detects token in blacklist
4. Security alert logged:
   - Event type: `SUSPICIOUS_ACTIVITY`
   - Details: "Token used after logout"
   - User ID, IP, timestamp

**Dual storage:**
- **Redis:** Fast lookup (<1ms), auto-expires
- **PostgreSQL:** Audit trail, synced on startup

**Cleanup:** Expired tokens removed by scheduled job.

### Rate Limiting

Prevents brute force and abuse:

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 5 requests/minute per IP |
| `/auth/register` | 3 requests/hour per IP |
| `/auth/resend-verification` | 1 request/5 minutes per user |
| `/api/opt-out` | 10 requests/minute per IP |

**Backend:** `slowapi` library with Redis storage.

### Audit Logging

All auth events logged to `auth_audit_logs` table:

**Logged events:**
- `register` - User registration
- `login` - Successful login
- `login_failed` - Failed login attempt
- `logout` - User logout
- `email_verified` - Email verification
- `token_refresh` - Token rotation
- `account_deleted` - Account deletion
- `suspicious_activity` - Security alert

**Log data:**
- User ID
- Event type
- IP address
- User agent
- Timestamp
- Success/failure
- Failure reason (if failed)
- Additional metadata (JSON)

**Retention:** Recommended 1 year minimum for compliance.

### Security Headers

Applied to all responses:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains (production)
Content-Security-Policy: default-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## Troubleshooting

### User can't log in

**Symptoms:** Login fails with "Invalid credentials"

**Checks:**
1. Verify email and password correct
2. Check account not deleted:
   ```sql
   SELECT email, deleted_at FROM users WHERE email = 'user@example.com';
   ```
3. Check password hash in database (should start with `$2b$12$`)
4. Check rate limiting:
   ```bash
   redis-cli GET "rate:login:user-ip-address"
   ```

**Solutions:**
- If deleted: Admin restore (`UPDATE users SET deleted_at = NULL WHERE id = '...'`)
- If rate limited: Wait or clear Redis key
- If password wrong: User must reset (password reset flow TBD)

---

### Email verification not received

**Symptoms:** User registered but no verification email

**Checks:**
1. Check email queue:
   ```bash
   redis-cli LLEN "email:queue"
   ```
2. Check SendGrid logs (SendGrid dashboard)
3. Check spam folder
4. Check email_verification_tokens table:
   ```sql
   SELECT * FROM email_verification_tokens WHERE user_id = '...';
   ```

**Solutions:**
- If email worker not running: Start worker
- If token expired: User clicks "Resend verification"
- If SendGrid error: Check API key and logs

---

### Token blacklist not working

**Symptoms:** User can access API after logout

**Checks:**
1. Verify Redis connection:
   ```bash
   redis-cli PING
   ```
2. Check token in blacklist:
   ```bash
   redis-cli GET "blacklist:{jti}"
   ```
3. Check PostgreSQL logged_out_tokens:
   ```sql
   SELECT * FROM logged_out_tokens WHERE token_jti = '...';
   ```
4. Verify token validation middleware active

**Solutions:**
- If Redis down: Restart Redis, backend auto-syncs from PostgreSQL
- If token not added: Check logout endpoint logs
- If middleware not active: Verify `main.py` includes auth middleware

---

### "Token used after logout" security alerts

**Symptoms:** High volume of `SUSPICIOUS_ACTIVITY` events

**Causes:**
1. **Legitimate:** User clicks logout in one browser tab, another tab tries request
2. **Attack:** Stolen token used after victim logs out

**Investigation:**
1. Check audit logs for pattern:
   ```sql
   SELECT user_id, ip_address, user_agent, created_at
   FROM auth_audit_logs
   WHERE event_type = 'suspicious_activity'
   ORDER BY created_at DESC
   LIMIT 100;
   ```

2. Look for:
   - Different IP addresses → likely attack
   - Same IP, same user agent → likely multi-tab issue
   - High frequency → possible automated attack

**Response:**
- If attack suspected: Contact user, force password reset
- If multi-tab: Educate user or add grace period

---

### Refresh token rotation failing

**Symptoms:** User logged out unexpectedly after 15 minutes

**Checks:**
1. Verify refresh token endpoint working:
   ```bash
   curl -X POST http://localhost:8000/auth/jwt/refresh \
     -H "Cookie: refresh_token=..." -v
   ```
2. Check refresh_tokens table for `used=true` entries
3. Check frontend auto-refresh logic

**Solutions:**
- If token marked used: Frontend tried to refresh twice (race condition)
- If token expired: User must log in again (7-day limit reached)
- Add retry logic in frontend for refresh failures

---

## Development

### Running Tests

Backend tests:
```bash
cd backend
pytest tests/test_password_hashing.py -v
pytest tests/test_auth_e2e.py -v
pytest tests/test_email_verification.py -v
pytest tests/test_logged_out_tokens.py -v
pytest tests/test_unverified_access.py -v
pytest tests/test_account_deletion.py -v
```

All auth tests:
```bash
cd backend
pytest tests/test_*auth* tests/test_*verification* tests/test_*logged_out* tests/test_*account_deletion* tests/test_*password* -v
```

Coverage check:
```bash
cd backend
pytest tests/ --cov=app/auth --cov-report=term-missing
```

### Local Development Setup

1. **Start dependencies:**
   ```bash
   docker-compose up postgres redis
   ```

2. **Run migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```

3. **Start backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

4. **Start email worker** (optional, for testing emails):
   ```bash
   cd backend
   rq worker email_queue
   ```

5. **Start frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

6. **Test flow:**
   - Visit http://localhost:3000/register
   - Register a user
   - Check terminal for verification link (if email worker not running)
   - Verify email
   - Login

### Mocking Email in Tests

Tests should mock `enqueue_email` to avoid sending real emails:

```python
from unittest.mock import patch

@patch('app.services.email_service.enqueue_email')
async def test_registration(mock_email, client):
    response = await client.post('/auth/register', json={
        "email": "test@example.com",
        "password": "Test123!",
        "first_name": "Test",
        "last_name": "User"
    })

    assert response.status_code == 201
    mock_email.assert_called_once()
```

### Creating Test Users

Helper function for tests:

```python
async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "Test123!",
    is_verified: bool = True
) -> User:
    user = User(
        email=email,
        first_name="Test",
        last_name="User",
        hashed_password=hash_password(password),
        is_verified=is_verified
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

---

## Production Deployment

### Environment Setup

1. **Generate production secret key:**
   ```bash
   openssl rand -hex 32
   ```

2. **Set production environment variables:**
   ```bash
   # Required
   DATABASE_URL=postgresql+asyncpg://user:password@prod-db:5432/hyrepath
   REDIS_URL=redis://prod-redis:6379/0
   SECRET_KEY=your-256-bit-production-key
   COOKIE_SECURE=true
   COOKIE_DOMAIN=.yourdomain.com
   FRONTEND_URL=https://yourdomain.com

   # Google OAuth (production URLs)
   GOOGLE_OAUTH_REDIRECT_URL=https://yourdomain.com/callback/google

   # SendGrid
   SENDGRID_API_KEY=SG.production-key
   SENDGRID_FROM_EMAIL=noreply@yourdomain.com
   ```

3. **Update Google OAuth redirect URIs** in Google Cloud Console

4. **Enable HTTPS:**
   - Configure SSL/TLS certificates
   - Set `COOKIE_SECURE=true`
   - Configure reverse proxy (Nginx, Caddy, etc.)

### Security Checklist

- [ ] `SECRET_KEY` is unique and never committed
- [ ] `COOKIE_SECURE=true` (HTTPS only)
- [ ] `COOKIE_DOMAIN` set correctly
- [ ] CORS origins restricted to production frontend
- [ ] Google OAuth redirect URIs updated
- [ ] SendGrid API key is production key
- [ ] Rate limiting enabled
- [ ] Security headers active
- [ ] Audit logging enabled
- [ ] Redis persistence enabled
- [ ] PostgreSQL backups configured
- [ ] SSL/TLS certificates valid

### Scaling

For 10,000+ concurrent users:

**API Instances:**
- Run 4-6 FastAPI instances behind load balancer
- Each instance: 2 CPU, 4GB RAM
- Connection pool: 20-30 per instance

**Database:**
- PostgreSQL Primary: 4 CPU, 16GB RAM
- Read replicas for `/users/me` lookups
- Connection pooling configured

**Redis:**
- Single instance: 2GB RAM (sufficient for 10K users)
- Or Redis Cluster: 3+ nodes for high availability
- Persistence enabled (AOF + RDB snapshots)

**Monitoring:**
- Prometheus metrics
- Grafana dashboards
- Alerts for:
  - Login latency > 500ms (p95)
  - Database connections > 80%
  - Redis memory > 80%
  - Failed logins > 100/min (brute force)
  - Token reuse > 10/hour (stolen tokens)

### Backup and Recovery

**PostgreSQL Backup:**
```bash
# Daily automated backup
pg_dump -h localhost -U postgres -d hyrepath -F c -f backup_$(date +%Y%m%d).dump

# Restore
pg_restore -h localhost -U postgres -d hyrepath backup_20260731.dump
```

**Redis Backup:**
```bash
# Enable in redis.conf
appendonly yes
save 900 1
save 300 10

# Backup files
/var/lib/redis/dump.rdb
/var/lib/redis/appendonly.aof
```

**Recovery Plan:**
1. Restore PostgreSQL from latest backup
2. Sync Redis blacklist from PostgreSQL:
   - Restart backend, auto-sync on startup
3. Verify auth working:
   - Test login
   - Test token validation
   - Check audit logs

---

## Related Documentation

- [ADR 0009: Cookie OAuth Authentication](./adr/0009-cookie-oauth-authentication.md)
- [Google OAuth Setup Guide](./google-oauth-setup.md)
- [Backend Architecture](../backend/docs/ARCHITECTURE.md)
- [RULE.md](../RULE.md) - Development rules

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review audit logs: `SELECT * FROM auth_audit_logs WHERE user_id = '...' ORDER BY created_at DESC LIMIT 50;`
3. Check Redis status: `redis-cli INFO memory`
4. Check PostgreSQL connections: `SELECT count(*) FROM pg_stat_activity;`
