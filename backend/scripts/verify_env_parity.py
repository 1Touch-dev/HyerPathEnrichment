#!/usr/bin/env python3
"""Verify staging and production env templates define the same keys."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare env template key parity")
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--production", required=True, type=Path)
    args = parser.parse_args()

    staging = _parse_keys(args.staging)
    production = _parse_keys(args.production)
    only_staging = sorted(staging - production)
    only_production = sorted(production - staging)

    if only_staging or only_production:
        if only_staging:
            print("Keys only in staging:", ", ".join(only_staging), file=sys.stderr)
        if only_production:
            print("Keys only in production:", ", ".join(only_production), file=sys.stderr)
        raise SystemExit(1)

    print(f"parity ok ({len(staging)} keys)")


if __name__ == "__main__":
    main()
