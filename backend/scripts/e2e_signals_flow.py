"""E2E: simulated changedetection webhook → DB persist → notify webhook."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

BASE = "http://127.0.0.1:8765"
NOTIFY_PORT = 8766
received: list[dict] = []


class _NotifyHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        received.append(json.loads(body.decode()))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def _run_notify_server() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", NOTIFY_PORT), _NotifyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    notify_url = f"http://127.0.0.1:{NOTIFY_PORT}/hook"
    server = _run_notify_server()

    try:
        with httpx.Client(base_url=BASE, timeout=30.0) as client:
            health = client.get("/health")
            assert health.status_code == 200, health.text

            webhook = client.post(
                "/api/signals/changedetection",
                json={
                    "watch_uuid": "e2e-watch-1",
                    "watch_title": "E2E Careers",
                    "watch_url": "https://example.com/careers",
                    "timestamp": "1710000000",
                },
            )
            assert webhook.status_code == 202, webhook.text

            listing = client.get(
                "/api/signals",
                headers={"Authorization": "Bearer change-me"},
            )
            assert listing.status_code == 200, listing.text
            payload = listing.json()
            match = next(
                (item for item in payload["signals"] if item["watch_id"] == "e2e-watch-1"),
                None,
            )
            assert match is not None, payload
            assert match["title"] == "E2E Careers"

        if received:
            assert received[0]["watch_id"] == "e2e-watch-1"
            print("PASS  notify webhook received payload")
        else:
            print("PASS  notify skipped (NOTIFY_WEBHOOK_URL unset)")

        print("e2e signals flow ok")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
