#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend
export TEST_DATABASE_URL="postgresql+asyncpg://hyrepath:hyrepath@127.0.0.1:5432/hyrepath"
export PYTHONPATH=.

# Prefer project venv if present (Windows venv may not work in WSL) — use python3 + pip if needed
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif [ -x .venv/Scripts/python.exe ]; then
  # Running Windows venv from WSL is awkward; use system python with editable install check
  PY=python3
else
  PY=python3
fi

echo "Using interpreter: $PY"
"$PY" -c "import pytest, sqlalchemy, psycopg; print('deps ok', pytest.__version__)" 2>&1 || {
  echo "Installing backend[dev] for system python..."
  python3 -m pip install -e '.[dev]' -q
  PY=python3
}

echo "== port check =="
python3 - <<'PY'
import socket
s=socket.create_connection(("127.0.0.1",5432), timeout=3)
print("5432 open")
s.close()
PY

echo "== run postgres tests =="
"$PY" -m pytest tests -m postgres -v --tb=short
