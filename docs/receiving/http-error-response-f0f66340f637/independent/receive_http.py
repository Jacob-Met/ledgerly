#!/usr/bin/env python3
"""Independent actual-loopback receiving; no author tests or provider access."""
from __future__ import annotations
import argparse, base64, hashlib, http.client, importlib, json, os, platform, re
import sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EXPECTED_SUPPORT = {
    "ledgerly/__init__.py": "a8233412d496773ed05f664cad4d88a0e1642c804e33e019daf6487e11b5b32a",
    "ledgerly/extract.py": "f7644fb7a0d2fedd2e564da8ca490523aa924793b2a67f84fab151d6404e5b20",
}
ORIGINAL_SHA = "de61591ef00eb77ea6efb76fc100a9b6c72b38b10361a1e64a13d811a76ddbb3"
CONTRACT_SHA = "e6a43a9fbf8098bff6aec2364fe80d6cad88380ad649db4dc14abf48bb0a749a"
def utc(): return datetime.now(timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def inventory(root):
    return {name: {"bytes": len((b := (root / name).read_bytes())), "sha256": digest(b)}
            for name in [*EXPECTED_SUPPORT, "ledgerly/paypal.py"]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_root", type=Path)
    ap.add_argument("label", choices=["original", "candidate"])
    ap.add_argument("expected_paypal_sha256")
    args = ap.parse_args()
    owned = Path(__file__).resolve().parent
    contract = owned / "frozen-contract.json"
    assert digest(contract.read_bytes()) == CONTRACT_SHA
    before = inventory(args.source_root)
    assert before["ledgerly/paypal.py"]["sha256"] == args.expected_paypal_sha256
    assert all(before[k]["sha256"] == v for k, v in EXPECTED_SUPPORT.items())
    start = {"utc": utc(), "pid": os.getpid(), "label": args.label,
             "source_root": str(args.source_root), "source_sha256": args.expected_paypal_sha256}
    with (owned / (args.label + "-started.json")).open("x") as f:
        json.dump(start, f, indent=2); f.write("\n")
    sys.path.insert(0, str(args.source_root))
    module = importlib.import_module("ledgerly.paypal")
    error_class = module.PayPalError
    response_class = module.Response
    original_env = os.environ.get("LEDGERLY_ALLOW_NETWORK")
    original_urlopen = urllib.request.urlopen
    checks, cases, requests, responses, server_requests = [], [], [], [], []
    release_stall = threading.Event()
    lock = threading.Lock()
    partial = b'{"short":'
    response_data = {"invoice": "試験", "nested": {"items": [1, "café"]}}
    translated_data = {
        "name": "UNPROCESSABLE_ENTITY", "message": "請求を確認",
        "details": [
            {"issue": "FIRST_ISSUE", "description": "説明 café"},
            {"issue": "SECOND_IGNORED", "description": "not selected"},
        ],
    }
    def check(case, name, actual, expected=True):
        ok = actual == expected
        checks.append({"case": case, "name": name, "ok": ok,
                       "actual": actual, "expected": expected})
        return ok
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_): pass
        def do_GET(self): self.respond()
        def do_POST(self): self.respond()
        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            with lock:
                server_requests.append({"path": self.path, "method": self.command,
                                        "body_hex": body.hex()})
            if self.path == "/v1/oauth2/token":
                status, payload = 200, b'{"access_token":"fixture-token"}'
            elif self.path == "/success":
                status, payload = 201, json.dumps(response_data, ensure_ascii=False).encode()
            elif self.path == "/empty":
                status, payload = 204, b""
            elif self.path == "/stall":
                status, payload = 503, b'{"'
            elif self.path == "/truncated":
                status, payload = 503, partial
            elif self.path == "/translated":
                status, payload = 422, json.dumps(translated_data, ensure_ascii=False).encode()
            else:
                status, payload = 404, b"{}"
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            length = 64 if self.path == "/stall" else len(payload) + (13 if self.path == "/truncated" else 0)
            self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.end_headers()
            if payload:
                self.wfile.write(payload); self.wfile.flush()
            if self.path == "/stall":
                release_stall.wait(3)
            self.close_connection = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02),
                              name="ledgerly-independent-loopback")
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    transport_state = {"case": "", "outside_origin_attempts": [], "translated_boundary": None}
    def state(record):
        e, r, fp = record["error"], record["response"], record["socket_file"]
        return {"http_error_closed": bool(e.closed) if e is not None else None,
                "http_response_closed": bool(r.closed),
                "captured_socket_file_closed": bool(fp.closed) if fp is not None else None}
    def receiving_urlopen(req, data=None, timeout=None, **kwargs):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != server.server_port:
            transport_state["outside_origin_attempts"].append(url)
            raise AssertionError("receiver refuses non-fixture origin")
        path = parsed.path
        headers = {k.lower(): v for k, v in req.header_items()}
        row = {"case": transport_state["case"], "url": url, "path": path,
               "method": req.get_method(), "declared_timeout": timeout,
               "transport_timeout": 0.20 if path == "/stall" else timeout,
               "body_hex": (req.data or b"").hex(), "headers": headers}
        requests.append(row)
        try:
            response = opener.open(req, data=data, timeout=row["transport_timeout"])
        except urllib.error.HTTPError as e:
            responses.append({"case": transport_state["case"], "path": path,
                              "error": e, "response": e.fp, "socket_file": e.fp.fp})
            raise
        else:
            responses.append({"case": transport_state["case"], "path": path,
                              "error": None, "response": response, "socket_file": response.fp})
            return response
    urllib.request.urlopen = receiving_urlopen
    def translated_observer(*a, **kw):
        record = next(r for r in reversed(responses) if r["path"] == "/translated")
        transport_state["translated_boundary"] = state(record)
        return error_class(*a, **kw)
    module.PayPalError = translated_observer
    def close_checks(cid, record, prefix="before_cleanup"):
        snap = state(record)
        for key, value in snap.items():
            if value is not None: check(cid, prefix + "." + key, value)
        return snap
    def cleanup_case(cid):
        for rec in responses:
            if rec["case"] == cid:
                for obj in (rec["error"], rec["response"], rec["socket_file"]):
                    if obj is not None: obj.close()
        if cid == "http_error_stall": release_stall.set()
    def run_case(cid, action):
        transport_state["case"] = cid
        first = len(checks)
        try:
            detail = action()
        except BaseException as e:
            detail = {"unexpected_type": type(e).__name__, "message": str(e),
                      "traceback": traceback.format_exc()}
            check(cid, "completed_expected_path", False)
        finally:
            cleanup_case(cid)
        cases.append({"id": cid, "passed": all(c["ok"] for c in checks[first:]),
                      "detail": detail, "check_count": len(checks) - first})
    started = time.monotonic()
    fatal = None
    try:
        def guard():
            os.environ.pop("LEDGERLY_ALLOW_NETWORK", None)
            previous = len(requests)
            try:
                module.HttpPayPalClient("fixture-client", "fixture-secret", base_url=origin)
            except Exception as e:
                check("network_guard", "exact_type", type(e).__name__, "RuntimeError")
                check("network_guard", "exact_message", str(e),
                      "Network disabled. Set LEDGERLY_ALLOW_NETWORK=1 to use the real sandbox.")
            else:
                check("network_guard", "raises_existing_guard", False)
            check("network_guard", "transport_calls", len(requests) - previous, 0)
            return {"transport_calls": len(requests) - previous}
        run_case("network_guard", guard)
        os.environ["LEDGERLY_ALLOW_NETWORK"] = "1"
        client = module.HttpPayPalClient("fixture-client", "fixture-secret", base_url=origin)
        def success():
            value = client._call("POST", "/success", response_data, {"X-Receiver-Case": "success"})
            check("success_json", "response_type", type(value) is response_class)
            check("success_json", "status", value.status, 201)
            check("success_json", "body", value.body, response_data)
            states = {r["path"]: close_checks("success_json", r, r["path"]) for r in responses if r["case"] == "success_json"}
            return {"result": {"status": value.status, "body": value.body}, "resources": states}
        run_case("success_json", success)
        def empty():
            value = client._call("GET", "/empty")
            check("success_empty", "response_type", type(value) is response_class)
            check("success_empty", "status", value.status, 204)
            check("success_empty", "body", value.body, None)
            rec = responses[-1]
            return {"result": {"status": value.status, "body": value.body},
                    "resources": close_checks("success_empty", rec)}
        run_case("success_empty", empty)
        def error_case(cid, method, path, body=None, extra=None):
            caught = None
            try: client._call(method, path, body, extra)
            except Exception as e: caught = e
            check(cid, "exception_escaped", caught is not None)
            rec = responses[-1]
            snap = close_checks(cid, rec)
            detail = {"exception_type": type(caught).__name__, "message": str(caught),
                      "resources": snap,
                      "http_error_context_identity": caught is not None and caught.__context__ is rec["error"]}
            check(cid, "HTTPError_context_preserved", detail["http_error_context_identity"])
            if cid == "http_error_stall":
                check(cid, "real_timeout", type(caught) is TimeoutError)
                check(cid, "HTTP_status", rec["error"].code, 503)
            elif cid == "http_error_truncated":
                check(cid, "real_incomplete_read", type(caught) is http.client.IncompleteRead)
                got_partial = getattr(caught, "partial", None)
                detail["partial_hex"] = got_partial.hex() if isinstance(got_partial, bytes) else None
                detail["expected_missing_bytes"] = getattr(caught, "expected", None)
                check(cid, "exact_partial_hex", detail["partial_hex"], partial.hex())
                check(cid, "exact_missing_bytes", detail["expected_missing_bytes"], 13)
            else:
                check(cid, "original_error_class", type(caught) is error_class)
                check(cid, "http_status", getattr(caught, "http_status", None), 422)
                got = getattr(caught, "body", {})
                detail["translated_body"] = got
                check(cid, "name", got.get("name"), translated_data["name"])
                check(cid, "message", got.get("message"), translated_data["message"])
                check(cid, "first_detail_only", got.get("details"), translated_data["details"][:1])
                check(cid, "debug_id_shape", bool(re.fullmatch("[0-9a-f]{13}", got.get("debug_id", ""))))
                check(cid, "exact_exception_message", str(caught),
                      "422 UNPROCESSABLE_ENTITY: 請求を確認 [FIRST_ISSUE]")
                detail["before_translation"] = transport_state["translated_boundary"]
                for key, value in (transport_state["translated_boundary"] or {}).items():
                    if value is not None: check(cid, "before_translation." + key, value)
            return detail
        run_case("http_error_stall", lambda: error_case("http_error_stall", "POST", "/stall", {"case": "stall"}, {"X-Receiver-Case": "stall"}))
        run_case("http_error_truncated", lambda: error_case("http_error_truncated", "GET", "/truncated"))
        run_case("translated_error", lambda: error_case("translated_error", "POST", "/translated", {"label": "請求"}, {"X-Receiver-Case": "translated"}))
        auth = [r for r in requests if r["path"] == "/v1/oauth2/token"]
        api = [r for r in requests if r["path"] != "/v1/oauth2/token"]
        check("shared", "one_cached_auth", len(auth), 1)
        check("shared", "five_API_calls", len(api), 5)
        if auth:
            check("shared", "auth_method", auth[0]["method"], "POST")
            check("shared", "auth_form_body", auth[0]["body_hex"], b"grant_type=client_credentials".hex())
            check("shared", "auth_header", auth[0]["headers"].get("authorization"),
                  "Basic " + base64.b64encode(b"fixture-client:fixture-secret").decode())
            check("shared", "auth_content_type", auth[0]["headers"].get("content-type"), "application/x-www-form-urlencoded")
            check("shared", "auth_declared_timeout", auth[0]["declared_timeout"], 20)
        expected = [
            ("/success", "POST", response_data, "success"),
            ("/empty", "GET", None, None),
            ("/stall", "POST", {"case": "stall"}, "stall"),
            ("/truncated", "GET", None, None),
            ("/translated", "POST", {"label": "請求"}, "translated"),
        ]
        ids = []
        for rec, exp in zip(api, expected):
            path, method, body, extra = exp
            check("shared", path + ".path", rec["path"], path)
            check("shared", path + ".method", rec["method"], method)
            check("shared", path + ".body", rec["body_hex"], (b"" if body is None else json.dumps(body).encode()).hex())
            check("shared", path + ".bearer", rec["headers"].get("authorization"), "Bearer fixture-token")
            check("shared", path + ".content_type", rec["headers"].get("content-type"), "application/json")
            check("shared", path + ".extra", rec["headers"].get("x-receiver-case"), extra)
            check("shared", path + ".declared_timeout", rec["declared_timeout"], 30)
            ids.append(rec["headers"].get("paypal-request-id", ""))
        check("shared", "request_IDs", len(set(ids)) == 5 and all(re.fullmatch("[0-9a-f]{32}", v) for v in ids))
        check("shared", "outside_origin_attempts", transport_state["outside_origin_attempts"], [])
        check("shared", "server_received_exact_requests",
              [(r["path"], r["method"], r["body_hex"]) for r in server_requests],
              [(r["path"], r["method"], r["body_hex"]) for r in requests])
    except BaseException:
        fatal = traceback.format_exc()
    finally:
        release_stall.set()
        for rec in responses:
            for obj in (rec["error"], rec["response"], rec["socket_file"]):
                if obj is not None:
                    try: obj.close()
                    except Exception: pass
        urllib.request.urlopen = original_urlopen
        module.PayPalError = error_class
        if original_env is None: os.environ.pop("LEDGERLY_ALLOW_NETWORK", None)
        else: os.environ["LEDGERLY_ALLOW_NETWORK"] = original_env
        server.shutdown(); thread.join(2); server.server_close()
    after = inventory(args.source_root)
    check("shared", "source_bytes_unchanged", before, after)
    check("shared", "server_thread_joined", not thread.is_alive())
    check("shared", "all_captured_resources_closed_after_cleanup",
          all(v is not False for r in responses for v in state(r).values()))
    receipt = {
        "schema": "hamon.independent-http-receiving.v1", "actor": "/root/runtime_integration",
        "identity": "f0f66340f637", "phase": args.label, "started": start,
        "finished_utc": utc(), "elapsed_seconds": time.monotonic() - started,
        "environment": {"python": sys.version, "executable": sys.executable,
                        "platform": platform.platform(), "pid": os.getpid()},
        "contract_sha256": CONTRACT_SHA, "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_before": before, "source_after": after,
        "cases": cases, "checks": checks, "requests": requests, "server_requests": server_requests,
        "case_passes": sum(c["passed"] for c in cases), "case_count": len(cases),
        "check_passes": sum(c["ok"] for c in checks), "check_count": len(checks),
        "fatal_error": fatal,
        "accepted": len(cases) == 6 and all(c["passed"] for c in cases) and all(c["ok"] for c in checks) and fatal is None,
        "limitations": ["Actual local IPv4 HTTP only, fake fixture credentials and token.",
                       "The fixture's transport timeout is 0.20s only for the stalled path; product requested 30.",
                       "No PayPal service, provider request, dependency installation, deployed receiving, or maintained-suite execution.",
                       "Resource observations precede explicit fixture cleanup; underlying response objects were captured before product handling."],
        "cleanup": {"server_thread_joined": not thread.is_alive(), "all_captured_resources_closed": all(v is not False for r in responses for v in state(r).values()),
                    "urlopen_restored": urllib.request.urlopen is original_urlopen, "source_unchanged": before == after}
    }
    raw = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode()
    sys.stdout.buffer.write(raw); sys.stdout.buffer.flush()
    try:
        with (owned / (args.label + "-receipt.json")).open("xb") as f: f.write(raw)
    except OSError as e:
        print("Receipt persistence failed after complete stdout: " + repr(e), file=sys.stderr)
    return 0 if fatal is None else 2
if __name__ == "__main__":
    raise SystemExit(main())
