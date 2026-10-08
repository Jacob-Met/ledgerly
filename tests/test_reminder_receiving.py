"""Independent product receiving tests for Ledgerly queued reminder freshness.

Run with LEDGERLY_SOURCE pointing to an unchanged checkout or a candidate tree:
    LEDGERLY_SOURCE=/path/to/ledgerly python -m unittest discover -s . -v

Only the real Agent, real browser bridge and synthetic SandboxMock are used.
The bridge is imported from the source tree without modification.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

REPO_PARENT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = (REPO_PARENT if (REPO_PARENT / "ledgerly/agent.py").is_file()
                  else Path(__file__).parent / "baseline")
SOURCE = Path(os.environ.get("LEDGERLY_SOURCE", DEFAULT_SOURCE)).resolve()
sys.path.insert(0, str(SOURCE))
from ledgerly.agent import Agent, ApprovalRequired, RulePlanner
from ledgerly.paypal import PayPalError, SandboxMock

spec = importlib.util.spec_from_file_location("ledgerly_review_bridge", SOURCE / "web-demo/python/bridge.py")
bridge = importlib.util.module_from_spec(spec)
# The deployed browser engine loads this directory as its Python module root.
# Match that import context for bridge siblings without changing application code.
with patch.object(sys, "path", [str(SOURCE / "web-demo/python"), *sys.path]):
    spec.loader.exec_module(bridge)

INVOICER = {"name": "Review Freelancer", "email_address": "freelancer@example.test"}
JOB = """From: Alex Reader <alex@example.test>
Subject: Manuscript proofreading

Proofreading: 18 hours @ £40/hr
Style sheet preparation: 2 hrs @ £40/hr
We pay within 30 days of invoice.
"""


class Clock:
    day = date(2026, 10, 1)

    def __call__(self):
        return self.day


def reminders(mock):
    return [r for r in mock.requests if r[1].endswith("/remind")]


class AgentReceiving(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.mock = SandboxMock(now=lambda: datetime.combine(self.clock.day, time.min, tzinfo=timezone.utc))
        self.agent = Agent(self.mock, INVOICER, today=self.clock,
                           webhook_verifier=self.mock.verify_webhook_signature)
        created = self.agent.tool_create_invoice(JOB)
        self.assertTrue(created["ok"], created)
        self.inv = created["invoices"][0]
        self.iid = self.inv["invoice_id"]
        self.assertEqual(Decimal(self.inv["total"]), Decimal("800"))
        self.agent.approve(self.inv["approval_id"])
        self.clock.day = date(2026, 11, 10)

    def queue(self):
        result = self.agent.tool_send_reminder(self.iid)
        self.assertTrue(result["ok"], result)
        return result["approval_id"]

    def deliver(self, event):
        raw = json.dumps(event, separators=(",", ":")).encode()
        return self.agent.handle_webhook(raw, self.mock.sign(raw))

    def pay(self, amount, deliver=True):
        event = self.mock.simulate_payer_payment(self.iid, Decimal(str(amount)))
        if deliver:
            self.deliver(event)
        return event

    def assert_no_send_and_permit_closed(self, action_id):
        before = len(reminders(self.mock))
        try:
            result = self.agent.approve(action_id)
        except (KeyError, ValueError, PayPalError):
            result = None
        self.assertEqual(len(reminders(self.mock)), before, "outgoing reminder attempted despite stale/unknown state")
        self.assertNotEqual(self.agent.pending[action_id].status, "APPROVED", result)
        self.assertEqual(self.agent.ledger[self.iid].reminders_sent, 0)
        self.assertIsNone(self.agent.ledger[self.iid].last_reminder_on)
        with self.assertRaises(ApprovalRequired):
            self.agent.client.remind_invoice(self.iid)

    def test_partial_payment_webhook_invalidates_old_approval(self):
        aid = self.queue()
        old_payload = copy.deepcopy(self.agent.pending[aid].payload)
        self.pay(300)
        self.assertEqual(self.agent.ledger[self.iid].balance, Decimal("500"))
        self.assertNotIn(aid, {p["id"] for p in self.agent.list_pending()})
        self.assert_no_send_and_permit_closed(aid)
        self.assertEqual(self.agent.pending[aid].payload, old_payload, "old approved text was silently rewritten")
        fresh_id = self.queue()
        self.assertNotEqual(aid, fresh_id)
        fresh = self.agent.pending[fresh_id].payload
        self.assertIn("GBP 500", fresh["note"])
        self.assertIn("GBP 300", fresh["note"])
        self.assertNotIn("GBP 800", fresh["note"])
        self.assertEqual(reminders(self.mock), [])
        self.agent.approve(fresh_id)
        self.assertEqual(len(reminders(self.mock)), 1)
        self.assertEqual(reminders(self.mock)[0][2]["note"], fresh["note"])

    def test_status_refresh_invalidates_old_partial_payment_approval(self):
        aid = self.queue()
        self.pay(300, deliver=False)
        self.agent.tool_get_status(self.iid)
        self.assertNotIn(aid, {p["id"] for p in self.agent.list_pending()})
        self.assert_no_send_and_permit_closed(aid)
        fresh_id = self.queue()
        self.assertIn("GBP 500", self.agent.pending[fresh_id].payload["note"])

    def test_missed_payment_webhook_cannot_send_stale_balance(self):
        aid = self.queue()
        self.pay(300, deliver=False)
        self.assertEqual(self.agent.ledger[self.iid].balance, Decimal("800"))
        self.assert_no_send_and_permit_closed(aid)
        self.assertEqual(self.agent.ledger[self.iid].balance, Decimal("500"))

    def test_missed_full_payment_stops_before_outgoing_request(self):
        aid = self.queue()
        self.pay(800, deliver=False)
        self.assert_no_send_and_permit_closed(aid)
        self.assertEqual(self.agent.ledger[self.iid].status, "PAID")

    def test_paid_status_refresh_removes_reminder_from_pending_ui(self):
        aid = self.queue()
        self.pay(800, deliver=False)
        self.agent.tool_get_status(self.iid)
        self.assertNotIn(aid, {p["id"] for p in self.agent.list_pending()})
        self.assert_no_send_and_permit_closed(aid)

    def test_provider_cancel_without_webhook_stops_before_request(self):
        aid = self.queue()
        self.mock.invoices[self.iid]["status"] = "CANCELLED"
        self.assert_no_send_and_permit_closed(aid)
        self.assertEqual(self.agent.ledger[self.iid].status, "CANCELLED")

    def test_drafting_refreshes_provider_after_missed_webhook(self):
        self.pay(300, deliver=False)
        aid = self.queue()
        self.assertIn("GBP 500", self.agent.pending[aid].payload["note"])
        self.assertNotIn("GBP 800", self.agent.pending[aid].payload["note"])
        self.assertEqual(reminders(self.mock), [])

    def test_same_state_preserves_exact_reviewed_text_one_shot(self):
        aid = self.queue()
        payload = copy.deepcopy(self.agent.pending[aid].payload)
        self.agent.tool_get_status(self.iid)
        self.assertIn(aid, {p["id"] for p in self.agent.list_pending()})
        result = self.agent.approve(aid)
        self.assertTrue(result["reminded"])
        sent = reminders(self.mock)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][2]["subject"], payload["subject"])
        self.assertEqual(sent[0][2]["note"], payload["note"])
        self.assertEqual(self.agent.ledger[self.iid].reminders_sent, 1)
        self.assertEqual(self.agent.ledger[self.iid].last_reminder_on, self.clock.day)
        with self.assertRaises(ValueError):
            self.agent.approve(aid)
        with self.assertRaises(ApprovalRequired):
            self.agent.client.remind_invoice(self.iid)
        self.assertEqual(len(reminders(self.mock)), 1)

    def test_unchanged_verified_webhook_does_not_churn_approval(self):
        aid = self.queue()
        payload = copy.deepcopy(self.agent.pending[aid].payload)
        event = self.mock.make_webhook_event("INVOICING.INVOICE.UPDATED", self.iid)
        self.deliver(event)
        self.assertEqual(self.agent.pending[aid].status, "PENDING")
        self.assertEqual(self.agent.pending[aid].payload, payload)
        self.assertTrue(self.agent.approve(aid)["reminded"])
        self.assertEqual(len(reminders(self.mock)), 1)

    def test_aged_firm_reminder_requires_fresh_review(self):
        aid = self.queue()
        payload = copy.deepcopy(self.agent.pending[aid].payload)
        self.assertIn("10 days", payload["subject"])
        self.clock.day += timedelta(days=1)
        self.assert_no_send_and_permit_closed(aid)
        self.assertEqual(self.agent.pending[aid].payload, payload)
        fresh_id = self.queue()
        self.assertIn("11 days", self.agent.pending[fresh_id].payload["subject"])

    def test_approval_read_failure_fails_without_outgoing_or_permit(self):
        aid = self.queue()
        failure = PayPalError(503, "SERVICE_UNAVAILABLE", "Synthetic provider outage")
        with patch.object(self.mock, "get_invoice", side_effect=failure) as read:
            self.assert_no_send_and_permit_closed(aid)
            self.assertGreaterEqual(read.call_count, 1)

    def test_draft_read_failure_does_not_create_unverified_approval(self):
        failure = PayPalError(503, "SERVICE_UNAVAILABLE", "Synthetic provider outage")
        with patch.object(self.mock, "get_invoice", side_effect=failure):
            result = self.agent.run("chase", RulePlanner())
        self.assertEqual(self.agent.list_pending(), [], result)
        self.assertEqual(reminders(self.mock), [])

    def test_delayed_old_payment_event_preserves_the_current_balance_review(self):
        old_event = self.pay(100, deliver=False)
        self.pay(200)
        aid = self.queue()
        payload = copy.deepcopy(self.agent.pending[aid].payload)
        self.assertIn("GBP 500", payload["note"])
        self.deliver(old_event)
        self.assertEqual(self.agent.ledger[self.iid].balance, Decimal("500"))
        self.assertEqual(self.agent.pending[aid].status, "PENDING")
        self.assertEqual(self.agent.pending[aid].payload, payload)
        self.assertNotIn("GBP 700", payload["note"])
        self.assertEqual(reminders(self.mock), [])
        with self.assertRaises(ApprovalRequired):
            self.agent.client.remind_invoice(self.iid)
        self.assertTrue(self.agent.approve(aid)["reminded"])
        self.assertEqual(len(reminders(self.mock)), 1)
        self.assertEqual(reminders(self.mock)[0][2]["subject"], payload["subject"])
        self.assertEqual(reminders(self.mock)[0][2]["note"], payload["note"])
        with self.assertRaises(ValueError):
            self.agent.approve(aid)
        self.assertEqual(len(reminders(self.mock)), 1)

    def test_invoice_send_approval_unchanged_when_status_refreshed(self):
        other = self.agent.tool_create_invoice(JOB)["invoices"][0]
        self.agent.tool_get_status(other["invoice_id"])
        self.assertEqual(self.agent.pending[other["approval_id"]].status, "PENDING")
        self.agent.approve(other["approval_id"])
        self.assertEqual(self.agent.ledger[other["invoice_id"]].status, "SENT")


class BrowserBridgeReceiving(unittest.TestCase):
    def setUp(self):
        bridge.SESSION = bridge.Demo()
        bridge.SESSION.clock.day = date(2026, 10, 1)
        out = self.call("draft", text=JOB)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["result"]["unauthorized_send_blocked"])
        action = out["state"]["pending"][0]
        self.iid = action["invoice_id"]
        self.assertTrue(self.call("approve", action_id=action["id"])["ok"])
        self.call("advance", day="2026-11-10")
        queued = self.call("chase")
        self.aid = next(p["id"] for p in queued["state"]["pending"] if p["kind"] == "send_reminder")

    def call(self, action, **kwargs):
        return json.loads(bridge.handle_json(json.dumps({"action": action, **kwargs})))

    def test_browser_partial_payment_disables_old_approval_and_fresh_draft_sends_500(self):
        payment = self.call("payment", invoice_id=self.iid, amount="300")
        self.assertTrue(payment["ok"], payment)
        self.assertEqual(Decimal(payment["state"]["ledger"][0]["balance"]), Decimal("500"))
        self.assertNotIn(self.aid, {p["id"] for p in payment["state"]["pending"]})
        old = self.call("approve", action_id=self.aid)
        self.assertFalse(old["ok"], old)
        self.assertEqual(reminders(bridge.SESSION.mock), [])
        fresh = self.call("chase")
        action = next(p for p in fresh["state"]["pending"] if p["kind"] == "send_reminder")
        self.assertIn("GBP 500", action["payload"]["note"])
        self.assertNotEqual(self.aid, action["id"])
        self.assertEqual(reminders(bridge.SESSION.mock), [])
        sent = self.call("approve", action_id=action["id"])
        self.assertTrue(sent["ok"], sent)
        self.assertEqual(len(reminders(bridge.SESSION.mock)), 1)
        self.assertIn("GBP 500", reminders(bridge.SESSION.mock)[0][2]["note"])
        self.assertEqual(sent["state"]["external_calls"], 0)

    def test_browser_aged_approval_returns_error_and_no_false_success(self):
        self.call("advance", day="2026-11-11")
        result = self.call("approve", action_id=self.aid)
        self.assertFalse(result["ok"], result)
        self.assertEqual(reminders(bridge.SESSION.mock), [])
        self.assertEqual(result["state"]["ledger"][0]["reminders_sent"], 0)
        self.assertNotIn(self.aid, {p["id"] for p in result["state"]["pending"]})

    def test_browser_failed_preflight_read_returns_error_without_send(self):
        failure = PayPalError(503, "SERVICE_UNAVAILABLE", "Synthetic provider outage")
        with patch.object(bridge.SESSION.mock, "get_invoice", side_effect=failure):
            result = self.call("approve", action_id=self.aid)
        self.assertFalse(result["ok"], result)
        self.assertEqual(reminders(bridge.SESSION.mock), [])
        self.assertEqual(result["state"]["external_calls"], 0)

    def test_browser_full_payment_existing_cancel_and_replay_preserved(self):
        payment = self.call("payment", invoice_id=self.iid, amount="800")
        self.assertTrue(payment["ok"], payment)
        self.assertEqual(payment["state"]["ledger"][0]["status"], "PAID")
        self.assertNotIn(self.aid, {p["id"] for p in payment["state"]["pending"]})
        replay = self.call("replay")
        self.assertTrue(replay["result"]["duplicate"])
        self.assertEqual(reminders(bridge.SESSION.mock), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
