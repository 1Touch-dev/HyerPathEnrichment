## Summary
- Add repo-root `.pre-commit-config.yaml` with ruff format/lint, mypy, frontend typecheck, hygiene hooks, `.env` blocking, and commit-msg guard against author trailers.
- Wire installation into `make setup` plus new `make lint` and `make pre-commit` targets; document usage in README.
- Add CI `pre-commit` job running `pre-commit run --all-files`.
- Apply one-time ruff format to `backend/app` and `backend/tests`, fix mypy baseline issues, and add `scripts/verify_precommit.sh`.

## Test plan
- [x] `make setup` installs pre-commit + commit-msg hooks
- [x] `pre-commit run --all-files` passes locally
- [x] `scripts/verify_precommit.sh` passes (env guard + commit-msg negative tests)
- [x] `mypy backend/app` passes
- [x] `cd frontend && npm run typecheck` passes
- [ ] CI `pre-commit`, `lint-test`, and `frontend-contract` jobs green on PR
