#!/usr/bin/env python
"""Generate OpenAPI schema from FastAPI app."""
import json
from pathlib import Path

from app.main import app

output_path = Path(__file__).parent.parent / "frontend" / "openapi" / "openapi.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

schema = app.openapi()
with open(output_path, "w") as f:
    json.dump(schema, f, indent=2)

print(f"Generated OpenAPI schema to {output_path}")
