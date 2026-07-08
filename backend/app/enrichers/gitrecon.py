from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import run_command


class GitReconEnricher(Enricher):
    source_name = "GitRecon"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.username or request.email)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        username = request.username or (request.email or "").split("@")[0]
        if not username:
            return {}

        script = settings.gitrecon_script.strip()
        if script:
            command = ["python3", script, "-s", "github", "-o", username]
        else:
            # Upstream CLI: gitrecon.py -s github -o <username> (writes JSON under results/)
            command = ["python3", "gitrecon.py", "-s", "github", "-o", username]

        env = os.environ.copy()
        if settings.github_token:
            env["GITHUB_TOKEN"] = settings.github_token

        with tempfile.TemporaryDirectory() as tmp:
            returncode, _, _ = await run_command(command, timeout=120.0, env=env, cwd=tmp)
            result_file = Path(tmp) / "results" / username / f"{username}_github.json"
            if returncode != 0 or not result_file.exists():
                return {}
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}

        login = str(data.get("username", username))
        profile_url = f"https://github.com/{login}"
        emails = [str(email) for email in data.get("leaked_emails", []) if email]
        organizations = [str(org) for org in data.get("orgs", []) if org]

        fragment: dict[str, Any] = {
            "handles": [
                {
                    "platform": "GitHub",
                    "username": login,
                    "profile_url": profile_url,
                    "confidence": 0.9,
                    "metadata": {"provider": self.source_name, "matched": True},
                }
            ],
            "github": {
                "profile": profile_url,
                "organizations": organizations,
                "public_commits": 0,
            },
        }
        if emails:
            fragment["emails"] = emails
        return fragment
