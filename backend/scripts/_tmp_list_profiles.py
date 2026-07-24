import hashlib
import os

import httpx

EMAIL = os.environ["MLX_EMAIL"]
PASSWORD = os.environ["MLX_PASSWORD"]
FOLDER_ID = os.environ["MLX_FOLDER_ID"]
WORKSPACE_ID = os.environ.get("MLX_WORKSPACE_ID", "")
API_BASE = "https://api.multilogin.com"

with httpx.Client(timeout=15.0) as client:
    resp = client.post(
        f"{API_BASE}/user/signin",
        json={"email": EMAIL, "password": hashlib.md5(PASSWORD.encode()).hexdigest()},
    )
    data = resp.json()["data"]
    token, refresh_token = data["token"], data.get("refresh_token", "")
    if WORKSPACE_ID:
        resp2 = client.post(
            f"{API_BASE}/user/refresh_token",
            json={"email": EMAIL, "refresh_token": refresh_token, "workspace_id": WORKSPACE_ID},
        )
        token = resp2.json()["data"]["token"]

    headers = {"Authorization": f"Bearer {token}"}
    resp3 = client.post(
        f"{API_BASE}/profile/search",
        json={"limit": 20, "offset": 0, "search_text": "", "folder_id": FOLDER_ID},
        headers=headers,
    )
    for p in resp3.json().get("data", {}).get("profiles", []):
        print(p.get("id"), "|", p.get("name"), "| in_use_by=", repr(p.get("in_use_by")), "| last_launched_at=", p.get("last_launched_at"))
