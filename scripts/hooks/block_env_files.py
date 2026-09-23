#!/usr/bin/env python3
"""Fail if staged files include real env secret files.

Blocked (anywhere in the tree):
  .env, .env.local, .env.production, .env.staging
  and any other .env* that is not a *.example / *.template

Allowed:
  .env.example, .env.staging.example, .env.production.template, etc.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Basename is a real env file (not a template).
_BLOCKED_BASENAME = re.compile(
    r"^\.env$"
    r"|^\.env\.local$"
    r"|^\.env\.production$"
    r"|^\.env\.staging$"
    r"|^\.env\.[^.]+$"  # .env.foo but not .env.foo.example
)

_ALLOWED_SUFFIX = re.compile(r"\.(example|template)$")


def _is_blocked(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if _ALLOWED_SUFFIX.search(name):
        return False
    if not name.startswith(".env"):
        return False
    # Explicit names + any non-template .env*
    if _BLOCKED_BASENAME.match(name) or name.startswith(".env"):
        return True
    return False


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or "ERROR: unable to read staged files", file=sys.stderr)
        return result.returncode

    blocked = [line for line in result.stdout.splitlines() if _is_blocked(line)]
    if not blocked:
        return 0

    print(
        "ERROR: refusing to commit real env files "
        "(.env / .env.local / .env.production / .env.staging / other non-template .env*)",
        file=sys.stderr,
    )
    print(
        "Use .env.example / .env.*.example / .env.*.template only. "
        "Real secrets stay on the host and must never reach GitHub.",
        file=sys.stderr,
    )
    for path in blocked:
        print(f"  - {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
