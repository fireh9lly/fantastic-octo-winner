#!/usr/bin/env python3
"""LAN relay that serves your Claude plan usage to the CrossMux "Claude Usage" app.

Why a relay?  The usage numbers come from the same endpoint Claude Code's
/usage screen uses, authenticated with your Claude Code OAuth login. Those
access tokens expire after a few hours and Claude Code refreshes them on your
computer. Running this relay on that computer lets the e-ink device always get
a fresh token's worth of data without ever holding your Claude credentials:
the device only knows a random relay key.

Standard library only. Python 3.8+.

    python3 claude_usage_relay.py            # listen on 0.0.0.0:8787
    python3 claude_usage_relay.py --port 9000

On first start it creates a random relay key, then prints the exact
/claude-usage.json to copy onto the device's SD card.

Token sources, in order:
  1. $CLAUDE_USAGE_TOKEN (e.g. a token from `claude setup-token`)
  2. ~/.claude/.credentials.json   (Linux / Windows / WSL)
  3. macOS Keychain item "Claude Code-credentials"
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
CACHE_SECONDS = 60
KEY_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "crossmux-claude-relay" / "key"


class TokenError(Exception):
    pass


def _token_from_credentials(data: dict) -> str:
    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        raise TokenError("no claudeAiOauth.accessToken in Claude Code credentials")
    expires_ms = oauth.get("expiresAt")
    if isinstance(expires_ms, (int, float)) and expires_ms / 1000 < time.time():
        raise TokenError(
            "Claude Code's access token has expired. Open Claude Code (any command, e.g. `claude -p hi`) "
            "so it refreshes its login, then try again."
        )
    return token


def read_token() -> str:
    env = os.environ.get("CLAUDE_USAGE_TOKEN", "").strip()
    if env:
        return env

    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    cred_file = config_dir / ".credentials.json"
    if cred_file.is_file():
        try:
            return _token_from_credentials(json.loads(cred_file.read_text()))
        except json.JSONDecodeError as exc:
            raise TokenError(f"could not parse {cred_file}: {exc}") from exc

    if platform.system() == "Darwin":
        try:
            raw = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise TokenError("Claude Code credentials not found in the macOS Keychain; run `claude` and log in") from exc
        return _token_from_credentials(json.loads(raw))

    raise TokenError(f"{cred_file} not found; run `claude` and log in, or set CLAUDE_USAGE_TOKEN")


class UsageCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._body: bytes | None = None
        self._fetched = 0.0

    def get(self) -> tuple[int, bytes]:
        with self._lock:
            if self._body is not None and time.time() - self._fetched < CACHE_SECONDS:
                return 200, self._body
            status, body = fetch_usage()
            if status == 200:
                self._body, self._fetched = body, time.time()
            return status, body


def fetch_usage() -> tuple[int, bytes]:
    try:
        token = read_token()
    except TokenError as exc:
        return 503, json.dumps({"error": str(exc)}).encode()

    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": BETA_HEADER,
            "Accept": "application/json",
            "User-Agent": "crossmux-claude-usage-relay/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200, response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:500].decode("utf-8", "replace")
        # 401 from upstream means *Claude's* token is bad, not the relay key:
        # report 502 so the device does not say "update your token".
        return 502, json.dumps({"error": f"upstream HTTP {exc.code}", "detail": detail}).encode()
    except (urllib.error.URLError, socket.timeout) as exc:
        return 502, json.dumps({"error": f"upstream unreachable: {exc}"}).encode()


def load_or_create_key() -> str:
    if KEY_FILE.is_file():
        return KEY_FILE.read_text().strip()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(24)
    KEY_FILE.write_text(key + "\n")
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("10.255.255.255", 1))  # no packets are sent
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def make_handler(key: str, cache: UsageCache):
    expected = f"Bearer {key}".encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ClaudeUsageRelay/1.0"

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if self.path.split("?", 1)[0] != "/usage":
                self._send(404, b'{"error":"not found"}')
                return
            supplied = self.headers.get("Authorization", "").encode()
            if not hmac.compare_digest(supplied, expected):
                self._send(401, b'{"error":"bad relay key"}')
                return
            status, body = cache.get()
            self._send(status, body)

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write(f"{self.log_date_time_string()} {self.address_string()} {fmt % args}\n")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="interface to bind (default: all)")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--check", action="store_true", help="fetch usage once, print it, and exit")
    args = parser.parse_args()

    if args.check:
        status, body = fetch_usage()
        print(f"HTTP {status}")
        print(json.dumps(json.loads(body), indent=2))
        sys.exit(0 if status == 200 else 1)

    key = load_or_create_key()
    config = {"url": f"http://{lan_ip()}:{args.port}/usage", "token": key}
    print("Claude usage relay running. Save this as /claude-usage.json on the device's SD card:\n")
    print(json.dumps(config, indent=2))
    print(f"\n(relay key stored in {KEY_FILE})\n")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(key, UsageCache()))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
