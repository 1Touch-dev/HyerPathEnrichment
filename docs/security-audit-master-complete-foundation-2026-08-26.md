# 🛡️ Code Hardening, Security Audit & Global Compliance Report

| Field | Value |
| :--- | :--- |
| **Branch** | `master-complete-foundation` |
| **Commit** | `9e1623c` |
| **Audit date** | 2026-08-26 (UTC) |
| **Scope** | Backend (`backend/app`), Frontend BFF (`frontend/app/api`), compliance modules, Docker/env defaults |
| **Method** | Static code review (auth, AppSec, privacy, infra); no live exploit PoCs executed |
| **Classification** | Confidential — Internal / Client Security |

---

### 1. Executive Summary

**Overall posture:** The foundation branch has meaningful security building blocks — cookie JWT auth with refresh rotation, bcrypt passwords, origin-based CORS with credentials, Redis sliding-window rate limits, enrichment opt-out/suppression, DSAR endpoints, admin RBAC + MFA scaffolding, and compliance audit hashing for enrichment identifiers. That said, **the current security posture is not production-ready** for multi-jurisdiction PII processing without remediating several Critical/High defects.

**Critical risk areas:**

1. **Unauthenticated destructive opt-out** — `POST /api/opt-out` accepts any identifier and immediately purges enrichment data (DoS / malicious erasure).
2. **Default / weak JWT & API secrets** — app boots with documented defaults; no production fail-fast on `SECRET_KEY` / `API_TOKEN`.
3. **Privilege escalation via impersonation** — admins can impersonate `is_superuser` targets and inherit full privilege short-circuit.
4. **Incomplete erasure** — purge clears `dossier_payload` but leaves raw PII in `jobs.request_payload`; account delete does not cascade to CVs, chat, outreach, or sourced leads.
5. **SSRF** — authenticated users can set arbitrary `webhook_url` values that workers POST to.
6. **Fail-open webhook auth** — signals endpoint skips auth when `CHANGEDETECTION_API_KEY` is empty.
7. **Authorization gaps** — recruiter actions and LinkedIn lead listing are available to any verified user.

**Code redundancy & architectural debt:**

- ~100+ Next.js BFF `route.ts` files duplicate try/`backendFetch`/error mapping; auth routes reimplement cookie forwarding inconsistently (fragile multi-`Set-Cookie` relay).
- Dual LinkedIn URL validators; dual pgvector SQL styles (bound params vs string interpolation).
- Enricher subprocess runners share `run_command` but lack shared username/CLI sanitization.
- Legacy `API_TOKEN` / `verify_token` coexist with cookie JWT; docs (`LEGAL.md`, `SECURITY_HARDENING.md`) partially diverge from live behavior (e.g., DSAR returning full dossier).
- Tenancy / brand isolation is design-only (Machine 1 docs); runtime isolation is per-`user_id` on a shared DB.

**Verdict:** Treat as **conditional go** — ship only after P0 items in §5 are fixed and secrets rotated for any environment that ever used defaults.

---

### 2. Branch-Wise Vulnerability & Security Audit

#### Branch: `master-complete-foundation` @ `9e1623c`

##### Vulnerabilities & Known Bugs

| ID | Severity | OWASP / Class | Finding | Location |
| :--- | :--- | :--- | :--- | :--- |
| V-01 | **Critical** | A01 Broken Access Control | Public opt-out triggers immediate purge without proof of identity | `backend/app/modules/opt_out/router.py` |
| V-02 | **Critical** | A07 Auth Failures | Default `SECRET_KEY` / `API_TOKEN`; no prod refuse-to-start | `backend/app/core/config.py` |
| V-03 | **Critical** | A01 Privilege Escalation | Impersonation of `is_superuser` inherits all permissions | `backend/app/modules/admin/impersonation.py` |
| V-04 | **High** | A01 / A10 SSRF | User-controlled `webhook_url` POSTed by workers | `backend/app/clients/notify.py` |
| V-05 | **High** | A07 Auth Failures | Signals webhook auth skipped when API key empty | `backend/app/modules/signals/router.py` |
| V-06 | **High** | A01 Broken Access Control | Email test “API token” dependency never verifies client token | `backend/app/modules/email/router.py` |
| V-07 | **High** | A01 Broken Access Control | Recruiter apply/suggest: any verified user, any candidate | `backend/app/modules/recruiter_actions/router.py` |
| V-08 | **High** | A02 Cryptographic Failures | Refresh tokens stored as plaintext PK; delete-account does not revoke them | `backend/app/auth/refresh_tokens.py`, `auth/router.py` |
| V-09 | **High** | A07 Session | `COOKIE_SECURE` defaults `False`; MFA optional for impersonation; MFA secrets plaintext | `config.py`, `impersonation.py`, `mfa.py` |
| V-10 | **High** | A01 | Support/`users:suspend` can disable superusers | `backend/app/modules/admin/service.py` |
| V-11 | **Medium** | A03 Injection | Document vector search embeds floats via f-string SQL | `backend/app/services/vector_search.py` |
| V-12 | **Medium** | A03 / A05 | Enricher CLI flag injection via username argv | `backend/app/enrichers/*.py` |
| V-13 | **Medium** | A03 | HTML injection in transactional email templates | `backend/app/services/email_service.py` |
| V-14 | **Medium** | A05 Misconfiguration | Rate limits keyed on Bearer header while auth is cookie-based → shared anonymous bucket | `backend/app/dependencies/rate_limit.py` |
| V-15 | **Medium** | A01 | LinkedIn sourcing list lacks `linkedin_sourcing:*` permission | `linkedin_sourcing/router.py` |
| V-16 | **Medium** | A08 Integrity | Upload MIME trust without magic-byte sniff | `documents/service.py` |
| V-17 | **Medium** | A02 | `python-jose` + env-configurable `JWT_ALGORITHM` | `pyproject.toml`, `config.py` |
| V-18 | **Medium** | A04 Insecure Design | CSRF: cookie auth + `SameSite=lax`, no CSRF tokens on mutations | `auth/router.py` |
| V-19 | **Low** | A05 | Public `/metrics`; readiness detail leakage | `modules/health/router.py` |
| V-20 | **Low** | A07 | User enumeration on register / resend-verification | `auth/router.py` |

**Positive controls observed:** bcrypt (`rounds=12`); HttpOnly access cookies; refresh rotation + reuse detection; DSAR ownership filter; compliance audit logs hash identifiers; CORS allowlist (not `*`); subprocess enrichers use `create_subprocess_exec` (no `shell=True`); no React `dangerouslySetInnerHTML` XSS surface found.

##### Data Leakage & Exposure

| Area | Status | Notes |
| :--- | :--- | :--- |
| Enrichment `request_payload` | **Exposed residual** | Opt-out/DSAR purge clears `dossier_payload` only — raw email/LinkedIn remain in `request_payload` |
| CV / chat / embeddings | **Cleartext at rest** | `CandidateDocument.raw_text`, `extracted_data`, `CvChatMessage.content`, `DocumentEmbedding.chunk_text` |
| OAuth / MFA / refresh | **Cleartext at rest** | OAuth tokens, `mfa_secret`, refresh token values in DB |
| Logging | **Mixed** | Compliance audit avoids raw PII; email test mode can log full recipient + context; speech DEBUG may log transcription |
| API responses | **Partial** | `/auth/me` exposes `is_superuser`; DSAR access returns full merged dossier (docs claim metadata-only — **drift**) |
| Opt-out check | **Oracle** | Unauthenticated `GET /api/opt-out/check` discloses suppression status |
| BFF cookies | **Fragile** | `Headers.get("set-cookie")` may drop one of dual cookies on login/refresh/impersonation |
| Third-party transfer | **Broad** | CV/contact data → OpenAI/LiteLLM/Gemini, Perplexity, R2, SendGrid, Whisper, LinkedIn/Multilogin |

> **Note:** Local `backend/.env` is gitignored (good). Operators must ensure live secrets never enter commits, CI artifacts, or chat logs. Rotate any key that may have been shared outside vaults.

##### Code Hardening & Strengthening Recommendations

**1. Fail closed on weak secrets (V-02)**

Before:

```python
SECRET_KEY: str = Field(
    default="change-me-in-production-use-openssl-rand-hex-32",
    alias="SECRET_KEY",
)
COOKIE_SECURE: bool = Field(default=False, alias="COOKIE_SECURE")
```

After:

```python
_INSECURE_SECRET_DEFAULTS = {
    "change-me-in-production-use-openssl-rand-hex-32",
    "change-me",
}

def validate_production_secrets(settings: Settings) -> None:
    if settings.app_env not in {"staging", "production"}:
        return
    if settings.SECRET_KEY in _INSECURE_SECRET_DEFAULTS or len(settings.SECRET_KEY) < 32:
        raise RuntimeError("Refusing to start: SECRET_KEY is missing or insecure")
    if settings.api_token in _INSECURE_SECRET_DEFAULTS:
        raise RuntimeError("Refusing to start: API_TOKEN is insecure")
    if not settings.COOKIE_SECURE:
        raise RuntimeError("Refusing to start: COOKIE_SECURE must be True in production")
```

**2. Verify opt-out before purge (V-01)**

Before:

```python
@router.post("/opt-out", status_code=202)
async def create_opt_out(request: SuppressionRequest, db: AsyncSession = Depends(get_db_session)):
    await get_opt_out_service(db).register(request.identifier, request.reason)
    return {"status": "accepted"}
```

After:

```python
@router.post("/opt-out", status_code=202)
async def create_opt_out(request: SuppressionRequest, db: AsyncSession = Depends(get_db_session)):
    # Queue request + send OTP / signed email link; do NOT purge here
    await get_opt_out_service(db).request_opt_out(request.identifier, request.reason)
    return {"status": "verification_required"}

@router.post("/opt-out/confirm")
async def confirm_opt_out(token: str, db: AsyncSession = Depends(get_db_session)):
    await get_opt_out_service(db).confirm_and_purge(token)  # single-use, short TTL
    return {"status": "accepted"}
```

**3. Block superuser impersonation + require MFA (V-03, V-09)**

```python
if target.is_superuser:
    raise HTTPException(403, "Cannot impersonate a superuser")
if not admin.mfa_enabled or not verify_mfa_code(admin, mfa_code):
    raise HTTPException(403, "MFA required for impersonation")
```

**4. SSRF-harden webhooks (V-04)**

```python
from ipaddress import ip_address
from urllib.parse import urlparse

def assert_safe_webhook_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("webhook_url must be https")
    # resolve hostname; reject private/link-local/metadata ranges
    # follow_redirects=False on httpx client
    return url
```

**5. Clear `request_payload` on purge**

```python
job.dossier_payload = {}
job.request_payload = {}  # was missing — residual PII
job.status = JobStatus.purged.value
```

**6. Fix signals fail-open + email test auth**

```python
expected = settings.changedetection_api_key.strip()
if not expected or not hmac.compare_digest(x_signal_token, expected):
    raise UnauthorizedError("invalid signal token")
```

##### Code Optimization & Redundancy Reduction

| Hotspot | Refactor strategy |
| :--- | :--- |
| 100+ BFF `route.ts` files | Shared `createBffProxy({ path, methods, auth })` factory; one cookie-forward helper using `getSetCookie()` |
| Auth login/refresh/impersonation cookie relay | Central `forwardBackendCookies(response)` → `NextResponse.cookies.set` per cookie |
| LinkedIn URL validation | Single `extract_linkedin_slug()` used by Tier-1 scrape **and** sourcing |
| pgvector similarity SQL | One bind-param helper; retire f-string path in `vector_search.py` |
| Enricher argv construction | Shared `sanitize_cli_token(value)` + insert `--` before user values |
| Legacy `API_TOKEN` / `verify_token` | Deprecate or remove; align `LEGAL.md` / `SECURITY_HARDENING.md` with cookie JWT + DSAR behavior |
| Permission checks | Shared decorator inventory; close “verified-only” gaps (recruiter actions, lead list) |

---

### 3. Multi-Jurisdiction Government Data Policy & Regulatory Compliance

**Data inventory (high level):** user accounts (email, name, password hash, MFA), candidate CVs and chat, enrichment dossiers, outreach drafts, LinkedIn-sourced leads, job preferences, practice audio (TTL), auth/admin/compliance audit logs. Processing spans India/US/EU/Brazil user bases potentially; third-party processors include LLM vendors, R2, SendGrid, speech APIs.

**Encryption:** TLS expected at reverse proxy only; **no application field-level encryption**; DB/volume encryption is operator-owned. Passwords use bcrypt. MFA/OAuth/refresh secrets are plaintext in DB.

**Consent:** Enrichment opt-out + CAN-SPAM-style outreach footer exist; **no durable product consent ledger**, **no DPDP Consent Manager**, privacy UI is DSAR-oriented rather than a full notice.

#### Compliance Matrix Table

| Jurisdiction | Law / Regulation | Key Requirement | Status (`Found` / `Not Found`) | Implementation Type (`Direct` / `Indirect` / `Not Found`) | Official Legal / Gov Citation | Codebase Gap & Fix |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **India** | DPDP Act 2023 | Lawful purpose limitation & processing only for stated purposes | `Not Found` | `Not Found` | *Digital Personal Data Protection Act, 2023, Section 4* | Add purpose register + processing records; bind each module (enrichment, outreach, LLM) to recorded purposes |
| **India** | DPDP Act 2023 | Notice to Data Principal before/at collection | `Not Found` | `Not Found` | *DPDP Act 2023, Section 5* | Ship privacy notice covering categories, purposes, rights, cross-border transfers; capture acknowledgment timestamp |
| **India** | DPDP Act 2023 | Consent for processing (free, specific, informed, unconditional, clear) | `Not Found` | `Not Found` | *DPDP Act 2023, Section 6(1)* | Implement Consent Manager integration or first-party consent ledger with withdrawability |
| **India** | DPDP Act 2023 | Right to correction & erasure | `Found` | `Indirect` | *DPDP Act 2023, Section 12(1)* | Opt-out + DSAR + soft account delete exist but purge is incomplete (`request_payload`, CV/outreach/leads). Extend cascade erasure |
| **India** | DPDP Act 2023 | Security safeguards / Data Fiduciary obligations | `Found` | `Indirect` | *DPDP Act 2023, Section 8(5)* | Auth, hashing, rate limits present; add prod secret fail-fast, field encryption for MFA/OAuth, verified opt-out |
| **India** | DPDP Rules (draft/operational) | Significant Data Fiduciary / DPO appointment where applicable | `Not Found` | `Not Found` | *DPDP Act 2023, Section 10* (SDF designation by Central Government) | Appoint DPO if designated; document contact in privacy notice |
| **USA** | CCPA / CPRA | Right to know / access personal information | `Found` | `Indirect` | *Cal. Civ. Code § 1798.110, § 1798.100* | DSAR access exists; expand to full PI categories (CV, outreach, leads), not enrichment-only |
| **USA** | CCPA / CPRA | Right to delete | `Found` | `Indirect` | *Cal. Civ. Code § 1798.105* | Fix purge residual PII; cascade delete across product tables; verify service-provider deletion with LLM/R2/SendGrid |
| **USA** | CCPA / CPRA | Right to opt-out of sale/sharing | `Found` | `Indirect` | *Cal. Civ. Code § 1798.120; § 1798.140(ad)/(ah)* | Enrichment opt-out exists; clarify “sale/share” posture for analytics/ads; honor GPC if advertising added |
| **USA** | CCPA / CPRA | Security of personal information | `Found` | `Indirect` | *Cal. Civ. Code § 1798.150* (reasonable security) | Close Critical auth/SSRF/default-secret issues to meet “reasonable security” |
| **USA** | FTC Act | Unfair/deceptive practices — accurate privacy claims | `Found` | `Indirect` | *15 U.S.C. § 45* | Align public docs with code (DSAR dossier return, purge scope) |
| **USA** | CAN-SPAM | Accurate header, physical address, unsubscribe for commercial email | `Found` | `Direct` | *15 U.S.C. §§ 7701–7713; 16 CFR Part 316* | Outreach footer + physical address config validation present; ensure transactional vs commercial classification is documented |
| **USA** | HIPAA | PHI safeguards / BAA | `Not Found` | `Not Found` | *45 CFR Parts 160 & 164* | N/A unless health data collected; if ever in scope, segregate PHI + BAAs — currently no HIPAA controls |
| **EU** | GDPR | Lawful basis for processing | `Not Found` | `Not Found` | *Regulation (EU) 2016/679, Art. 6(1)* | Record lawful basis per processing activity (consent / contract / legitimate interest with LIA) |
| **EU** | GDPR | Transparency / privacy notice | `Found` | `Indirect` | *GDPR Arts. 12–14* | `LEGAL.md` + partial privacy UI; need end-user Art. 13/14 notice in product |
| **EU** | GDPR | Data subject access | `Found` | `Direct` | *GDPR Art. 15* | DSAR access endpoint; broaden data categories returned |
| **EU** | GDPR | Right to erasure (“right to be forgotten”) | `Found` | `Indirect` | *GDPR Art. 17* | Incomplete purge + soft-delete-only account — must hard-delete / anonymize all copies including processors |
| **EU** | GDPR | Security of processing | `Found` | `Indirect` | *GDPR Art. 32(1)* | Implement encryption at rest for sensitive fields, harden auth, MFA for privileged ops, vulnerability fixes |
| **EU** | GDPR | Breach notification (72h to SA) | `Not Found` | `Not Found` | *GDPR Arts. 33–34* | Add incident response runbook + detection/alerting; no in-repo breach workflow |
| **EU** | GDPR | International transfers | `Not Found` | `Not Found` | *GDPR Arts. 44–49* | Document SCCs/DPAs for OpenAI, R2, SendGrid, etc.; TIAs for high-risk tools |
| **EU** | GDPR | Processor contracts | `Not Found` | `Not Found` | *GDPR Art. 28* | Execute/store DPAs; map subprocessors |
| **Brazil** | LGPD | Legal basis for processing | `Not Found` | `Not Found` | *Law No. 13.709/2018, Art. 7* | Map each processing activity to Art. 7 basis; store consent evidence where consent is used |
| **Brazil** | LGPD | Data subject rights (access, deletion, etc.) | `Found` | `Indirect` | *LGPD Art. 18* | Same DSAR/opt-out gaps as GDPR/DPDP; localize Portuguese notice if targeting BR users |
| **Brazil** | LGPD | Security / technical measures | `Found` | `Indirect` | *LGPD Art. 46* | Same hardening backlog as Art. 32 GDPR |
| **Brazil** | LGPD | Communication of security incidents | `Not Found` | `Not Found` | *LGPD Art. 48* | Define ANPD notification playbook |
| **Brazil** | LGPD | DPO (encarregado) appointment | `Not Found` | `Not Found` | *LGPD Art. 41* | Appoint/encarregado contact in privacy notice |

---

### 4. Infrastructure, Network & API Hardening

##### CORS Configuration

| Setting | Observed | Assessment |
| :--- | :--- | :--- |
| Origins | `CORS_ALLOWED_ORIGINS` → parsed list; fallback `FRONTEND_URL` / localhost | **Good** if ops sets exact origins; risk if wildcard/`null` added |
| Credentials | `allow_credentials=True` | Correct with explicit origins (never `*`) |
| Methods | GET, POST, PUT, PATCH, DELETE, OPTIONS | Appropriate |
| Headers | `Authorization`, `Content-Type` | Tight; ensure custom headers (e.g. MFA/`X-Signal-Token` from browsers) are intentional |
| Preflight cache | `max_age=600` | Fine |

**Recommendation:** Reject empty/`null` origin; CI check that production env sets non-localhost allowlist; document admin vs app origins separately.

##### Rate Limiting & DDoS Protection

| Control | Status | Gap |
| :--- | :--- | :--- |
| Redis sliding-window limits | Present (auth, compliance, documents upload, outreach send, impersonation) | Cookie sessions often lack Bearer → fall into shared `"anonymous"` bucket |
| Redis outage behavior | Fail-open | Prefer fail-closed for auth/compliance scopes |
| `/auth/refresh` | **Not rate-limited** | Add limit |
| Edge DDoS | Not in app code | Rely on CDN/WAF (Cloudflare etc.) — document required |
| Opt-out / DSAR | Compliance rate limit | Keep; add verification before purge |

##### Environment & Secrets Handling

| Item | Finding |
| :--- | :--- |
| Hardcoded defaults | `SECRET_KEY`, `API_TOKEN=change-me`, GlitchTip default in compose |
| `.env.example` | Documents weak placeholders (expected for templates; dangerous if copied verbatim) |
| `SecretStr` usage | Partial (SendGrid, R2, OAuth secret) — JWT secret is plain `str` |
| Docker | `API_TOKEN` defaults to `change-me`; JWT `SECRET_KEY` may be omitted → code default |
| Local `.env` | Gitignored — verify never committed; rotate if historically exposed |
| Third-party keys | OpenAI, Gemini, Langfuse, AWS, SendGrid, ChangeDetection — vault/KMS in prod |

---

### 5. Actionable Implementation Checklist (Pre-Merge & Pre-Deployment)

#### P0 — Critical (block production merge/deploy)

- [ ] **Refuse startup** in staging/production when `SECRET_KEY` / `API_TOKEN` are defaults or short; rotate any deployed default JWTs
- [ ] **Opt-out verification** (OTP / signed link) before purge; stop anonymous destructive erasure
- [ ] **Purge completeness:** clear `jobs.request_payload`; cascade to CVs, chat, embeddings, outreach, sourced leads where legally required
- [ ] **Block impersonation of `is_superuser`**; require MFA for all impersonation starts
- [ ] **SSRF harden** `webhook_url` (HTTPS-only, deny private IPs, no redirects, validate on write)
- [ ] **Signals webhook fail-closed** when `CHANGEDETECTION_API_KEY` empty; constant-time compare
- [ ] **Fix `/api/email/test` auth** (real header check or superuser-only; disable in production)
- [ ] Set **`COOKIE_SECURE=True`** (and enforce) in staging/production

#### P1 — High (fix before broad user rollout)

- [ ] Hash refresh tokens at rest; **revoke all refresh tokens** on account delete / password change
- [ ] RBAC on **recruiter actions** and **LinkedIn sourcing list**
- [ ] Forbid suspending superusers without stricter gate
- [ ] Encrypt MFA secrets (and preferably OAuth tokens) at rest
- [ ] Escape all dynamic HTML in email templates; allowlist `href` schemes
- [ ] Fix BFF **multi-Set-Cookie** relay (`getSetCookie` + centralized helper)
- [ ] Rate-limit `/auth/refresh`; key limits on `user.id` / IP for cookie clients
- [ ] Align **LEGAL.md / SECURITY_HARDENING.md** with actual DSAR & purge behavior
- [ ] Execute **DPAs/SCCs** for LLM, R2, SendGrid; document subprocessors

#### P2 — Medium (harden within next sprint)

- [ ] Bind-parameterize `vector_search.py` SQL
- [ ] Sanitize enricher CLI args; reject leading `-`
- [ ] Magic-byte upload sniffing; stricter LinkedIn URL normalization for sourcing
- [ ] CSRF tokens or `SameSite=strict` for sensitive cookies; trusted-proxy config for XFF
- [ ] Migrate off `python-jose` → **PyJWT**; hardcode `HS256`
- [ ] Privacy notice + consent ledger (DPDP §5–6 / GDPR Arts. 12–14 / LGPD Art. 7–8)
- [ ] Breach notification runbook (GDPR 33–34 / LGPD 48)
- [ ] Protect `/metrics`; uniform auth error messages (anti-enumeration)
- [ ] Collapse BFF boilerplate; remove dead `verify_token` path
- [ ] Review `frontend/audit-ci.jsonc` allowlist; run `pip-audit` / `npm audit` in CI

---

### Appendix A — Related Internal Artifacts

- `backend/docs/LEGAL.md`
- `docs/SECURITY_HARDENING.md`
- `docs/adr/0004-public-compliance-apis.md`
- `docs/adr/0005-suppression-sql-redis-dual-store.md`
- `docs/adr/0009-cookie-oauth-authentication.md`
- `docs/adr/0015-admin-module-rbac-audit-mfa.md`

### Appendix B — Disclaimer

This report is based on static analysis of branch `master-complete-foundation` at commit `9e1623c` on 2026-08-26. It is not a penetration test, legal opinion, or certification of compliance. Regulatory citations are for engineering gap analysis; counsel should validate applicability for each deployment region and data category.
