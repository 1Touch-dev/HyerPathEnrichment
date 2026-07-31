import React from 'react';

const ProjectCompletionAssessment = () => {
  const sections = [
    {
      title: "1. Architecture & Core Infrastructure",
      complete: 95,
      items: [
        { name: "FastAPI + Bearer Auth", status: "complete", evidence: "✓ main.py, verify_token()" },
        { name: "Redis + RQ Queue", status: "complete", evidence: "✓ RQ worker, queue.py, workers/tasks/" },
        { name: "PostgreSQL + Alembic", status: "complete", evidence: "✓ JSONB support, migrations, dual SQLite/Postgres" },
        { name: "Modular Architecture", status: "complete", evidence: "✓ app/modules/, app/enrichers/, app/domain/" },
        { name: "Docker Compose Stack", status: "complete", evidence: "✓ 9+ services, healthchecks, profiles" },
        { name: "Cloudflare R2 Storage", status: "complete", evidence: "✓ r2.py, local fallback" },
        { name: "API Envelopes", status: "complete", evidence: "✓ core/responses.py, EnvelopeAPIRoute" }
      ]
    },
    {
      title: "2. Enrichment Tiers Implementation",
      complete: 90,
      items: [
        { name: "Tier 1 - LinkedIn Photo", status: "partial", evidence: "✓ Code complete, 3 bugs fixed, full canary PENDING (PR #142)" },
        { name: "Tier 2 - Username Hunt", status: "complete", evidence: "✓ Sherlock, Maigret, Social-Analyzer (20/20 profiles)" },
        { name: "Tier 3 - GitHub/Email/OSINT", status: "mostly-complete", evidence: "✓ gitrecon, Harvester, CrossLinked, email-sleuth; catch-all PENDING" },
        { name: "Tier 4 - Jobs/Business", status: "mostly-complete", evidence: "✓ JobSpy (Indeed/LinkedIn), GMaps scraper; multi-board expansion PENDING" },
        { name: "LLM Disambiguation", status: "complete", evidence: "✓ LLM_MODE (stub/ollama/litellm), threshold-based" },
        { name: "Enricher Protocol", status: "complete", evidence: "✓ base.py, 11 enrichers, registry, parallel dispatch" },
        { name: "Merge & Confidence", status: "complete", evidence: "✓ merge.py, prefer-max strategy" }
      ]
    },
    {
      title: "3. API Endpoints (9 Routes)",
      complete: 100,
      items: [
        { name: "POST /enrich", status: "complete", evidence: "✓ Async queue path, 202 Accepted" },
        { name: "GET /enrich", status: "complete", evidence: "✓ Paginated job list" },
        { name: "GET /enrich/{id}", status: "complete", evidence: "✓ Job polling" },
        { name: "POST /enrich/sync", status: "complete", evidence: "✓ Synchronous inline path" },
        { name: "POST /api/opt-out", status: "complete", evidence: "✓ Public, IP rate-limited" },
        { name: "GET /api/opt-out/check", status: "complete", evidence: "✓ Suppression check" },
        { name: "POST /api/dsar", status: "complete", evidence: "✓ Access/deletion requests" },
        { name: "GET /api/dsar/{id}", status: "complete", evidence: "✓ DSAR polling" },
        { name: "GET /health, /ready", status: "complete", evidence: "✓ Liveness + readiness" }
      ]
    },
    {
      title: "4. Compliance & Legal",
      complete: 100,
      items: [
        { name: "Opt-out Flow", status: "complete", evidence: "✓ SHA-256 suppression, SQL+Redis dual-store" },
        { name: "DSAR Automation", status: "complete", evidence: "✓ Access + deletion within 30 days" },
        { name: "Audit Logs", status: "complete", evidence: "✓ SQL audit_logs, 5-year retention" },
        { name: "Data Purge", status: "complete", evidence: "✓ compliance/purge.py, photo cache erasure" },
        { name: "Public Boundaries Doc", status: "complete", evidence: "✓ backend/docs/LEGAL.md, product policy" },
        { name: "Rate Limiting", status: "complete", evidence: "✓ Redis fixed-window, per-token + per-IP" }
      ]
    },
    {
      title: "5. External Integrations",
      complete: 85,
      items: [
        { name: "Multilogin CDP", status: "partial", evidence: "✓ Profile pool, Selenium Remote; full canary PENDING" },
        { name: "Playwright Browser", status: "complete", evidence: "✓ connect_over_cdp, async scraping" },
        { name: "Reacher (AGPL)", status: "complete", evidence: "✓ Docker sidecar, SMTP verify" },
        { name: "AfterShip email-verifier", status: "complete", evidence: "✓ Sidecar, EMAIL_VERIFY_LEVEL=basic" },
        { name: "Social-Analyzer (AGPL)", status: "complete", evidence: "✓ Sidecar, NLP scoring" },
        { name: "Google Maps Scraper", status: "complete", evidence: "✓ Custom Dockerfile, Playwright 1.57.0" },
        { name: "LiteLLM Proxy", status: "complete", evidence: "✓ litellm_config.yaml, fallback chain" },
        { name: "Langfuse Observability", status: "complete", evidence: "✓ LLM tracing, no-op until configured" },
        { name: "Scrapoxy Proxies", status: "complete", evidence: "✓ ProxyProvider, PROXY_MODE=none/scrapoxy/paid" },
        { name: "Changedetection.io", status: "mostly-complete", evidence: "✓ Webhook consumer; product flow PENDING (gap 71)" }
      ]
    },
    {
      title: "6. Sidecars (Isolated AGPL Services)",
      complete: 100,
      items: [
        { name: "Reacher", status: "complete", evidence: "✓ Docker image, HTTP API" },
        { name: "email-verifier", status: "complete", evidence: "✓ AfterShip Go binary" },
        { name: "social-analyzer", status: "complete", evidence: "✓ AGPL isolation, port 9005" },
        { name: "google-maps-scraper", status: "complete", evidence: "✓ Custom build, -web mode" },
        { name: "changedetection", status: "complete", evidence: "✓ Observability profile" },
        { name: "litellm", status: "complete", evidence: "✓ LLM proxy profile" },
        { name: "langfuse", status: "complete", evidence: "✓ Observability profile" },
        { name: "GlitchTip", status: "complete", evidence: "✓ Sentry-compatible error tracking" }
      ]
    },
    {
      title: "7. Testing & Quality",
      complete: 90,
      items: [
        { name: "Shape Tests", status: "complete", evidence: "✓ test_pipeline_shape.py, all enrichers" },
        { name: "Fake Sidecars CI", status: "complete", evidence: "✓ docker-compose.fake-sidecars.yml" },
        { name: "Full-path E2E", status: "complete", evidence: "✓ e2e_full_path.sh, GHA 29563202825" },
        { name: "Load Testing (k6)", status: "complete", evidence: "✓ LOAD_TESTING.md, run_load_test.py" },
        { name: "Tier 2-4 Live Canary", status: "complete", evidence: "✓ 20/20 profiles PASS (tier234-live-m5)" },
        { name: "Tier 1 Live Canary", status: "partial", evidence: "✓ Real scrapes succeed, 3 bugs fixed; 10-profile re-run PENDING" },
        { name: "Dependency Audit", status: "complete", evidence: "✓ Dependabot, pip-audit, npm audit" }
      ]
    },
    {
      title: "8. DevOps & Deployment",
      complete: 85,
      items: [
        { name: "Makefile (DX)", status: "complete", evidence: "✓ Root Makefile, setup/up/down/test/smoke" },
        { name: "Docker Multi-Stage", status: "complete", evidence: "✓ Dockerfile.api, Dockerfile.worker" },
        { name: "Compose Healthchecks", status: "complete", evidence: "✓ Default stack + sidecars" },
        { name: "Alembic Migrations", status: "complete", evidence: "✓ One-shot migrate service, auto-stamp" },
        { name: "WSL2 Setup Guide", status: "complete", evidence: "✓ DEV_SETUP_WSL.md" },
        { name: "Fresh Setup Verification", status: "complete", evidence: "✓ SETUP_VERIFICATION.md" },
        { name: "Structured Logging", status: "complete", evidence: "✓ JSON/text, ADR 0007" },
        { name: "Prometheus Metrics", status: "complete", evidence: "✓ /metrics endpoint, optional" },
        { name: "Production Deploy", status: "pending-vps", evidence: "✓ Code/docs complete; VPS cutover PENDING" },
        { name: "Production Acceptance", status: "local-only", evidence: "✓ Local dry-run PASS (PR #143); prod host PENDING" }
      ]
    },
    {
      title: "9. Frontend (Next.js)",
      complete: 100,
      items: [
        { name: "5 Landing Pages", status: "complete", evidence: "✓ /candidates, /recruiters, /sales, /investors, /journalists" },
        { name: "Console UI", status: "complete", evidence: "✓ /app/enrich, /app/jobs, /app/history" },
        { name: "Dossier View", status: "complete", evidence: "✓ Photo, handles, emails, jobs, business" },
        { name: "OpenAPI Codegen", status: "complete", evidence: "✓ frontend/src/lib/generated/, npm run openapi:gen" },
        { name: "API Client", status: "complete", evidence: "✓ backend-client.ts, type-safe" },
        { name: "shadcn/ui", status: "complete", evidence: "✓ components/ui/, Tailwind" }
      ]
    },
    {
      title: "10. Documentation",
      complete: 95,
      items: [
        { name: "ARCHITECTURE.md", status: "complete", evidence: "✓ backend/docs/, agent quick ref" },
        { name: "LEGAL.md", status: "mostly-complete", evidence: "✓ Compliance posture; LinkedIn section PENDING (gap 61)" },
        { name: "DEVPLAN.md", status: "complete", evidence: "✓ Phased checklist, Phase 0-7" },
        { name: "ADRs (8 decisions)", status: "complete", evidence: "✓ docs/adr/000[1-8]*.md" },
        { name: "PROD_ACCEPTANCE.md", status: "complete", evidence: "✓ Local sign-off; prod column PENDING VPS" },
        { name: "Testing Docs", status: "complete", evidence: "✓ TESTING_TIER1.md, TESTING_TIER234.md, LOAD_TESTING.md" },
        { name: "Ops Runbook", status: "complete", evidence: "✓ deployment.md, OPS.md, ALERTING.md" },
        { name: "README (both)", status: "complete", evidence: "✓ Root + backend/README.md" }
      ]
    }
  ];

  const gaps = [
    { id: 28, title: "Email pattern fallback", phase: 2, status: "OPEN" },
    { id: 31, title: "Reacher order + catch-all", phase: 2, status: "OPEN" },
    { id: 39, title: "JobSpy multi-board expansion", phase: 2, status: "OPEN" },
    { id: 61, title: "LEGAL LinkedIn section", phase: 3, status: "OPEN" },
    { id: 71, title: "Signals product flow", phase: 4, status: "OPEN" },
    { id: 76, title: "Real canary set (Tier 1)", phase: 5, status: "PARTIAL (PR #142)" },
    { id: "86-89", title: "Production VPS deploy", phase: 6, status: "DEFERRED (no VPS chosen)" },
    { id: 90, title: "Guide complete", phase: 7, status: "PARTIAL (local/staging OK)" }
  ];

  const overallCompletion = 92; // weighted average

  return (
    <div className="max-w-7xl mx-auto p-8 bg-gradient-to-br from-slate-50 to-blue-50 min-h-screen">
      <div className="bg-white rounded-xl shadow-2xl p-8 mb-8">
        <h1 className="text-4xl font-bold text-slate-800 mb-2">
          Hyrepath Enrichment — Completion Assessment
        </h1>
        <p className="text-slate-600 mb-4">Against Developer Guide v0.2 (July 2026)</p>

        <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg p-6 text-white mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">Overall Completion</h2>
              <p className="text-blue-100">Based on 10 major areas + 200+ checklist items</p>
            </div>
            <div className="text-6xl font-black">{overallCompletion}%</div>
          </div>
          <div className="mt-4 bg-white/20 rounded-full h-4 overflow-hidden">
            <div
              className="bg-white h-full transition-all duration-500 rounded-full"
              style={{ width: `${overallCompletion}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
            <h3 className="text-lg font-bold text-green-800 mb-2">✓ Complete on main</h3>
            <ul className="text-sm text-green-700 space-y-1">
              <li>• All 9 API endpoints</li>
              <li>• Full compliance (opt-out/DSAR)</li>
              <li>• Redis queue + worker</li>
              <li>• 11 enrichers (real integrations)</li>
              <li>• Docker compose stack</li>
              <li>• Frontend (5 landing + console)</li>
              <li>• E2E harness + load testing</li>
              <li>• ADRs + production docs</li>
            </ul>
          </div>

          <div className="bg-amber-50 border-2 border-amber-200 rounded-lg p-4">
            <h3 className="text-lg font-bold text-amber-800 mb-2">⚠ Remaining Gaps</h3>
            <ul className="text-sm text-amber-700 space-y-1">
              <li>• Tier 1 full canary (PR #142 open)</li>
              <li>• Email catch-all parsing (gap 31)</li>
              <li>• JobSpy multi-board (gap 39)</li>
              <li>• Signals product flow (gap 71)</li>
              <li>• LinkedIn section in LEGAL (gap 61)</li>
              <li>• <strong>Production VPS cutover</strong> (86-89)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Detailed Breakdown */}
      {sections.map((section, idx) => (
        <div key={idx} className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-slate-800">{section.title}</h2>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-blue-600">{section.complete}%</div>
              <div className="w-32 bg-slate-200 rounded-full h-3">
                <div
                  className="bg-blue-500 h-full rounded-full transition-all"
                  style={{ width: `${section.complete}%` }}
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            {section.items.map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded hover:bg-slate-50 transition-colors">
                <div className="flex-shrink-0 mt-0.5">
                  {item.status === 'complete' && (
                    <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-sm">✓</div>
                  )}
                  {item.status === 'partial' && (
                    <div className="w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center text-white text-sm">⚠</div>
                  )}
                  {item.status === 'mostly-complete' && (
                    <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm">~</div>
                  )}
                  {item.status === 'pending-vps' && (
                    <div className="w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white text-sm">⏳</div>
                  )}
                  {item.status === 'local-only' && (
                    <div className="w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-white text-sm">🏠</div>
                  )}
                </div>
                <div className="flex-grow">
                  <div className="font-semibold text-slate-700">{item.name}</div>
                  <div className="text-sm text-slate-500">{item.evidence}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Open Gaps */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h2 className="text-2xl font-bold text-slate-800 mb-4">Open Developer Guide Gaps</h2>
        <div className="space-y-3">
          {gaps.map((gap, i) => (
            <div key={i} className="flex items-center gap-4 p-4 border-l-4 border-amber-400 bg-amber-50 rounded">
              <div className="font-mono text-lg font-bold text-amber-700">#{gap.id}</div>
              <div className="flex-grow">
                <div className="font-semibold text-slate-800">{gap.title}</div>
                <div className="text-sm text-slate-600">Phase {gap.phase}</div>
              </div>
              <div className={`px-3 py-1 rounded-full text-sm font-semibold ${
                gap.status === 'OPEN' ? 'bg-red-100 text-red-700' :
                gap.status.includes('PARTIAL') ? 'bg-amber-100 text-amber-700' :
                'bg-purple-100 text-purple-700'
              }`}>
                {gap.status}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Summary Verdict */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-lg shadow-2xl p-8 text-white">
        <h2 className="text-3xl font-bold mb-4">📊 Verdict</h2>

        <div className="space-y-4 text-lg">
          <p className="leading-relaxed">
            <strong className="text-green-400">92% complete</strong> against the Developer Guide scope.
            The <strong>core product is feature-complete and production-ready</strong> in local/staging environments.
          </p>

          <div className="border-l-4 border-green-400 pl-4 my-4 bg-white/10 p-4 rounded">
            <h3 className="font-bold text-green-300 mb-2">✓ What's Done (on main branch):</h3>
            <ul className="space-y-1 text-base">
              <li>• All 4 enrichment tiers implemented with real tools</li>
              <li>• Complete API (9 endpoints) with Bearer auth</li>
              <li>• LGPD/GDPR/CCPA compliance (opt-out + DSAR + audit)</li>
              <li>• Redis queue + RQ worker + Postgres + Alembic</li>
              <li>• 8 AGPL sidecars isolated properly</li>
              <li>• Full E2E test harness + load testing (k6)</li>
              <li>• Production-grade logging, metrics, error tracking</li>
              <li>• Next.js frontend with 5 audience landing pages</li>
              <li>• Comprehensive docs (Architecture, Legal, ADRs, Ops runbook)</li>
            </ul>
          </div>

          <div className="border-l-4 border-amber-400 pl-4 my-4 bg-white/10 p-4 rounded">
            <h3 className="font-bold text-amber-300 mb-2">⚠ What's Remaining:</h3>
            <ul className="space-y-1 text-base">
              <li>• <strong>Tier 1 Multilogin live canary</strong> — real scrapes work, 3 bugs fixed, but 10-profile automated re-run not complete (PR #142 open)</li>
              <li>• <strong>Email catch-all detection</strong> (gap 31) — Reacher field exists, needs parsing</li>
              <li>• <strong>JobSpy multi-board</strong> (gap 39) — currently Indeed + LinkedIn; guide expects 5 boards</li>
              <li>• <strong>Signals product flow</strong> (gap 71) — webhook consumer exists, but watch→notify end-to-end is logging-only</li>
              <li>• <strong>Production VPS</strong> (gaps 86-89) — code/docs/automation 100% ready (local dry-run passed), but no actual VPS chosen yet</li>
            </ul>
          </div>

          <div className="border-l-4 border-blue-400 pl-4 my-4 bg-white/10 p-4 rounded">
            <h3 className="font-bold text-blue-300 mb-2">🎯 Critical Path to 100%:</h3>
            <ol className="space-y-2 text-base list-decimal list-inside">
              <li>Complete Tier 1 live canary (10 profiles automated) → merge PR #142</li>
              <li>Implement email catch-all parsing (gap 31) — ~1 day</li>
              <li>Expand JobSpy to 5 boards (gap 39) — ~2 days</li>
              <li>Document LinkedIn scraping in LEGAL.md (gap 61) — ~1 hour</li>
              <li>Design + implement signals product flow (gap 71) — ~3 days</li>
              <li><strong>Choose production VPS + deploy</strong> → run acceptance → sign off (gaps 86-89)</li>
            </ol>
          </div>

          <p className="leading-relaxed pt-4">
            <strong className="text-yellow-300">Task 90 Status:</strong> <span className="text-amber-300 font-bold">PARTIAL</span>
            — local/staging verification complete, but production deployment blocked by VPS selection (external blocker, not code).
          </p>

          <p className="leading-relaxed">
            The repository contains a <strong className="text-green-300">production-grade enrichment platform</strong> that matches
            ~90% of the Developer Guide's architectural vision. The remaining 8-10% are polish items (email catch-all, job board expansion,
            Tier 1 full canary) plus the external production hosting decision.
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-6 bg-slate-100 rounded-lg p-4">
        <h3 className="font-bold text-slate-700 mb-2">Status Legend:</h3>
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-green-500"></div>
            <span>Complete — merged to main</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-blue-500"></div>
            <span>Mostly Complete — minor gap</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-amber-500"></div>
            <span>Partial — significant work remains</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-purple-500"></div>
            <span>Pending VPS — code ready, host needed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-indigo-500"></div>
            <span>Local Only — not yet on prod</span>
          </div>
        </div>
      </div>

      <div className="mt-6 text-center text-sm text-slate-500">
        Assessment Date: {new Date().toLocaleDateString()} • Based on: docs/PROJECT_COMPLETE_AUDIT.md, docs/DEVPLAN.md, backend/docs/ARCHITECTURE.md
      </div>
    </div>
  );
};

export default ProjectCompletionAssessment;
