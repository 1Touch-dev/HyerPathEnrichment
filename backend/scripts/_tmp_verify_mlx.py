"""One-off verification: sign in to Multilogin cloud API, exchange for a
workspace token, list profiles in the configured folder, start one profile
via the LOCAL WSL launcher agent (127.0.0.1:45001), and confirm the
per-profile Selenium/DevTools port is reachable on loopback.

Reads credentials from environment variables (passed in, not hardcoded).
Delete this file after use — it is not part of the permanent test suite.
"""

import hashlib
import os
import sys

import httpx

EMAIL = os.environ["MLX_EMAIL"]
PASSWORD = os.environ["MLX_PASSWORD"]
FOLDER_ID = os.environ["MLX_FOLDER_ID"]
WORKSPACE_ID = os.environ.get("MLX_WORKSPACE_ID", "")
API_BASE = os.environ.get("MLX_API_BASE", "https://api.multilogin.com")
LAUNCHER_BASE = os.environ.get("MLX_LAUNCHER_BASE", "https://127.0.0.1:45001/api/v2")


def main() -> int:
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{API_BASE}/user/signin",
            json={"email": EMAIL, "password": hashlib.md5(PASSWORD.encode()).hexdigest()},
        )
        print("signin status:", resp.status_code)
        if resp.status_code != 200:
            print(resp.text[:300])
            return 1
        data = resp.json()["data"]
        token = data["token"]
        refresh_token = data.get("refresh_token", "")

        if WORKSPACE_ID:
            resp2 = client.post(
                f"{API_BASE}/user/refresh_token",
                json={"email": EMAIL, "refresh_token": refresh_token, "workspace_id": WORKSPACE_ID},
            )
            print("workspace token exchange status:", resp2.status_code)
            if resp2.status_code != 200:
                print(resp2.text[:300])
                return 1
            token = resp2.json()["data"]["token"]

        headers = {"Authorization": f"Bearer {token}"}

        resp3 = client.post(
            f"{API_BASE}/profile/search",
            json={"limit": 5, "offset": 0, "search_text": "", "folder_id": FOLDER_ID},
            headers=headers,
        )
        print("profile search status:", resp3.status_code)
        print(resp3.text[:800])
        if resp3.status_code != 200:
            return 1
        profiles = resp3.json().get("data", {}).get("profiles", [])
        if not profiles:
            print("No profiles found in folder — nothing to start.")
            return 0
        profile_id = profiles[0].get("profile_id") or profiles[0].get("id")
        print("using profile_id:", profile_id)

    with httpx.Client(timeout=60.0, verify=False) as launcher_client:
        start_url = f"{LAUNCHER_BASE}/profile/f/{FOLDER_ID}/p/{profile_id}/start"
        resp4 = launcher_client.get(
            start_url,
            params={"automation_type": "selenium"},
            headers=headers,
        )
        print("start_profile status:", resp4.status_code)
        print(resp4.text[:500])
        if resp4.status_code != 200:
            return 1
        port = resp4.json()["data"]["port"]
        print("selenium/devtools port:", port)

        resp5 = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=10.0)
        print("devtools check status:", resp5.status_code)
        print(resp5.text[:300])

        stop_url = f"https://127.0.0.1:45001/api/v1/profile/stop/p/{profile_id}"
        resp6 = launcher_client.get(stop_url, headers=headers)
        print("stop_profile status:", resp6.status_code)

    return 0


if __name__ == "__main__":
    sys.exit(main())
