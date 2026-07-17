#!/usr/bin/env python3
"""Create or list changedetection.io watches via the REST API."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

from app.core.config import get_settings

DEFAULT_SIGNAL_URL = "post://api:8000/api/signals/changedetection"
NOTIFICATION_BODY = json.dumps(
    {
        "watch_uuid": "{{watch_uuid|tojson}}",
        "watch_title": "{{watch_title|tojson}}",
        "watch_url": "{{watch_url|tojson}}",
        "timestamp": "{{last_changed|tojson}}",
    }
)


def _base_url() -> str:
    settings = get_settings()
    url = settings.changedetection_url.strip().rstrip("/")
    if not url:
        print("CHANGEDETECTION_URL is not set", file=sys.stderr)
        sys.exit(1)
    return url


def _api_key() -> str:
    return get_settings().changedetection_api_key.strip()


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _signal_notification_url(api_key: str) -> str:
    url = os.environ.get("CHANGEDETECTION_SIGNAL_URL", DEFAULT_SIGNAL_URL).strip()
    if api_key:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}+X-Signal-Token={api_key}"
    return url


def list_watches() -> None:
    base = _base_url()
    api_key = _api_key()
    response = httpx.get(
        f"{base}/api/v1/watch",
        headers=_headers(api_key),
        timeout=30.0,
    )
    response.raise_for_status()
    watches = response.json()
    if not watches:
        print("No watches configured.")
        return
    for watch in watches.values() if isinstance(watches, dict) else watches:
        print(f"{watch.get('uuid', '?')}\t{watch.get('title', '')}\t{watch.get('url', '')}")


def create_watch(url: str, title: str) -> None:
    base = _base_url()
    api_key = _api_key()
    payload = {
        "url": url,
        "title": title,
        "notification_urls": [_signal_notification_url(api_key)],
        "notification_body": NOTIFICATION_BODY,
    }
    response = httpx.post(
        f"{base}/api/v1/watch",
        headers=_headers(api_key),
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    watch_uuid = response.json().get("uuid", "unknown")
    print(f"created watch {watch_uuid} for {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage changedetection.io watches")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List configured watches")

    create_parser = subparsers.add_parser("create", help="Create a watch")
    create_parser.add_argument("url", help="URL to monitor")
    create_parser.add_argument("--title", default="", help="Optional watch title")

    args = parser.parse_args()
    if args.command == "list":
        list_watches()
    elif args.command == "create":
        title = args.title or args.url
        create_watch(args.url, title)


if __name__ == "__main__":
    main()
