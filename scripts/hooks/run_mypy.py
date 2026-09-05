#!/usr/bin/env python3
"""Run mypy against backend/app using the project virtualenv when present."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _is_runnable(python_path: Path) -> bool:
    """Confirm a candidate interpreter actually executes on this OS.

    A `.venv` created inside WSL leaves a `Scripts/python.exe` that exists on
    disk when viewed from native Windows (e.g. via a shared /mnt mount) but
    isn't a real, runnable Windows executable. `Path.is_file()` alone can't
    tell the difference, so probe it directly.
    """
    try:
        result = subprocess.run(
            [str(python_path), "--version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _python_executable() -> str:
    root = Path(__file__).resolve().parents[2]
    if sys.platform == "win32":
        candidate = root / "backend" / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = root / "backend" / ".venv" / "bin" / "python"
    if candidate.is_file() and _is_runnable(candidate):
        return str(candidate)
    return sys.executable


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    backend = root / "backend"
    result = subprocess.run(
        [_python_executable(), "-m", "mypy", "app"],
        cwd=backend,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
