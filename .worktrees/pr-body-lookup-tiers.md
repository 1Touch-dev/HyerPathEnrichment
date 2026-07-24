## Summary
- Replaces Quick/Standard/Deep depth radios on the Look up page with per-tier checkboxes for both sync and async modes
- Use-case landings still seed via `?tiers=…`; selected tiers are preserved exactly (no preset collapse)
- Sync mode keeps tier1 disabled/stripped; Advanced still holds optional company/business/job fields

## Test plan
- [ ] Open `/app/enrich` from hub — tier2 + tier3 checked by default
- [ ] Open from `/recruiters` — tier1–3 pre-checked; uncheck one and submit async — payload matches
- [ ] Switch to sync with tier1 checked — tier1 disabled/unchecked; submit succeeds without tier1
- [ ] Open from `/sales` — only tier3 checked; can add tier2 manually
- [ ] `npm run typecheck` in `frontend/`
