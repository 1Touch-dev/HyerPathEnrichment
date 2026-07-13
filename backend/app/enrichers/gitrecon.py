from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.enrichers.base import Enricher
from app.models import EnrichmentRequest
from app.providers import run_command


def fragment_from_gitrecon_data(
    data: dict[str, Any],
    *,
    username: str,
    source_name: str = "GitRecon",
) -> dict[str, Any]:
    """Map upstream gitrecon JSON into a dossier fragment."""
    login = str(data.get("username") or data.get("login") or username)
    profile_url = f"https://github.com/{login}"

    raw_emails = (
        data.get("leaked_emails")
        or data.get("emails")
        or data.get("commit_emails")
        or []
    )
    emails = [str(email) for email in raw_emails if email]

    raw_orgs = data.get("orgs") or data.get("organizations") or []
    organizations = [str(org) for org in raw_orgs if org]

    commits = data.get("public_commits")
    if commits is None:
        commits = data.get("commits") or data.get("total_commits") or 0
    try:
        public_commits = int(commits)
    except (TypeError, ValueError):
        public_commits = 0

    fragment: dict[str, Any] = {
        "handles": [
            {
                "platform": "GitHub",
                "username": login,
                "profile_url": profile_url,
                "confidence": 0.9,
                "metadata": {"provider": source_name, "matched": True},
            }
        ],
        "github": {
            "profile": profile_url,
            "organizations": organizations,
            "public_commits": public_commits,
        },
    }
    if emails:
        fragment["emails"] = emails
    return fragment


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
            command = ["python3", script, username, "-s", "github", "-o"]
        else:
            # Upstream CLI: gitrecon.py <username> -s github -o (writes JSON under results/)
            command = ["python3", "gitrecon.py", username, "-s", "github", "-o"]

        env = os.environ.copy()
        if settings.github_token:
            env["GITHUB_TOKEN"] = settings.github_token

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "results").mkdir(parents=True, exist_ok=True)
            returncode, _, stderr = await run_command(command, timeout=120.0, env=env, cwd=tmp)
            result_file = Path(tmp) / "results" / username / f"{username}_github.json"
            if returncode != 0 or not result_file.exists():
                hint = (stderr or "").strip().splitlines()
                logger.warning(
                    "gitrecon produced no output (rc=%s file=%s): %s",
                    returncode,
                    result_file,
                    hint[-1] if hint else "no stderr",
                )
                return {}
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}

        return fragment_from_gitrecon_data(data, username=username, source_name=self.source_name)
