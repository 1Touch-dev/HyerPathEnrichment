from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

files_patches = {
    "backend/tests/test_tier2_merge.py": [
        (
            'EnrichmentRequest(username="jane")',
            'EnrichmentRequest(username="jane", requested_tiers=["tier2"])',
        ),
    ],
    "backend/tests/test_disambiguation.py": [
        (
            'return EnrichmentRequest(username="jane-doe", email="jane@acme.com")',
            'return EnrichmentRequest(username="jane-doe", email="jane@acme.com", requested_tiers=["tier2", "tier3"])',
        ),
    ],
    "backend/tests/test_job_dedup.py": [
        (
            'EnrichmentRequest(job_search="software engineer")',
            'EnrichmentRequest(job_search="software engineer", requested_tiers=["tier4"])',
        ),
    ],
    "backend/tests/test_fake_sidecar_server.py": [
        (
            'EnrichmentRequest(username="torvalds")',
            'EnrichmentRequest(username="torvalds", requested_tiers=["tier2"])',
        ),
        (
            'EnrichmentRequest(business="coffee shop San Francisco")',
            'EnrichmentRequest(business="coffee shop San Francisco", requested_tiers=["tier4"])',
        ),
    ],
    "backend/tests/test_gitrecon_throttle.py": [
        (
            'EnrichmentRequest(username="octocat")',
            'EnrichmentRequest(username="octocat", requested_tiers=["tier3"])',
        ),
    ],
}

for rel, pairs in files_patches.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        count = text.count(old)
        if count == 0:
            print(f"MISSING in {rel}: {old[:70]}")
        else:
            text = text.replace(old, new)
            print(f"OK {rel} x{count}")
    path.write_text(text, encoding="utf-8")

p = ROOT / "backend/tests/test_enrichers.py"
text = p.read_text(encoding="utf-8")
pairs = [
    (
        'EnrichmentRequest(username="octocat")',
        'EnrichmentRequest(username="octocat", requested_tiers=["tier3"])',
    ),
    (
        'EnrichmentRequest(company="Microsoft")',
        'EnrichmentRequest(company="Microsoft", requested_tiers=["tier3"])',
    ),
    (
        'EnrichmentRequest(username="jane doe", company="Acme Corp")',
        'EnrichmentRequest(username="jane doe", company="Acme Corp", requested_tiers=["tier3"])',
    ),
    (
        'EnrichmentRequest(username="jane", company="Acme Corp")',
        'EnrichmentRequest(username="jane", company="Acme Corp", requested_tiers=["tier3"])',
    ),
    (
        'EnrichmentRequest(username="jane")',
        'EnrichmentRequest(username="jane", requested_tiers=["tier2"])',
    ),
    (
        'EnrichmentRequest(username="torvalds")',
        'EnrichmentRequest(username="torvalds", requested_tiers=["tier2"])',
    ),
    (
        'EnrichmentRequest(business="Joe\'s Coffee")',
        'EnrichmentRequest(business="Joe\'s Coffee", requested_tiers=["tier4"])',
    ),
    (
        'EnrichmentRequest(business="coffee shop San Francisco")',
        'EnrichmentRequest(business="coffee shop San Francisco", requested_tiers=["tier4"])',
    ),
    (
        'EnrichmentRequest(job_search="SRE")',
        'EnrichmentRequest(job_search="SRE", requested_tiers=["tier4"])',
    ),
    (
        'EnrichmentRequest(username="x")',
        'EnrichmentRequest(username="x", requested_tiers=["tier2"])',
    ),
]
for old, new in pairs:
    count = text.count(old)
    if count == 0:
        print(f"MISSING enrichers: {old[:70]}")
    else:
        text = text.replace(old, new)
        print(f"OK enrichers x{count}: {old[:50]}")
p.write_text(text, encoding="utf-8")
print("done")
