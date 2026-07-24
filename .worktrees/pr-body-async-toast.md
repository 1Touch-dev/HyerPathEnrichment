## Summary
- Async enrichment: show Job created toast and stay on /app/enrich (no dossier redirect)
- Only cache terminal jobs in React Query; pending jobs poll without storing queued dossiers
- Sync still redirects to the job page with completed data
- Add sonner toaster; update async e2e expectations

## Test plan
- [ ] Async Look up shows toast with job id and URL stays on /app/enrich
- [ ] History lists the new job; open completed job and dossier loads
- [ ] Sync Look up still redirects to /app/jobs/{id} with results
- [ ] Opening a still-running job from History shows waiting UI until completed
