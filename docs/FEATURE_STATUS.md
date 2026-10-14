# HyrePath — Feature Status Tracker

**Date:** 2026-10-14
**Sources:**

- Notion (HyrePath workspace): [HyrePath Platform — Product Feature Catalog](https://app.notion.com/p/3e31d1b2b75a81bd9c8fc6f1a3224bad) (validated 22 Sep 2026)
- Notion: [HyrePath Feature Brief](https://app.notion.com/p/3d41d1b2b75a81fd81b1d7f485823d61)
- Operator phase status export: `hyepath` (2026-10-12)
- Operator updates (2026-10-14): CI/CD, Google OAuth, Perplexity, Stripe, Multilogin

**Legend:** ✅ Completed · ⏳ Pending · 🔧 Needs fix · ⚠️ Partial

---

## Operator / go-live checklist

| Item | Status | Notes |
|------|--------|-------|
| Deploy on AWS EC2 | ✅ Completed | Day-1 stack: API, workers, sidecars, observability, Next.js frontend |
| Elastic IP | ✅ Completed | Stable public address attached |
| Phase 2 candidate platform (code) | ✅ Completed | Job matching, swipe, CV, portfolio, outreach, interview, applications, scheduling, desk |
| GitHub CI/CD | ✅ Completed | Deploy workflow and host CD configured |
| Perplexity subscription / API | ✅ Completed | Outreach company research key available |
| Stripe integration | ✅ Completed | Billing provider wired (checkout / portal) |
| Google OAuth integration | ✅ Completed | Sign-in with Google integrated end-to-end |
| Google verification | ⏳ Pending | OAuth app / brand verification with Google still open |
| Stripe business verification | ⏳ Pending | Stripe account business verification still open |
| Multilogin | 🔧 Needs fix | Day-1 leaves Multilogin / `worker-tier1` off; must be fixed before Tier-1 photo path is live |
| Purchase / configure domain | ⏳ Pending | Target e.g. `enrich.hyrepath.io`; HTTPS / cookies need real DNS |
| DNS configuration | ⏳ Pending | Point DNS at Elastic IP; Let's Encrypt; update public URLs |
| Live / pilot testing | ⏳ Pending | Full product-door pilot over real HTTPS still open |

---

## 1. HP-PLT — Access and accounts

| ID | Feature | Status |
|----|---------|--------|
| HP-PLT-01 | Register and sign in | ✅ Completed |
| HP-PLT-02 | Email verification | ✅ Completed |
| HP-PLT-03 | Unified session (Candidate / Desk / OSINT) | ✅ Completed |
| HP-PLT-04 | Profile and settings | ✅ Completed |
| HP-PLT-05 | Account deletion | ✅ Completed |
| HP-PLT-06 | Staff invite redemption | ✅ Completed |
| — | Google OAuth sign-in | ✅ Completed |
| — | Google OAuth / brand verification | ⏳ Pending |

---

## 2. HP-CAN — Candidate career app

### Curriculum vitae and documents

| ID | Feature | Status |
|----|---------|--------|
| HP-CAN-01 | CV and document upload | ✅ Completed |
| HP-CAN-02 | Structured CV extraction | ✅ Completed |
| HP-CAN-03 | Completeness check | ✅ Completed |
| HP-CAN-04 | Guided CV completion (chat) | ✅ Completed |
| HP-CAN-05 | AI CV improvement | ✅ Completed |
| HP-CAN-06 | Document search | ✅ Completed |
| HP-CAN-07 | Document management | ✅ Completed |

### Job matching and discovery

| ID | Feature | Status |
|----|---------|--------|
| HP-CAN-08 | Job preferences | ✅ Completed |
| HP-CAN-09 | Job market scan | ✅ Completed |
| HP-CAN-10 | Ranked matches with explanations | ✅ Completed |
| HP-CAN-11 | Match feedback | ✅ Completed |
| HP-CAN-12 | Apply to listing | ✅ Completed |
| HP-CAN-13 | Match notifications (email / push) | ✅ Completed |
| HP-CAN-13b | Match notifications (SMS) | ⚠️ Partial — stub; not implemented |
| HP-CAN-14 | Swipe discovery | ✅ Completed |

### Applications and interviews

| ID | Feature | Status |
|----|---------|--------|
| HP-CAN-15 | Application tracker | ✅ Completed |
| HP-CAN-16 | Manual job entry | ✅ Completed |
| HP-CAN-17 | Interview scheduling (+ `.ics`) | ✅ Completed |
| HP-CAN-18 | Interview reminders | ✅ Completed |

### Interview practice

| ID | Feature | Status |
|----|---------|--------|
| HP-CAN-20 | Practice sessions | ✅ Completed |
| HP-CAN-21 | Job-specific (JD-aware) practice | ✅ Completed |
| HP-CAN-22 | Personalized questions from résumé | ✅ Completed |
| HP-CAN-23 | Answer feedback (rubric) | ✅ Completed |
| HP-CAN-24 | Spoken practice (Whisper, pace, fillers) | ✅ Completed |
| HP-CAN-25 | Practice report | ✅ Completed |
| — | Optional voice-tone signal writer | ⚠️ Partial — column/UI exist; no backend writer |

### Portfolio, outreach, and membership

| ID | Feature | Status |
|----|---------|--------|
| HP-CAN-26 | Portfolio builder | ✅ Completed |
| HP-CAN-27 | Public portfolio page | ✅ Completed |
| HP-CAN-28 | Assisted outreach drafting (Perplexity context) | ✅ Completed |
| HP-CAN-29 | Staff-assisted LinkedIn send | ✅ Completed |
| HP-CAN-30 | Optional premium membership (Stripe) | ✅ Completed |
| — | Stripe business verification | ⏳ Pending |

---

## 3. HP-OSI — Public-information research (OSINT)

| ID | Feature | Status |
|----|---------|--------|
| HP-OSI-01 | Identifier intake | ✅ Completed |
| HP-OSI-02 | Research depth selection | ✅ Completed |
| HP-OSI-03 | Professional photo capture | 🔧 Needs fix — Multilogin / Tier-1 path broken / off |
| HP-OSI-04 | Social handle discovery | ✅ Completed |
| HP-OSI-05 | Email and professional intelligence | ✅ Completed |
| HP-OSI-06 | Jobs and local business lookup | ✅ Completed |
| HP-OSI-07 | Live research jobs | ✅ Completed |
| HP-OSI-08 | Unified dossier | ✅ Completed |
| HP-OSI-09 | Suppression-aware research | ✅ Completed |

---

## 4. HP-DSK — Staff operations (Desk)

### Placement work

| ID | Feature | Status |
|----|---------|--------|
| HP-DSK-01 | Sourcing leads | ✅ Completed |
| HP-DSK-02 | LinkedIn send tasks | ✅ Completed |
| HP-DSK-03 | Demand intelligence | ✅ Completed |
| HP-DSK-04 | AI action oversight | ✅ Completed |

### Content moderation

| ID | Feature | Status |
|----|---------|--------|
| HP-DSK-05 | Review queue | ✅ Completed |
| HP-DSK-06 | Job posting moderation | ✅ Completed |
| HP-DSK-07 | Document moderation | ✅ Completed |
| HP-DSK-08 | Portfolio moderation | ✅ Completed |
| HP-DSK-09 | Outreach moderation | ✅ Completed |

### People, access, and brands

| ID | Feature | Status |
|----|---------|--------|
| HP-DSK-10 | User directory (+ assisted session) | ✅ Completed |
| HP-DSK-11 | Roles and permissions (RBAC) | ✅ Completed |
| HP-DSK-12 | Staff invitations | ✅ Completed |
| HP-DSK-13 | Staff audit log | ✅ Completed |
| HP-DSK-14 | Brand storefronts | ✅ Completed |

### Platform operations

| ID | Feature | Status |
|----|---------|--------|
| HP-DSK-15 | System health | ✅ Completed |
| HP-DSK-16 | Background work queues | ✅ Completed |
| HP-DSK-17 | Analytics | ✅ Completed |
| HP-DSK-18 | Change signals | ✅ Completed |

---

## 5. HP-PUB — Public and marketing surfaces

| ID | Feature | Status |
|----|---------|--------|
| HP-PUB-01 | Marketing hub | ✅ Completed |
| HP-PUB-02 | Audience landings | ✅ Completed |
| HP-PUB-03 | Brand landing pages | ✅ Completed |
| HP-PUB-04 | Published portfolios | ✅ Completed |
| HP-PUB-05 | Public opt-out | ✅ Completed |

---

## 6. HP-SEC — Trust, privacy, and security

| ID | Feature | Status |
|----|---------|--------|
| HP-SEC-01 | Permanent opt-out | ✅ Completed |
| HP-SEC-02 | Data subject requests | ✅ Completed |
| HP-SEC-03 | Public-data boundary | ✅ Completed |
| HP-SEC-04 | Multi-factor authentication (TOTP) | ✅ Completed |
| HP-SEC-05 | Role-based access | ✅ Completed |
| HP-SEC-06 | Audit trails | ✅ Completed |

---

## 7. Integrations

| Capability | Status | Notes |
|------------|--------|-------|
| Enrichment API | ✅ Completed | Same suppression rules as console |
| Email notifications | ✅ Completed | Match digests / interview reminders when configured |
| Web push | ✅ Completed | Optional; when push is configured |
| Calendar files (`.ics`) | ✅ Completed | Interview appointments |
| Perplexity (outreach research) | ✅ Completed | API key / subscription in place |
| Payments (Stripe) | ✅ Completed | Integration done |
| Stripe business verification | ⏳ Pending | Required before treating billing as fully live |
| Google OAuth | ✅ Completed | Integrated |
| Google verification | ⏳ Pending | App / brand verification still open |
| Change detection | ✅ Completed | Monitored page change signals |
| GitHub CI/CD | ✅ Completed | Deploy path configured |
| Multilogin (Tier-1 browser) | 🔧 Needs fix | Broken; keep Tier-1 off until fixed |

---

## Remaining open (summary)

1. **Google verification** — OAuth integrated; Google’s verification still pending
2. **Stripe business verification** — Stripe integration done; business verification still pending
3. **Multilogin** — must be fixed before enabling Tier-1 / LinkedIn photo capture in prod
4. **Domain + DNS** — real domain, Let's Encrypt, public URL cutover
5. **Live / pilot testing** — end-to-end pilot over real HTTPS
6. **Known product gaps** — SMS match digest stub; voice-tone practice signal writer; drag-and-drop kanban / two-way Google Calendar sync are later enhancements

---

## Related Notion pages

| Doc | URL |
|-----|-----|
| Product Feature Catalog | https://app.notion.com/p/3e31d1b2b75a81bd9c8fc6f1a3224bad |
| Feature Brief | https://app.notion.com/p/3d41d1b2b75a81fd81b1d7f485823d61 |
| Feature Specs (Evidence-Backed) | https://app.notion.com/p/3d41d1b2b75a81228a9cc30c88cf8779 |
| HyrePath HQ | https://app.notion.com/p/3d41d1b2b75a81f899d2d51e81558b6b |
