# SPDX-License-Identifier: MIT
"""Actual loopback witness; shortened fixture timeout, no provider access."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch

source = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source))
from ledgerly.paypal import HttpPayPalClient, PayPalError

before = (source / "ledgerly/paypal.py").read_bytes()
results = []
for mode in ("timeout", "valid-error", "invalid-json", "success"):
    release = threading.Event()
    requests = []
    captured = []
    transport_arguments = []
    payload = {
        "timeout": b'{"name": "fixture body never completed"}',
        "valid-error": b'{"name":"FIXTURE_ERROR","message":"synthetic message","details":[{"issue":"SYNTHETIC","description":"synthetic detail"}]}',
        "invalid-json": b'{"',
        "success": b'{"id":"fixture-id","status":"DRAFT"}',
    }[mode]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append({"method": self.command, "path": self.path,
                             "authorization": self.headers.get("Authorization"),
                             "content_type": self.headers.get("Content-Type")})
            self.send_response(200 if mode == "success" else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload[:1] if mode == "timeout" else payload)
            self.wfile.flush()
            if mode == "timeout":
                release.wait(2)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def local_open(request, *, timeout):
        assert request.full_url == base + "/v2/invoicing/invoices/fixture-id"
        transport_arguments.append({"product_timeout": timeout,
                                    "fixture_timeout": 0.15})
        try:
            response = opener.open(request, timeout=0.15)
        except urllib.error.HTTPError as error:
            captured.append((error, error.fp, error.fp.fp))
            raise
        captured.append((response, response, response.fp))
        return response

    started = time.monotonic()
    try:
        with patch.dict(os.environ, {"LEDGERLY_ALLOW_NETWORK": "1"}), patch("urllib.request.urlopen", local_open):
            client = HttpPayPalClient("synthetic-client", "synthetic-secret", base_url=base)
            client._token = "synthetic-token"
            try:
                result = client.get_invoice("fixture-id")
            except BaseException as error:
                outcome = {"type": type(error).__name__, "message": str(error),
                           "http_error_context_retained": bool(captured) and error.__context__ is captured[0][0]}
                if isinstance(error, PayPalError):
                    outcome["body"] = error.body
            else:
                outcome = {"type": "Response", "status": result.status, "body": result.body}
            wrapper, underlying, fp = captured[0]
            observation = {"mode": mode, "outcome": outcome,
                           "wrapper_closed_at_escape": wrapper.closed,
                           "underlying_closed_at_escape": underlying.closed,
                           "underlying_fp_is_none_at_escape": underlying.fp is None,
                           "captured_fp_closed_at_escape": fp.closed,
                           "requests": requests, "transport_arguments": transport_arguments,
                           "elapsed_s": round(time.monotonic() - started, 4)}
            results.append(observation)
    finally:
        for wrapper, _, _ in captured:
            wrapper.close()
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()

with patch.dict(os.environ, {}, clear=False):
    os.environ.pop("LEDGERLY_ALLOW_NETWORK", None)
    try:
        HttpPayPalClient("synthetic-client", "synthetic-secret", base_url="http://127.0.0.1:1")
    except RuntimeError as error:
        guard = {"refused": True, "message": str(error)}
    else:
        guard = {"refused": False}

after = (source / "ledgerly/paypal.py").read_bytes()
assert before == after
print(json.dumps({"source_commit": "79c16c51e5766c5091ba5b5b06b23b24c3ffc1f0",
                  "source": str(source / "ledgerly/paypal.py"),
                  "source_sha256": hashlib.sha256(before).hexdigest(),
                  "source_unchanged": True, "python": sys.version.split()[0],
                  "fixture_scope": "real loopback HTTP GET; cached synthetic token; a local-only urlopen wrapper preserves and records timeout=30 then shortens the fixture socket timeout to 0.15 seconds",
                  "provider_requests": 0, "cases": results, "network_guard": guard}, indent=2))
