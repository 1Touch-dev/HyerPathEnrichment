# Dependency audit verification (Task 4)

**Date:** 2026-07-20  
**Branch:** `chore/dependency-vulnerability-scanning-4`  
**Result:** PASS (local checks; CI pending on PR)

## What was added

| Component | Path / job |
|-----------|------------|
| Dependabot | [`.github/dependabot.yml`](../.github/dependabot.yml) — pip (`backend/`), npm (`frontend/`), GitHub Actions |
| CI gate | `.github/workflows/ci.yml` → `dependency-audit` job (blocks `docker-smoke`) |
| Local entrypoint | `make audit` → [`scripts/dependency_audit.sh`](../scripts/dependency_audit.sh) |
| Python scanner | `pip-audit` in `backend[dev]` |
| Frontend scanner | `audit-ci` + `npm audit` (high/critical) in `frontend/` |

**Audit threshold:** high + critical (npm via `audit-ci`; pip-audit fails on any known CVE except documented exceptions).

## Commands run

```bash
bash -n scripts/dependency_audit.sh                    # syntax check
cd frontend && npm run audit:ci                        # frontend gate
python -m pip install -e "backend[dev]" -q
python -m pip_audit --desc on --progress-spinner off     # dev deps
python -m pip install -e "backend[enrichers]" -q
python -m pip_audit --ignore-vuln PYSEC-2026-1604      # enrichers (see exceptions)
cd frontend && npm run typecheck && npm run build
```

## Results

| Check | Exit | Notes |
|-------|------|-------|
| A1 Dependabot YAML | PASS | 3 ecosystems configured |
| A2 Script syntax (`bash -n`) | PASS | LF line endings required |
| A3 `pip-audit` in `backend[dev]` | PASS | Installed via editable dev extra |
| B1 `npm run audit:ci` | PASS | next 14.2.35 baseline + audit-ci |
| B2 pip-audit `[dev]` | PASS | No known vulnerabilities |
| B3 pip-audit `[enrichers]` | PASS | With `PYSEC-2026-1604` ignore (see below) |
| B4 Frontend typecheck + build | PASS | Next.js 14.2.35 |
| C1 npm negative test | PASS | `lodash@4.17.20` → `npm audit --audit-level=high` exit 1 |
| C2 pip negative test | PASS | `urllib3==1.26.5` → `pip-audit` exit 1, 10 CVEs |
| D1–D3 CI | PENDING | Record GHA run URL after PR push |

## Dependency fixes in this PR

| Package | Change | Reason |
|---------|--------|--------|
| `next` | 14.2.5 → 14.2.35 | Patched Dec 2025 RSC CVEs ([security update](https://nextjs.org/blog/security-update-2025-12-11)) |
| `openapi-typescript` | 6.x → 7.13.0 | Removes vulnerable `undici` transitive dep |
| `pytest` | `>=8.2` → `>=9.0.3` | PYSEC-2026-1845 |
| `audit-ci` | added (dev) | npm audit gate with allowlist for stale next advisories |

## Documented exceptions

### npm — Next.js advisory lag (`frontend/audit-ci.jsonc`)

npm audit reports high findings for `next@14.2.35` with fix version `16.2.10` only. We pin **14.2.35** (latest 14.2.x per Next.js security advisories) and enforce via `frontend/scripts/verify-next-version.mjs`. Remaining next GHSA IDs are allowlisted until a planned Next 15+ upgrade.

### pip — markdownify (`PYSEC-2026-1604`)

`python-jobspy` (enrichers extra) requires `markdownify<0.14.0`. Ignored in enrichers audit pass only; tracked until jobspy updates.

## Out of scope

- Docker sidecar images that `git clone` + build Go/Node deps inside Dockerfiles (no lockfile in this repo).
- Moderate npm findings in nested `postcss` bundled by Next 14 (below high gate).

## Post-merge checklist (repo admin)

- [ ] GitHub → Settings → Code security → enable **Dependabot alerts**
- [ ] Enable **Dependabot security updates** (optional; complements `dependabot.yml`)
- [ ] Within 24–48h: confirm Dependabot shows pip + npm ecosystems
- [ ] Add `dependency-audit` as required status check on `main` (branch protection)

## CI evidence

_Update after PR CI completes:_

- PR: _(fill on push)_
- GHA `dependency-audit` run: _(fill on push)_
