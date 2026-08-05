#!/usr/bin/env python3
"""Diagnostic script to check Multilogin profile availability."""

import asyncio
import sys

# Add backend to path
sys.path.insert(0, "/app/backend")

from app.clients.multilogin import MultiloginClient
from app.core.config import get_settings


async def main():
    settings = get_settings()
    print(f"Multilogin Configuration:")
    print(f"  Email: {settings.multilogin_email}")
    print(f"  Folder ID: {settings.multilogin_folder_id}")
    print(f"  Workspace ID: {settings.multilogin_workspace_id}")
    print(f"  Browser Mode: {settings.browser_mode}")
    print()

    client = MultiloginClient()

    try:
        print("Attempting to get auth token...")
        token = await client.get_token()
        print(f"✓ Successfully obtained auth token (length: {len(token)})")
        print()

        print("Fetching profile list from configured folder...")
        profile_ids = await client.list_profiles()

        if not profile_ids:
            print("✗ ERROR: No profiles found in the configured folder!")
            print()
            print("Possible causes:")
            print("  1. MULTILOGIN_FOLDER_ID points to an empty or wrong folder")
            print("  2. Profiles were deleted from the folder")
            print("  3. Folder access permissions changed")
        else:
            print(f"✓ Found {len(profile_ids)} profile(s):")
            for i, profile_id in enumerate(profile_ids, 1):
                print(f"  {i}. {profile_id}")

    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
