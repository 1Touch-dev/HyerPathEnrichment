# Multi-Orch Master Decision Register

- Date: 2026-09-04
- Coordinator: ORCH-ROOT
- Baseline: `R2-BASELINE-2026-09-04`
- Scope: Wave 1 synthesis plus Wave 2 execution authority for `wave2-impl`

## Program status

All Wave 1 packets remain the backing evidence, and the required owner decisions were
supplied directly in the main session for this Wave 2 run. For this execution, the
decisions below are treated as approved and authorize Wave 2 implementation work without
changing the plan file itself.

## Decision register

| Decision ID | Current status | Exact owner(s) | Required review | Evidence / packet to review | Recommended option from packet | Implementation tasks unlocked if approved | What remains blocked if unanswered |
|---|---|---|---|---|---|---|---|
| `DEC-COMMIT-AUTH` | `APPROVED FOR THIS RUN` | Human release owner | `ORCH-ROOT` | `docs/audits/multi-orch/orch-root-wave1-g1-readiness-brief-2026-09-04.md`; `/home/axiz/.cursor/plans/multi-orch_blocker_resolution_e17125d7.plan.md` | Authorize the planned atomic Round 2 commit groups after targeted Wave 2 evidence is captured | `R2-COMMIT-EXEC-001`; immutable RC creation path needed before later live evidence | Later live evidence still depends on implementation quality, review, and Wave 3 environment evidence |
| `DEC-T4-SETUP` | `APPROVED FOR THIS RUN` | Infra human owner + QA human owner | Security human reviewer | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `docs/audits/multi-orch/orch-qa-wave1-packet-2026-09-04.md` | Reuse `create_test_user.py` plus real HTTP login in a non-production environment only, with hard production fail-closed controls and explicit superuser exception handling | `AUTH-SETUP-001`; `T4-LIVE-001`; live D002 and ADR21 T4 cases | Live auth setup still depends on a running non-production backend and later live execution evidence |
| `DEC-ADR21-SURFACE` | `APPROVED FOR THIS RUN` | Security human owner + Product human owner | `ORCH-SECURITY`; receiving Product review | `docs/audits/multi-orch-adr21-wave1-decision-packet-2026-09-04.md` | One explicit privileged-operation catalog covering Desk/admin mutations, mapped to `P1`/`P2`/`P3`/`UNAVAILABLE`, with unmapped operations fail-closed and `P4` still unavailable | `ADR21-IMPL-001`; `ADR21-TEST-001` through `ADR21-TEST-008` | Residual implementation gaps can still keep `BLK-SEC-001` and `G2` open until fully remediated and reviewed |
| `DEC-D002-PRECEDENCE` | `APPROVED FOR THIS RUN` | Product human owner | Security human reviewer | `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md` | Permission-centric model: backend permission pairs are authoritative, `is_superuser` override stays, `role_name` alone is never sufficient, and Brand/owner semantics never act as tenancy or ACL overrides | `D002-IMPL-001`; `D002-TEST-001` through `D002-TEST-005` | Residual FE/BE permission-boundary drift can still keep `BLK-PROD-002` open until corrected |
| `DEC-PILOT-ACCEPT` | `APPROVED FOR LATER WAVE 3` | Product human owner + Infra human owner | `ORCH-INFRA` | `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`; `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md` | Restricted internal pilot only, using RBAC-based cohort control, with explicit acknowledgement of current v1 limits and honest monitoring evidence labeling | `PILOT-DEPLOY-001` | Live pilot evidence remains deferred to Wave 3 |
| `DEC-ROLLBACK-ACCEPT` | `APPROVED FOR LATER WAVE 3` | Infra human owner + Product human owner | `ORCH-INFRA` | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `/home/axiz/.cursor/plans/multi-orch_blocker_resolution_e17125d7.plan.md` | Accept rollback only under ADR 0021 stop-the-world rules for schema `065+`; never run an older pre-hardening API against that schema; if incompatible, treat it as restore/roll-forward rather than casual downgrade | `ROLLBACK-LIVE-001` | Rollback rehearsal remains deferred to Wave 3 |

## Wave 2 decision gate summary

For this run, the decision dependencies required to start `wave2-impl` are resolved:

1. `DEC-COMMIT-AUTH`
2. `DEC-T4-SETUP`
3. `DEC-ADR21-SURFACE`
4. `DEC-D002-PRECEDENCE`

`DEC-PILOT-ACCEPT` and `DEC-ROLLBACK-ACCEPT` remain approved but deferred in use:
they do not gate Wave 2 code-writing, but they are still prerequisites for later
Wave 3 live pilot and rollback evidence.

## ORCH-ROOT conclusion

The decision landscape remains packet-backed, and this register now records the
main-session approvals used to authorize Wave 2 execution for this run. Remaining
blockers are implementation and live-evidence gaps, not unresolved owner decisions.
