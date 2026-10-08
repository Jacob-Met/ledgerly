"""Independent native receiving of Ledgerly approval failure finality.

Usage: python3 independent_review.py SOURCE_DIR RECEIPT_JSON
The same four unittest methods run on original and candidate source. Only authored
SandboxMock effects occur; bridge.handle_json is the actual current receiver.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import runpy
import sys
import unittest
import urllib.error
from datetime import date

ROOT = Path(sys.argv[1]).resolve()
OUTPUT = Path(sys.argv[2]).resolve()
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "web-demo/python")]

from ledgerly.agent import ApprovalRequired
from ledgerly.paypal import PayPalError

FILES = ("ledgerly/__init__.py", "ledgerly/agent.py", "ledgerly/extract.py",
         "ledgerly/paypal.py", "web-demo/python/bridge.py", "web-demo/python/review.py",
         "fixtures/01_simple_usd_hourly.txt", "fixtures/07_partial_payment_deposit.txt")
OBSERVATIONS = {}


def pins():
    result = {}
    for name in FILES:
        data = (ROOT / name).read_bytes()
        result[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
            "bytes": len(data),
        }
    return result


BEFORE = pins()


class ApprovalReceiving(unittest.TestCase):
    def setUp(self):
        values = runpy.run_path(str(ROOT / "web-demo/python/bridge.py"))
        self.handle = values["handle_json"]
        self.demo = self.handle.__globals__["SESSION"]
        self.demo.clock.day = date(2026, 10, 1)

    def call(self, **request):
        return json.loads(self.handle(json.dumps(request)))

    def create(self, *, deposit=False):
        fixture = "07_partial_payment_deposit.txt" if deposit else "01_simple_usd_hourly.txt"
        reply = self.call(action="draft", text=(ROOT / "fixtures" / fixture).read_text())
        self.assertTrue(reply["ok"], reply)
        self.assertTrue(reply["result"]["unauthorized_send_blocked"])
        self.assertEqual(len(reply["state"]["pending"]), 1)
        return reply["state"]["pending"][0]

    def reminder(self):
        invoice = self.create()
        sent = self.call(action="approve", action_id=invoice["id"])
        self.assertTrue(sent["ok"], sent)
        advanced = self.call(action="advance", day="2026-11-10")
        self.assertTrue(advanced["ok"], advanced)
        chase = self.call(action="chase")
        self.assertTrue(chase["ok"], chase)
        pending = chase["state"]["pending"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kind"], "send_reminder")
        return pending[0]

    def effects(self):
        return {suffix: sum(row[0] == "POST" and row[1].endswith("/" + suffix)
                            for row in self.demo.mock.requests)
                for suffix in ("send", "remind", "payments")}

    @staticmethod
    def response(reply):
        return {"ok": reply["ok"], "error": reply.get("error"),
                "message": reply.get("message"),
                "pending_kinds": [a["kind"] for a in reply["state"]["pending"]],
                "ledger": reply["state"]["ledger"]}

    def audit(self):
        return [row["event"] for row in self.demo.agent.audit
                if row["event"] in ("approved", "approve_failed")]

    def test_reminder_effect_then_timeout_is_terminal_in_bridge(self):
        action = self.reminder()
        original = self.demo.mock.remind_invoice

        def delivered_then_timeout(invoice_id, body=None):
            original(invoice_id, body)
            raise TimeoutError("authored reminder response was lost")

        self.demo.mock.remind_invoice = delivered_then_timeout
        first = self.call(action="approve", action_id=action["id"])
        first_status = self.demo.agent.pending[action["id"]].status
        first_effects = self.effects()
        retry = self.call(action="approve", action_id=action["id"])
        with self.assertRaises(ApprovalRequired):
            self.demo.agent.client.remind_invoice(action["invoice_id"])
        OBSERVATIONS["reminder_response_lost"] = {
            "first": self.response(first), "status_after_first": first_status,
            "effects_after_first": first_effects, "retry": self.response(retry),
            "effects_after_retry": self.effects(), "permit_revoked": True,
            "audit": self.audit(),
        }
        self.assertFalse(first["ok"])
        self.assertEqual(first["error"], "TimeoutError")
        self.assertEqual(first_status, "FAILED")
        self.assertEqual(first["state"]["pending"], [])
        self.assertFalse(retry["ok"])
        self.assertEqual(self.effects(), first_effects)
        self.assertEqual(first_effects["remind"], 1)
        self.assertEqual(self.audit().count("approve_failed"), 1)

    def test_deposit_followup_read_failure_cannot_replay_effects(self):
        action = self.create(deposit=True)

        def unavailable(invoice_id):
            raise urllib.error.URLError("authored post-payment status response was lost")

        self.demo.mock.get_invoice = unavailable
        first = self.call(action="approve", action_id=action["id"])
        first_status = self.demo.agent.pending[action["id"]].status
        first_effects = self.effects()
        retry = self.call(action="approve", action_id=action["id"])
        with self.assertRaises(ApprovalRequired):
            self.demo.agent.client.record_payment(action["invoice_id"], {})
        OBSERVATIONS["deposit_followup_read"] = {
            "first": self.response(first), "status_after_first": first_status,
            "effects_after_first": first_effects, "retry": self.response(retry),
            "effects_after_retry": self.effects(), "permit_revoked": True,
            "provider_status": self.demo.mock.invoices[action["invoice_id"]]["status"],
            "audit": self.audit(),
        }
        self.assertFalse(first["ok"])
        self.assertEqual(first["error"], "URLError")
        self.assertEqual(first_status, "FAILED")
        self.assertEqual(first["state"]["pending"], [])
        self.assertEqual(first_effects, {"send": 1, "remind": 0, "payments": 1})
        self.assertFalse(retry["ok"])
        self.assertEqual(self.effects(), first_effects)
        self.assertEqual(self.audit().count("approve_failed"), 1)

    def test_reminder_preflight_read_keeps_explicit_retry(self):
        action = self.reminder()
        original_get = self.demo.mock.get_invoice

        def unavailable(invoice_id):
            raise urllib.error.URLError("authored read before reminder")

        self.demo.mock.get_invoice = unavailable
        first = self.call(action="approve", action_id=action["id"])
        first_status = self.demo.agent.pending[action["id"]].status
        first_effects = self.effects()
        self.demo.mock.get_invoice = original_get
        retry = self.call(action="approve", action_id=action["id"])
        outgoing = [r for r in self.demo.mock.requests if r[1].endswith("/remind")]
        OBSERVATIONS["read_only_preflight"] = {
            "first": self.response(first), "status_after_first": first_status,
            "effects_after_first": first_effects, "retry": self.response(retry),
            "effects_after_retry": self.effects(),
            "final_status": self.demo.agent.pending[action["id"]].status,
            "reviewed_note_unchanged": outgoing[0][2]["note"] == action["payload"]["note"]
                                      if outgoing else False,
            "audit": self.audit(),
        }
        self.assertFalse(first["ok"])
        self.assertEqual(first["error"], "URLError")
        self.assertEqual(first_status, "PENDING")
        self.assertEqual([a["id"] for a in first["state"]["pending"]], [action["id"]])
        self.assertEqual(first_effects["remind"], 0)
        self.assertTrue(retry["ok"], retry)
        self.assertEqual(retry["state"]["pending"], [])
        self.assertEqual(self.effects()["remind"], 1)
        self.assertEqual(outgoing[0][2]["note"], action["payload"]["note"])
        self.assertEqual(self.audit().count("approve_failed"), 0)

    def test_known_provider_error_preserves_failure_body_and_gate(self):
        action = self.create()
        error = PayPalError(503, "UNAVAILABLE", "authored provider refusal")
        attempted = []

        def refused(invoice_id, body=None):
            attempted.append(invoice_id)
            raise error

        self.demo.mock.send_invoice = refused
        first = self.call(action="approve", action_id=action["id"])
        first_status = self.demo.agent.pending[action["id"]].status
        body_retained = self.demo.agent.pending[action["id"]].result == error.body
        retry = self.call(action="approve", action_id=action["id"])
        with self.assertRaises(ApprovalRequired):
            self.demo.agent.client.send_invoice(action["invoice_id"])
        OBSERVATIONS["known_provider_error"] = {
            "first": self.response(first), "status_after_first": first_status,
            "retry": self.response(retry), "attempts": len(attempted),
            "body_retained": body_retained, "effects": self.effects(),
            "permit_revoked": True, "audit": self.audit(),
        }
        self.assertFalse(first["ok"])
        self.assertEqual(first["error"], "PayPalError")
        self.assertEqual(first_status, "FAILED")
        self.assertTrue(body_retained)
        self.assertEqual(first["state"]["pending"], [])
        self.assertFalse(retry["ok"])
        self.assertEqual(len(attempted), 1)
        self.assertEqual(self.effects(), {"send": 0, "remind": 0, "payments": 0})
        self.assertEqual(self.audit().count("approve_failed"), 1)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ApprovalReceiving))
    after = pins()
    receipt = {
        "reviewer": "estate_continuity-3dcb83a1", "source": str(ROOT),
        "command": [sys.executable, *sys.argv], "python": sys.version,
        "platform": platform.platform(), "tests_run": result.testsRun,
        "successful": result.wasSuccessful(), "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "failure_details": [{"test": str(test), "traceback": trace}
                            for test, trace in result.failures + result.errors],
        "source_files": BEFORE, "source_unchanged": BEFORE == after,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "observations": OBSERVATIONS,
        "scope": "Four unchanged actual Python bridge/API checks; authored SandboxMock only. "
                 "No real provider, browser rendering, full-suite, installation or deployment claim.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if BEFORE != after:
        raise SystemExit("source changed during qualification")
    raise SystemExit(0 if result.wasSuccessful() else 1)
