# 0006. Heuristic LLM stub default with opt-in LiteLLM

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Handle disambiguation (which social profiles belong to the subject) can use an LLM, but production deployments must run without API keys or paid inference by default. We needed a default that keeps the pipeline deterministic and free-tier friendly.

## Decision

We chose **heuristic stub as default** with **opt-in LiteLLM/Ollama** (`LLM_MODE=litellm` or `ollama`) over **always-on LLM inference** because most installs should not require external model keys to boot. Always-on LLM was rejected — it adds cost, latency, and key management to every enrichment. LiteLLM + Langfuse integration exists in `clients/llm.py` for operators who opt in.

## Tradeoffs

- Disambiguation quality is lower on the stub until `LLM_MODE` is switched and prompts are tuned.
- Langfuse tracing and cost dashboards only matter once LiteLLM mode is exercised in staging/prod.
- Pipeline still walks handles below `DISAMBIGUATION_THRESHOLD` via `enrichers/disambiguate.py`.

## Consequences

- Default `LLM_MODE` uses the heuristic stub; no keys required for smoke tests.
- Config in `core/config.py`; HTTP client in `app/clients/llm.py`.
- Real prompt tuning and observability are follow-on work once LiteLLM is enabled in an environment.
