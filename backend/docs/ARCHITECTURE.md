# Backend Architecture

- FastAPI routes delegate to a service factory.
- The service creates a pipeline orchestrator.
- Enrichers are isolated modules per provider.
- SQLAlchemy stores jobs and suppression records.
- The current implementation uses safe local fallbacks for persistence and asset caching while preserving production-facing interfaces.
