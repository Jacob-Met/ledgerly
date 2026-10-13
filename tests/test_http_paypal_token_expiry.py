"""Token lifetime behavior through the real client with an in-memory transport.

These controls use authored credentials/responses and a controlled clock. They do
not contact PayPal or qualify an installed provider integration.
"""
from __future__ import annotations

import base64
from collections import deque
import io
import json
import os
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from ledgerly.paypal import HttpPayPalClient, PayPalError


class Reply(io.BytesIO):
    status = 200


class TokenExpiryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.responses = deque()
        self.requests = []
        self.opened = []
        self.enterContext(patch.dict(os.environ, {"LEDGERLY_ALLOW_NETWORK": "1"}))
        self.enterContext(patch.object(time, "monotonic", side_effect=lambda: self.now))
        self.transport = self.enterContext(patch.object(urllib.request, "urlopen", side_effect=self.urlopen))
        self.client = self.make_client()

    def make_client(self):
        return HttpPayPalClient("authored-client", "authored-secret", "https://fixture.invalid")

    def response(self, body, *, delay=0.0):
        self.responses.append((body, delay))

    def token(self, value="authored-token", lifetime=10, *, delay=0.0):
        self.response({"access_token": value, "expires_in": lifetime}, delay=delay)

    def urlopen(self, request, timeout):
        self.requests.append({"url": request.full_url, "method": request.method,
                              "headers": dict(request.header_items()),
                              "data": request.data, "timeout": timeout})
        if not self.responses:
            raise AssertionError("Unexpected extra request")
        body, delay = self.responses.popleft()
        self.now += delay
        if isinstance(body, Exception):
            raise body
        reply = Reply(body if isinstance(body, bytes) else json.dumps(body).encode("utf-8"))
        self.opened.append(reply)
        return reply

    def test_reuse_before_expiry_and_refresh_at_exact_deadline(self):
        self.token("first", 10)
        self.response({"id": "INV-1"})
        self.assertEqual(self.client.get_invoice("INV-1").body, {"id": "INV-1"})
        self.now = 109.999
        self.response({"id": "INV-1"})
        self.client.get_invoice("INV-1")
        self.now = 110.0
        self.token("second", 10)
        self.response({"id": "INV-1"})
        self.client.get_invoice("INV-1")
        self.assertEqual([r["method"] for r in self.requests], ["POST", "GET", "GET", "POST", "GET"])
        self.assertEqual([r["headers"]["Authorization"] for r in self.requests if r["method"] == "GET"],
                         ["Bearer first", "Bearer first", "Bearer second"])
        self.assertEqual([r["timeout"] for r in self.requests], [20, 30, 30, 20, 30])
        self.assertTrue(all(reply.closed for reply in self.opened))

    def test_fractional_lifetime_counts_response_delay_from_request_start(self):
        self.token("delayed", 10.5, delay=2.5)
        self.assertEqual(self.client._auth(), "delayed")
        self.now = 110.499
        self.assertEqual(self.client._auth(), "delayed")
        self.now = 110.5
        self.token("fresh", 5)
        self.assertEqual(self.client._auth(), "fresh")
        self.assertEqual(len(self.requests), 2)

    def test_system_clock_changes_do_not_control_expiry(self):
        with patch.object(time, "time", side_effect=AssertionError("Wall clock consulted")):
            self.token("first", 2)
            self.assertEqual(self.client._auth(), "first")
            self.now = 101.9
            self.assertEqual(self.client._auth(), "first")
            self.now = 102
            self.token("second", 2)
            self.assertEqual(self.client._auth(), "second")

    def test_already_expired_response_never_reaches_invoice_request(self):
        self.token("too-late", 10, delay=10)
        with self.assertRaisesRegex(ValueError, "expired before"):
            self.client.get_invoice("INV-1")
        self.assertEqual(len(self.requests), 1)
        self.assertIsNone(self.client._token)
        self.assertTrue(self.opened[0].closed)
        self.token("next-explicit-attempt", 10)
        self.response({"id": "INV-1"})
        self.client.get_invoice("INV-1")
        self.assertEqual(self.requests[-1]["headers"]["Authorization"], "Bearer next-explicit-attempt")

    def test_invalid_lifetimes_are_not_cached_or_used(self):
        values = [None, True, False, 0, -1, float("nan"), float("inf"),
                  float("-inf"), 10 ** 400, "10", [], {}]
        for value in values:
            with self.subTest(value=repr(value)):
                client = self.make_client()
                before = len(self.requests)
                self.token(lifetime=value)
                with self.assertRaisesRegex(ValueError, "expires_in"):
                    client.get_invoice("INV-1")
                self.assertEqual(len(self.requests), before + 1)
                self.assertIsNone(client._token)
                self.assertTrue(self.opened[-1].closed)
        self.response({"access_token": "missing-lifetime"})
        with self.assertRaisesRegex(ValueError, "expires_in"):
            self.client._auth()

    def test_nonobject_or_invalid_token_responses_are_not_cached(self):
        bodies = [None, [], 7, "text", {},
                  *({"access_token": value, "expires_in": 10} for value in
                    (None, False, 7, [], {}, "", "with space", "with\nnewline", "nul\0byte", "nonascii-€"))]
        for body in bodies:
            with self.subTest(body=body):
                client = self.make_client()
                before = len(self.requests)
                self.response(body)
                with self.assertRaises(ValueError):
                    client.get_invoice("INV-1")
                self.assertEqual(len(self.requests), before + 1)
                self.assertIsNone(client._token)
                self.assertTrue(self.opened[-1].closed)

    def test_refresh_failure_propagates_without_expired_fallback(self):
        self.token("expired", 1)
        self.assertEqual(self.client._auth(), "expired")
        self.now = 101
        failure = TimeoutError("authored refresh timeout")
        self.response(failure)
        with self.assertRaises(TimeoutError) as caught:
            self.client.get_invoice("INV-1")
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(self.requests), 2)
        self.assertIsNone(self.client._token)
        self.token("later-explicit-request", 1)
        self.response({"id": "INV-1"})
        self.client.get_invoice("INV-1")
        self.assertEqual(self.requests[-1]["headers"]["Authorization"], "Bearer later-explicit-request")

    def test_refresh_json_failure_closes_response_and_allows_explicit_retry(self):
        self.token("expired", 1)
        self.client._auth()
        self.now = 101
        self.response(b"{")
        with self.assertRaises(json.JSONDecodeError):
            self.client.get_invoice("INV-1")
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(self.opened[-1].closed)
        self.assertIsNone(self.client._token)
        self.token("new", 1)
        self.assertEqual(self.client._auth(), "new")

    def test_invoice_authentication_failure_does_not_refresh_or_replay(self):
        self.token("not-expired", 30)
        body = io.BytesIO(b'{"name":"AUTHENTICATION_FAILURE","message":"authored refusal"}')
        failure = urllib.error.HTTPError("https://fixture.invalid", 401, "Unauthorized", {}, body)
        self.addCleanup(failure.close)
        self.response(failure)
        with self.assertRaises(PayPalError) as caught:
            self.client.send_invoice("INV-1", {"send_to_recipient": False})
        self.assertEqual(caught.exception.http_status, 401)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[-1]["url"], "https://fixture.invalid/v2/invoicing/invoices/INV-1/send")

    def test_refresh_precedes_one_send_without_changing_request(self):
        self.token("old", 1)
        self.client._auth()
        self.now = 101
        self.token("new", 30)
        self.response(None)
        body = {"send_to_invoicer": False, "send_to_recipient": True, "note": "authored only"}
        self.client.send_invoice("INV-1", body)
        self.assertEqual(len(self.requests), 3)
        token_request, send = self.requests[-2:]
        self.assertEqual(token_request["url"], "https://fixture.invalid/v1/oauth2/token")
        self.assertEqual(token_request["data"], b"grant_type=client_credentials")
        self.assertEqual(token_request["headers"]["Authorization"],
                         "Basic " + base64.b64encode(b"authored-client:authored-secret").decode())
        self.assertEqual(token_request["headers"]["Content-type"], "application/x-www-form-urlencoded")
        self.assertEqual(send["method"], "POST")
        self.assertEqual(send["headers"]["Authorization"], "Bearer new")
        self.assertEqual(json.loads(send["data"]), body)
        self.assertRegex(send["headers"]["Paypal-request-id"], r"^[0-9a-f]{32}$")

    def test_network_gate_still_refuses_before_transport(self):
        with patch.dict(os.environ, {"LEDGERLY_ALLOW_NETWORK": "0"}):
            with self.assertRaisesRegex(RuntimeError, "Network disabled"):
                self.make_client()
        self.assertEqual(self.transport.call_count, 0)


if __name__ == "__main__":
    unittest.main()
