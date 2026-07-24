"""Single clean retry after waiting for any stale cloud lock to expire."""

import hashlib
import os
import sys
import time

import httpx

EMAIL = os.environ["MLX_EMAIL"]
PASSWORD = os.environ["MLX_PASSWORD"]
FOLDER_ID = os.environ["MLX_FOLDER_ID"]
WORKSPACE_ID = os.environ.get("MLX_WORKSPACE_ID", "")
PROFILE_ID = os.environ["MLX_PROFILE_ID"]
API_BASE = "https://api.multilogin.com"
LAUNCHER_BASE = "https://127.0.0.1:45001/api/v2"


def get_token() -> str:
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
    return token


def main() -> int:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=90.0, verify=False) as launcher_client:
        start_url = f"{LAUNCHER_BASE}/profile/f/{FOLDER_ID}/p/{PROFILE_ID}/start"
        print(f"[{time.strftime('%H:%M:%S')}] starting profile (up to 90s)...")
        resp4 = launcher_client.get(start_url, params={"automation_type": "selenium"}, headers=headers)
        print(f"[{time.strftime('%H:%M:%S')}] start_profile status:", resp4.status_code)
        print(resp4.text[:500])
        if resp4.status_code != 200:
            return 1
        port = resp4.json()["data"]["port"]
        print("selenium/devtools port:", port)

        time.sleep(2)
        resp5 = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=10.0)
        print("devtools check status:", resp5.status_code)
        print(resp5.text[:300])

    return 0


if __name__ == "__main__":
    sys.exit(main())
