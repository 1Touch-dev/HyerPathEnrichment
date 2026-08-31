# Security Hardening Guide

Production security best practices for Hyrepath Enrichment operators. This guide complements [deployment.md](deployment.md) with security-focused operational guidance.

**Target audience:** Self-hosted stack operators deploying to staging or production.

**Last updated:** August 2026

---

## 0. P0 runtime guards (code-enforced)

As of branch `fix/security-p0-master-complete-foundation`, the API **refuses to start** when `APP_ENV` is `staging` or `production` and any of the following are true:

- `SECRET_KEY` is missing, shorter than 32 characters, or still a known default
- `API_TOKEN` is missing or still a known default (`change-me`, etc.)
- `COOKIE_SECURE` is not `true`
- `CHANGEDETECTION_API_KEY` is empty (signals webhook must not be open)

Related code hardenings in the same change:

- Opt-out/DSAR purge clears both `dossier_payload` and `request_payload`
- Impersonation always requires MFA and cannot target a superuser
- Candidate/operator webhook POSTs reject non-https and private/local targets (`follow_redirects=False`)
- `/api/email/test` requires `X-API-Token` and returns 404 in staging/production

**Still open (deferred):** email confirmation before opt-out purge.

### P1 hardenings (branch `fix/security-p1-master-complete-foundation`)

- Refresh tokens stored as SHA-256 hashes (dual-read upgrades legacy plaintext); account delete revokes all refresh sessions and clears both cookies
- Account delete cascades erase of CVs/chat/outreach and scrubs sourced-lead PII; identifier purge also scrubs outreach recipients + sourced leads
- MFA secrets sealed at rest (Fernet derived from `SECRET_KEY`); legacy plaintext still verifies
- `recruiter_actions:write` required for apply/suggest; LinkedIn lead list requires `linkedin_sourcing:write`
- Support cannot deactivate superusers (only another superuser can)
- Transactional email HTML escapes dynamic fields; href schemes allowlisted
- BFF forwards multi-`Set-Cookie` via `getSetCookie()` helper
- `/auth/refresh` rate-limited; cookie-auth rate limits key on cookie+IP when Bearer is absent

---

## 1. API Token Security

The `API_TOKEN` secures all enrichment endpoints (`/enrich`, `/enrich/sync`, `/enrich/status`). Treat it as a production credential.

### Generate strong tokens

Use cryptographically secure random generation (32+ characters):

```bash
openssl rand -base64 32
```

**Never** use weak tokens like `dev-token-123`, commit SHAs, or predictable patterns.

### Token rotation

- **Quarterly rotation** (every 90 days) as a baseline
- **Immediate rotation** on team member departure, credential leak, or suspected compromise
- Update `API_TOKEN` in `backend/.env.production` (host) and `BACKEND_API_TOKEN` (frontend deployment)

### Storage and access control

| Environment | Storage | Permissions |
|------------|---------|-------------|
| **Host (backend)** | `backend/.env.production` | Mode `600` (`chmod 600`), root or service user only |
| **Frontend** | Deployment platform secrets (Vercel, Cloudflare Pages) | Platform access control; never expose in client bundles |
| **Multi-host** | Secrets manager (HashiCorp Vault, AWS Secrets Manager, Doppler) | Centralized audit + rotation |

**Never commit tokens to git.** Verify `.gitignore` excludes `.env.production` (already configured).

### Token audit

- Log all enrichment requests with timestamp and token ID (first 8 chars only — never the full token)
- Monitor for rate-limit violations or abnormal usage patterns
- Check Sentry / monitoring for `401 Unauthorized` spikes (potential brute-force attempts)

---

## 2. TLS Configuration

All production traffic **must** use HTTPS. The API listens on HTTP :8000 internally; TLS terminates at the reverse proxy.

### Caddy (recommended)

Zero-config automatic certificate renewal via Let's Encrypt.

Example `/etc/caddy/Caddyfile`:

```
enrich.hyrepath.io {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy handles:
- Initial ACME certificate issuance
- Automatic renewal (30 days before expiry)
- TLS 1.2+ enforcement
- HTTPS redirect (HTTP → HTTPS)

**No operator action required** after initial setup.

### Manual certificate management (certbot)

For nginx or Apache:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d enrich.hyrepath.io

# Test renewal
sudo certbot renew --dry-run

# Auto-renewal (systemd timer)
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

Certbot systemd timer runs twice daily; certificates renew at 30 days before expiry.

### Nginx TLS hardening

Example `/etc/nginx/sites-available/enrich.hyrepath.io`:

```nginx
server {
    listen 443 ssl http2;
    server_name enrich.hyrepath.io;

    # Certificates (certbot auto-generates these paths)
    ssl_certificate /etc/letsencrypt/live/enrich.hyrepath.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/enrich.hyrepath.io/privkey.pem;

    # TLS 1.2+ only
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;

    # HSTS (1 year)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Additional security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name enrich.hyrepath.io;
    return 301 https://$host$request_uri;
}
```

### Disable legacy TLS

**TLS 1.0 and 1.1 are deprecated** (RFC 8996). Explicitly disable:

- **Caddy:** Enforces TLS 1.2+ by default
- **Nginx:** Set `ssl_protocols TLSv1.2 TLSv1.3;` (shown above)
- **Apache:** `SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1`

### HSTS header

Force browsers to always use HTTPS for 1 year:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

Caddy applies this automatically. For nginx, add the `add_header` directive shown above.

**Preload:** After 3+ months of stable HTTPS operation, consider submitting the domain to the [HSTS preload list](https://hstspreload.org/).

---

## 3. Database Security

Postgres stores enrichment jobs, suppression lists, audit logs, and photo cache entries.

### Strong passwords

Generate a secure Postgres password (16+ characters, mixed case, symbols):

```bash
openssl rand -base64 24
```

Set in `backend/.env.production`:

```bash
POSTGRES_USER=hyrepath_prod
POSTGRES_PASSWORD=<strong-password>
DATABASE_URL=postgresql+asyncpg://hyrepath_prod:<strong-password>@postgres:5432/hyrepath_enrichment
```

**Never use the dev default** (`hyrepath` / `hyrepath`) in production (see [deployment.md § Secrets checklist](deployment.md#secrets-checklist)).

### Port binding

Postgres **must not** be exposed to the public internet.

In `backend/docker/docker-compose.prod.yml`:

```yaml
services:
  postgres:
    # No 'ports:' section — internal network only
    # API and worker connect via internal service name 'postgres:5432'
```

Verify no external binding:

```bash
docker ps | grep postgres
# Should NOT show 0.0.0.0:5432 or <public-ip>:5432
```

If you need direct access for debugging, use SSH port forwarding:

```bash
ssh -L 5433:127.0.0.1:5432 user@enrich.hyrepath.io
psql -h 127.0.0.1 -p 5433 -U hyrepath_prod hyrepath_enrichment
```

### Connection pooling

Limit `max_connections` to prevent resource exhaustion. Default Postgres `max_connections=100` is sufficient for most single-host deployments.

For high-traffic production, consider PgBouncer or connection pooler tuning (deferred to multi-host scaling guide).

### Regular updates

Postgres image receives security patches via the official Docker image (`postgres:17` or pinned patch version).

Update quarterly or on CVE alerts:

```bash
cd backend/docker
docker compose pull postgres
docker compose up -d postgres
```

**Test in staging first.**

### Encrypted backups

Hyrepath does not bundle backup automation. Operators **must** implement regular encrypted backups.

Example using `pg_dump` + GPG:

```bash
# Generate backup encryption key (one-time)
gpg --gen-key

# Daily backup script (add to cron)
#!/bin/bash
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="hyrepath_enrichment_${BACKUP_DATE}.sql.gpg"

docker exec -t hyrepath-postgres pg_dump -U hyrepath_prod hyrepath_enrichment \
  | gpg --encrypt --recipient ops@hyrepath.io \
  > "/backup/${BACKUP_FILE}"

# Retain 30 days (adjust as needed)
find /backup -name "hyrepath_enrichment_*.sql.gpg" -mtime +30 -delete
```

**Retention:** 30 days minimum; adjust for compliance requirements (see [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) for audit log retention — 5 years by default).

---

## 4. Redis Security

Redis handles rate-limit counters, photo cache (Tier 1), and temporary enrichment state.

### Protected mode

Redis runs in **protected mode** by default (Docker Compose internal network). Verify no external port exposure:

```yaml
services:
  redis:
    # No 'ports:' section in docker-compose.prod.yml
```

```bash
docker ps | grep redis
# Should NOT show 0.0.0.0:6379
```

### Authentication (requirepass)

For production, set a strong Redis password:

```bash
# On the host (inside Redis container)
docker exec -it hyrepath-redis redis-cli CONFIG SET requirepass '<strong-password>'
docker exec -it hyrepath-redis redis-cli CONFIG REWRITE
```

Update `REDIS_URL` in `backend/.env.production`:

```bash
REDIS_URL=redis://:strong-password@redis:6379/0
```

**Important:** URL-encode special characters in the password (`@`, `:`, `/` → percent-encoded).

### Disable dangerous commands

Protect against accidental data loss:

Add to `backend/docker/docker-compose.prod.yml`:

```yaml
services:
  redis:
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --rename-command FLUSHALL ""
      --rename-command FLUSHDB ""
      --rename-command KEYS ""
      --rename-command CONFIG ""
      --appendonly yes
```

| Command | Risk | Mitigation |
|---------|------|------------|
| `FLUSHALL` / `FLUSHDB` | Wipes all data | Rename to `""` (disable) |
| `KEYS` | Blocks Redis on large keyspaces | Rename or disable; use `SCAN` instead |
| `CONFIG` | Runtime config changes | Disable after initial setup |

### AOF encryption at rest

Redis Append-Only File (AOF) persistence enabled via `--appendonly yes` (shown above).

For encryption at rest, use:

1. **Encrypted block storage** (e.g., LUKS on Linux, provider-managed encryption for cloud VMs)
2. **Full-disk encryption** on the host
3. **Redis Enterprise** (paid) for built-in encryption at rest

Community Redis does not natively encrypt AOF files; encryption must occur at the storage layer.

### Network isolation

Redis and Postgres should communicate only with the API and worker containers. Use Docker internal networks (already configured in `docker-compose.yml`).

For multi-host deployments, place Redis in a **private subnet** or VPC with no internet ingress.

---

## 5. Docker Security

Hyrepath containers already follow non-root user best practices (see [backend/docker/Dockerfile.api](../backend/docker/Dockerfile.api) and [Dockerfile.worker](../backend/docker/Dockerfile.worker)).

### Non-root users

Both API and worker run as `appuser` (UID 1000):

```dockerfile
RUN addgroup --system --gid 1000 appuser \
 && adduser --system --uid 1000 --ingroup appuser appuser
USER appuser
```

**Never run containers as root** in production.

### Read-only root filesystem

Where possible, mount container filesystems read-only to prevent runtime tampering:

```yaml
services:
  api:
    read_only: true
    tmpfs:
      - /tmp
      - /var/tmp
```

**Caveat:** The current Dockerfiles write to `/app/.asset-cache` (local asset cache) and `/tmp` (temporary uploads). A read-only root filesystem requires volume mounts for these paths.

**Deferred:** Full read-only support pending refactor to externalize asset cache to R2-only storage.

### Resource limits

Prevent resource exhaustion attacks via Docker Compose `deploy.resources`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          memory: 512M
  worker:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
        reservations:
          memory: 1G
```

**Adjust** based on host capacity and observed usage. Monitor via `docker stats`.

### Image scanning

Scan images for CVEs before deploying to production:

```bash
# Docker Scout (built-in to Docker Desktop)
docker scout cves ghcr.io/<owner>/<repo>/api:latest

# Trivy (open-source)
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image ghcr.io/<owner>/<repo>/api:latest
```

**Integrate into CI:** Add Trivy or Scout to [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) as a required check before production approval.

### No privileged containers

**Never** use `privileged: true` or `--privileged` in production. The Hyrepath stack does not require elevated container privileges.

If Tier 1 LinkedIn scraping (Selenium + Multilogin) requires Docker-in-Docker, isolate the worker in a separate security boundary (dedicated VM or Kubernetes namespace with network policies).

---

## 6. Network Security

Host-level firewall and SSH hardening.

### Firewall rules

Allow only necessary ports:

```bash
# Ubuntu/Debian (ufw)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH (key-only, see below)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Verify
sudo ufw status verbose
```

**Block all other ports.** Internal Docker services (Postgres :5432, Redis :6379, API :8000) communicate via internal networks and do not need host firewall rules.

### SSH hardening

Edit `/etc/ssh/sshd_config`:

```sshd_config
# Disable password authentication (key-only)
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM no

# Disable root login
PermitRootLogin no

# Allow only specific users
AllowUsers deploy ops

# Modern key exchange algorithms
KexAlgorithms curve25519-sha256,diffie-hellman-group-exchange-sha256
```

Restart SSH:

```bash
sudo systemctl restart sshd
```

**Test SSH login with a new terminal session BEFORE closing the current one** to avoid lockout.

### Fail2ban (brute-force protection)

Automatically ban IPs after repeated SSH failures:

```bash
sudo apt install fail2ban

# Default jail: 5 failures → 10-minute ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo fail2ban-client status sshd
```

Custom jail for the API (optional — rate limiting already enforced in Redis):

```ini
# /etc/fail2ban/jail.d/hyrepath-api.conf
[hyrepath-api]
enabled = true
port = 443
filter = hyrepath-api
logpath = /var/log/nginx/access.log
maxretry = 10
bantime = 3600
```

Filter definition (`/etc/fail2ban/filter.d/hyrepath-api.conf`):

```ini
[Definition]
failregex = ^<HOST> .* "(POST|GET) /api/enrich.* HTTP.*" 401
ignoreregex =
```

**Note:** Redis-based rate limiting (see [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md)) is the primary defense; Fail2ban is a fallback for IP-level bans.

### VPC / private network

For cloud deployments (AWS, GCP, Azure, DigitalOcean):

- Place **Postgres and Redis** in a **private subnet** (no public IP)
- API and worker access databases via internal VPC IPs
- Only the reverse proxy (Caddy/nginx) has a public IP

Example AWS architecture:

```
Public Subnet:
  - Reverse Proxy (EC2 with Elastic IP)

Private Subnet:
  - API + Worker (ECS or EC2, private IPs only)
  - RDS Postgres (private endpoint)
  - ElastiCache Redis (private endpoint)
```

**VPC setup is cloud-provider-specific.** Consult provider documentation for Network ACLs and Security Groups.

### Rate limiting at reverse proxy

Enforce rate limits at the edge (in addition to Redis-based limits in the API):

**Nginx** (`/etc/nginx/nginx.conf`):

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;

    server {
        location /api/enrich {
            limit_req zone=api_limit burst=5 nodelay;
            proxy_pass http://127.0.0.1:8000;
        }
    }
}
```

**Caddy** (v2.7+):

```
enrich.hyrepath.io {
    rate_limit {
        zone api_limit {
            key {remote_host}
            events 30
            window 1m
        }
    }
    reverse_proxy 127.0.0.1:8000
}
```

**Cloudflare:** Enable "Rate Limiting" rules for `/api/enrich*` (30 requests/minute per IP).

---

## 7. Secrets Management

Best practices for handling secrets at scale.

### Docker secrets

For single-host deployments, use [Docker secrets](https://docs.docker.com/engine/swarm/secrets/) (requires Swarm mode or Compose v3.1+):

```yaml
services:
  api:
    secrets:
      - api_token
      - database_url
    environment:
      API_TOKEN_FILE: /run/secrets/api_token
      DATABASE_URL_FILE: /run/secrets/database_url

secrets:
  api_token:
    file: ./secrets/api_token.txt
  database_url:
    file: ./secrets/database_url.txt
```

Application code must read from `*_FILE` paths instead of environment variables.

**Status:** Hyrepath does not currently support `*_FILE` env loading. This is a future enhancement.

### HashiCorp Vault

For multi-host or team deployments:

1. Store secrets in Vault (`secret/hyrepath/production`)
2. Containers fetch secrets on startup via `vault kv get`
3. Rotate secrets via Vault UI/API without redeploying

Example startup script:

```bash
#!/bin/bash
export VAULT_ADDR=https://vault.hyrepath.io
export VAULT_TOKEN=$(cat /etc/vault-token)

export API_TOKEN=$(vault kv get -field=api_token secret/hyrepath/production)
export DATABASE_URL=$(vault kv get -field=database_url secret/hyrepath/production)

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Vault setup is outside the scope of this guide.** See [HashiCorp Vault documentation](https://developer.hashicorp.com/vault/docs).

### Never log secrets

Verify log scrubbing in Sentry and application logs:

```bash
# backend/.env.production
SENTRY_SEND_DEFAULT_PII=false
SENTRY_SCRUB_SECRETS=true
```

Hyrepath masks `API_TOKEN`, `POSTGRES_PASSWORD`, and enricher credentials in Sentry events (see `app/core/logging.py`).

**Audit logs** (SQL `audit_logs` table) store only **hashed identifiers** — never raw PII (see [backend/docs/LEGAL.md § Audit logging](../backend/docs/LEGAL.md#audit-logging)).

### Redact PII in monitoring

Set `SENTRY_SEND_DEFAULT_PII=false` (already default in `.env.production.example`).

If you capture request bodies for debugging, **strip** email addresses, LinkedIn URLs, and names before sending to Sentry:

```python
import sentry_sdk
from sentry_sdk.scrubbers import DEFAULT_DENYLIST

sentry_sdk.init(
    dsn="...",
    before_send=lambda event, hint: scrub_pii(event, hint),
)
```

**PII scrubbing is already implemented** in `app/core/logging.py` (production stack). Verify it remains active after any logging refactors.

### Rotate secrets on team changes

**Immediate rotation required** when:

- A team member with production access leaves
- A credential is suspected to be leaked (git history, logs, Slack)
- A contractor engagement ends
- A third-party integration is deprecated

**Rotation checklist:**

1. Generate new `API_TOKEN`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`
2. Update `backend/.env.production` (host) and frontend deployment secrets
3. Restart containers: `docker compose up -d --force-recreate`
4. Verify health: `curl https://enrich.hyrepath.io/health`
5. Invalidate old tokens (if token versioning is implemented)
6. Audit access logs for 48 hours post-rotation

### Audit secret access

If using a secrets manager, enable **audit logging** for all secret reads:

- **Vault:** Enable audit device (`vault audit enable file`)
- **AWS Secrets Manager:** CloudTrail logs `GetSecretValue` events
- **GCP Secret Manager:** Cloud Audit Logs
- **Azure Key Vault:** Diagnostic settings

Review audit logs quarterly or on-demand during investigations.

---

## 8. Compliance Checklist

Operator verification for legal and regulatory adherence. See [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) for full policy.

### Pre-production verification

- [ ] **Opt-out flow tested:** Submit opt-out via `POST /api/opt-out`, verify suppression prevents enrichment
- [ ] **Purge confirmed:** Opted-out identifier has `dossier_payload = {}`, `status = purged` in `jobs` table
- [ ] **Photo cache cleared:** `photo_cache` SQL and Redis `tier1:photo:*` keys deleted on opt-out
- [ ] **R2 assets deleted:** Object storage keys referenced by `asset_key` removed on purge
- [ ] **Suppression pre-check works:** `POST /enrich` with suppressed identifier returns `status: suppressed` without enqueueing

### Audit log retention

- [ ] **Retention configured:** `AUDIT_LOG_RETENTION_YEARS=5` (default) in `.env.production`
- [ ] **Cleanup scheduled:** Add `backend/scripts/purge_audit_logs.py` to cron (quarterly)
- [ ] **Backup includes audit logs:** `pg_dump` captures full `audit_logs` table (see § 3 Database Security)

### Data retention policy

Document and enforce data retention:

| Data type | Retention | Cleanup method |
|-----------|-----------|----------------|
| **Enrichment jobs** (non-purged) | 90 days (adjust as needed) | Manual purge script or automated job |
| **Audit logs** | 5 years (default, see `AUDIT_LOG_RETENTION_YEARS`) | `scripts/purge_audit_logs.py` |
| **Photo cache** | 30 days or until job purge | TTL in Redis + SQL cleanup on purge |
| **Suppression list** | **Permanent** (never deleted) | N/A — GDPR right-to-erasure satisfied via purge |

**Important:** Suppression list entries are **never** deleted — this is by design to honor opt-out permanently.

### GDPR / CCPA rights

- [ ] **Right to access:** DSAR endpoint (`POST /api/dsar` with `request_type: access`) returns job count and date range (no raw PII)
- [ ] **Right to deletion:** DSAR deletion (`request_type: deletion`) runs suppression + purge (same as opt-out)
- [ ] **30-day SLA:** DSAR requests are processed immediately in v1 (automated stack). Manual review queue deferred.
- [ ] **Unauthenticated access:** Opt-out and DSAR endpoints are public (no `Authorization` header required) so data subjects can exercise rights without an API key

### Regular security audits

- [ ] **Quarterly token rotation** (see § 1 API Token Security)
- [ ] **Quarterly dependency updates:** `docker compose pull`, test in staging, deploy to production
- [ ] **CVE monitoring:** Subscribe to [Postgres security](https://www.postgresql.org/support/security/), [Redis security](https://redis.io/topics/security), and [Python security](https://www.python.org/news/security/) mailing lists
- [ ] **Penetration testing:** Annual pen test or automated scanning (OWASP ZAP, Burp Suite) on staging
- [ ] **Access review:** Audit SSH keys, API tokens, and secrets manager access quarterly

### Incident response plan

Document and test your incident response:

1. **Detection:** Monitor Sentry, logs, and uptime checks (see [OPS.md](OPS.md))
2. **Containment:** Revoke compromised token, isolate affected host, enable maintenance mode
3. **Investigation:** Check audit logs, access logs, Sentry events for root cause
4. **Remediation:** Patch vulnerability, rotate secrets, restore from backup if needed
5. **Communication:** Notify affected customers (if data breach), document postmortem
6. **Prevention:** Update this guide and CI/CD checks to prevent recurrence

**Test the plan** annually via tabletop exercise or staging simulation.

---

## Enforcement summary

| Section | Enforcement | Verification |
|---------|-------------|--------------|
| **1. API Token Security** | Manual rotation + secrets manager | Audit logs, token age alerts |
| **2. TLS Configuration** | Caddy auto-renewal or certbot systemd timer | `curl -I https://enrich.hyrepath.io` (check HSTS header) |
| **3. Database Security** | Docker Compose internal network + password | `docker ps` (no public :5432), `psql` connection test |
| **4. Redis Security** | Protected mode + requirepass + disabled commands | `docker ps` (no public :6379), `redis-cli INFO` |
| **5. Docker Security** | Non-root users (in Dockerfiles) + resource limits (compose) | `docker inspect <container>` (check User, Resources) |
| **6. Network Security** | Host firewall + SSH config + Fail2ban | `sudo ufw status`, `ssh -v` test, Fail2ban logs |
| **7. Secrets Management** | `.env.production` mode 600 + Vault (optional) | `ls -la backend/.env.production`, Sentry scrubbing test |
| **8. Compliance Checklist** | Code enforcement (opt-out flow) + operator verification | End-to-end opt-out test, DSAR test, audit log query |

---

## Related documentation

- [deployment.md](deployment.md) — Production deploy workflow, TLS setup, secrets checklist
- [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) — Compliance policy, opt-out, DSAR, audit logs
- [OPS.md](OPS.md) — Rollback, incident response, audit log purge
- [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — Rate limiting, Redis counters, request flow

---

**Questions or security concerns?** Contact the Hyrepath security team or open a private security advisory on GitHub.
