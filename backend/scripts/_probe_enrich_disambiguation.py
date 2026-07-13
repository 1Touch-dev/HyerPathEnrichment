"""Check enrich/sync uses new LLM disambiguation evidence strings."""

from __future__ import annotations

import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/enrich/sync",
    data=json.dumps(
        {
            "username": "jane-doe",
            "email": "jane.doe@acme.com",
            "requested_tiers": ["tier2"],
        }
    ).encode(),
    headers={
        "Authorization": "Bearer change-me",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=180) as resp:
    payload = json.loads(resp.read().decode())

evidence = next(
    item["evidence"]
    for item in payload["dossier"]["confidence"]
    if item["label"] == "identity-match"
)
print("evidence", evidence)
print("dropped_meta", payload["dossier"]["metadata"].get("disambiguation_dropped"))
print(
    "handles",
    [
        (h["platform"][:40], round(h["confidence"], 3))
        for h in payload["dossier"]["handles"]
    ],
)
assert any("llm disambiguation dropped" in e for e in evidence), evidence
print("PASS: enrich uses new confidence evidence")
