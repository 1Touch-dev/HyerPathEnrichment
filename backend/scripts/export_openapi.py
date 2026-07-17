#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema to a JSON file (offline, no running server)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Hyrepath OpenAPI schema")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: stdout)",
    )
    args = parser.parse_args()

    from app.main import app

    schema = app.openapi()
    payload = json.dumps(schema, indent=2, sort_keys=True)
    payload = f"{payload}\n"

    if args.output is None:
        sys.stdout.write(payload)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
