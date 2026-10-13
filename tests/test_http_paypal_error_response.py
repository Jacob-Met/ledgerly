# SPDX-License-Identifier: MIT
"""Synthetic localhost transport receiving; no PayPal account or provider calls."""
from __future__ import annotations

from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from types import SimpleNamespace
import threading
import urllib.error
import urllib.request

import pytest

from ledgerly.paypal import HttpPayPalClient, PayPalError


@pytest.fixture
def local_http(monkeypatch):
    """Receive genuine HTTP responses, shortening only the local socket timeout."""
    fixtures = []

    def start(status, payload, *, stall=False, extra_length=0, read_error=None):
        state = SimpleNamespace(requests=[], timeouts=[], responses=[], release=threading.Event())

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                state.requests.append({"method": self.command, "path": self.path,
                                       "headers": dict(self.headers)})
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload) + extra_length))
                self.end_headers()
                self.wfile.write(payload[:1] if stall else payload)
                self.wfile.flush()
                if stall:
                    state.release.wait(2)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        fixtures.append((state, server, thread))
        base = f"http://127.0.0.1:{server.server_port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def local_open(request, *, timeout):
            assert request.full_url == base + "/v2/invoicing/invoices/fixture-id"
            state.timeouts.append(timeout)
            try:
                response = opener.open(request, timeout=0.15)
            except urllib.error.HTTPError as error:
                state.responses.append((error, error.fp, error.fp.fp))
                if read_error is not None:
                    def interrupted_read(*_, **__):
                        raise read_error
                    error.read = interrupted_read
                raise
            state.responses.append((response, response, response.fp))
            return response

        monkeypatch.setenv("LEDGERLY_ALLOW_NETWORK", "1")
        monkeypatch.setattr(urllib.request, "urlopen", local_open)
        client = HttpPayPalClient("synthetic-client", "synthetic-secret", base_url=base)
        client._token = "synthetic-token"
        return client, state

    yield start
    for state, server, thread in reversed(fixtures):
        for wrapper, _, _ in state.responses:
            wrapper.close()
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()


def assert_transport(state):
    assert state.timeouts == [30]
    assert len(state.requests) == 1
    request = state.requests[0]
    assert request["method"] == "GET"
    assert request["path"] == "/v2/invoicing/invoices/fixture-id"
    headers = {key.lower(): value for key, value in request["headers"].items()}
    assert headers["authorization"] == "Bearer synthetic-token"
    assert headers["content-type"] == "application/json"
    assert re.fullmatch(r"[0-9a-f]{32}", headers["paypal-request-id"])


def assert_closed(state):
    assert len(state.responses) == 1
    wrapper, response, fp = state.responses[0]
    assert wrapper.closed
    assert response.closed
    assert response.fp is None
    assert fp.closed


def test_error_read_timeout_closes_real_response(local_http):
    client, state = local_http(503, b'{"name":"fixture body never completed"}', stall=True)
    with pytest.raises(TimeoutError, match="timed out") as caught:
        client.get_invoice("fixture-id")
    assert caught.value.__context__ is state.responses[0][0]
    assert_transport(state)
    assert_closed(state)


@pytest.mark.parametrize("status", [401, 429, 503])
def test_error_translation_closes_real_response(local_http, status):
    body = {"name": "FIXTURE_ERROR", "message": "synthetic message",
            "details": [{"issue": "SYNTHETIC", "description": "synthetic detail"}]}
    client, state = local_http(status, json.dumps(body).encode())
    with pytest.raises(PayPalError) as caught:
        client.get_invoice("fixture-id")
    error = caught.value
    assert error.http_status == status
    assert str(error) == f"{status} FIXTURE_ERROR: synthetic message [SYNTHETIC]"
    assert {key: value for key, value in error.body.items() if key != "debug_id"} == body
    assert re.fullmatch(r"[0-9a-f]{13}", error.body["debug_id"])
    assert error.__context__ is state.responses[0][0]
    assert error.__cause__ is None and not error.__suppress_context__
    assert_transport(state)
    assert_closed(state)


@pytest.mark.parametrize("payload,exception,message", [
    (b'{"', json.JSONDecodeError, "Unterminated string"),
    (b"[]", AttributeError, "'list' object has no attribute 'get'"),
])
def test_error_parse_failure_closes_real_response(local_http, payload, exception, message):
    client, state = local_http(503, payload)
    with pytest.raises(exception, match=message) as caught:
        client.get_invoice("fixture-id")
    assert caught.value.__context__ is state.responses[0][0]
    assert_transport(state)
    assert_closed(state)


def test_error_empty_body_preserves_translation(local_http):
    client, state = local_http(503, b"")
    with pytest.raises(PayPalError) as caught:
        client.get_invoice("fixture-id")
    assert caught.value.http_status == 503
    assert str(caught.value) == "503 HTTP_ERROR: HTTP Error 503: Service Unavailable"
    assert caught.value.body["details"] == []
    assert_transport(state)
    assert_closed(state)


def test_error_incomplete_body_keeps_original_exception(local_http):
    payload = b'{"name":"fixture truncated"}'
    client, state = local_http(503, payload, extra_length=5)
    with pytest.raises(IncompleteRead) as caught:
        client.get_invoice("fixture-id")
    assert caught.value.partial == payload
    assert caught.value.expected == 5
    assert caught.value.__context__ is state.responses[0][0]
    assert_transport(state)
    assert_closed(state)


def test_error_interrupted_read_closes_unread_response(local_http):
    interruption = KeyboardInterrupt("synthetic interrupted read")
    client, state = local_http(503, b'{"name":"fixture unread"}', read_error=interruption)
    with pytest.raises(KeyboardInterrupt) as caught:
        client.get_invoice("fixture-id")
    assert caught.value is interruption
    assert caught.value.__context__ is state.responses[0][0]
    assert_transport(state)
    assert_closed(state)


@pytest.mark.parametrize("status,payload,expected", [
    (200, '{"id":"fixture-id","description":"テスト"}'.encode(),
     {"id": "fixture-id", "description": "テスト"}),
    (204, b"", None),
])
def test_success_response_and_transport_are_preserved(local_http, status, payload, expected):
    client, state = local_http(status, payload)
    response = client.get_invoice("fixture-id")
    assert response.status == status
    assert response.body == expected
    assert_transport(state)
    assert_closed(state)


def test_constructor_still_requires_explicit_network_opt_in(monkeypatch):
    monkeypatch.delenv("LEDGERLY_ALLOW_NETWORK", raising=False)
    with pytest.raises(RuntimeError, match="Network disabled"):
        HttpPayPalClient("synthetic-client", "synthetic-secret", base_url="http://127.0.0.1:1")
