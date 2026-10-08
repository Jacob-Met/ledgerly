"""Reminder receiving checks through the existing core and browser bridge.

Run without optional test dependencies: python -m unittest discover -s tests
-p test_reminder_freshness.py -v
"""
import json
import runpy
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledgerly.agent import Agent
from ledgerly.paypal import PayPalError, SandboxMock


ROOT = Path(__file__).resolve().parents[1]


class ReminderFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 1)
        self.mock = SandboxMock()
        self.agent = Agent(self.mock, {"name": "Example Freelancer", "email_address":
                           "freelancer@example.test"}, today=lambda: self.day)
        text = (ROOT / "fixtures/02_gbp_proofreading.txt").read_text()
        invoice = self.agent.tool_create_invoice(text)["invoices"][0]
        self.iid = invoice["invoice_id"]
        self.agent.approve(invoice["approval_id"])
        self.day = date(2026, 11, 10)

    def reminder(self):
        return self.agent.tool_send_reminder(self.iid)["approval_id"]

    def reminders_sent(self):
        return [r for r in self.mock.requests if r[1].endswith("/remind")]

    def pay(self, amount=None, deliver=True):
        event = self.mock.simulate_payer_payment(self.iid, amount)
        if deliver:
            self.agent.handle_webhook(json.dumps(event).encode())
        return event

    def test_partial_payment_rejects_old_note_and_allows_new_review(self):
        old = self.reminder()
        original = self.agent.pending[old].payload["note"]
        self.pay(Decimal("300"))
        self.assertEqual(self.agent.pending[old].status, "REJECTED")
        self.assertEqual(self.agent.pending[old].payload["note"], original)
        with self.assertRaises(ValueError):
            self.agent.approve(old)
        new = self.reminder()
        self.assertNotEqual(new, old)
        self.assertIn("GBP 500", self.agent.pending[new].payload["note"])
        self.assertEqual(self.reminders_sent(), [])
        self.agent.approve(new)
        self.assertEqual(len(self.reminders_sent()), 1)
        self.assertIn("GBP 500", self.reminders_sent()[0][2]["note"])

    def test_status_sync_invalidates_without_webhook(self):
        rid = self.reminder()
        self.pay(Decimal("300"), deliver=False)
        self.agent.tool_get_status(self.iid)
        self.assertEqual(self.agent.pending[rid].status, "REJECTED")
        self.assertEqual(self.reminders_sent(), [])

    def test_approval_reads_status_when_webhook_was_missed(self):
        rid = self.reminder()
        self.pay(Decimal("300"), deliver=False)
        with self.assertRaises(ValueError):
            self.agent.approve(rid)
        self.assertEqual(self.agent.ledger[self.iid].balance, Decimal("500"))
        self.assertEqual(self.agent.pending[rid].status, "REJECTED")
        self.assertEqual(self.reminders_sent(), [])

    def test_full_payment_is_rejected_before_reminder_request(self):
        rid = self.reminder()
        self.pay(deliver=False)
        with self.assertRaises(ValueError):
            self.agent.approve(rid)
        self.assertEqual(self.agent.pending[rid].status, "REJECTED")
        self.assertEqual(self.reminders_sent(), [])

    def test_new_day_requires_fresh_reminder_draft(self):
        rid = self.reminder()
        original = self.agent.pending[rid].payload["note"]
        self.day = date(2026, 11, 11)
        with self.assertRaises(ValueError):
            self.agent.approve(rid)
        self.assertEqual(self.agent.pending[rid].payload["note"], original)
        self.assertEqual(self.reminders_sent(), [])
        fresh = self.reminder()
        self.assertIn("11 days", self.agent.pending[fresh].payload["note"])

    def test_unchanged_invoice_preserves_exact_reviewed_message(self):
        rid = self.reminder()
        payload = dict(self.agent.pending[rid].payload)
        self.agent.tool_get_status(self.iid)
        self.assertEqual(self.agent.pending[rid].status, "PENDING")
        self.agent.approve(rid)
        sent = self.reminders_sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][2]["subject"], payload["subject"])
        self.assertEqual(sent[0][2]["note"], payload["note"])
        with self.assertRaises(ValueError):
            self.agent.approve(rid)
        self.assertEqual(len(self.reminders_sent()), 1)

    def test_failed_read_leaves_unsent_action_pending_for_explicit_retry(self):
        rid = self.reminder()
        original_get = self.mock.get_invoice

        def unavailable(_):
            raise PayPalError(503, "UNAVAILABLE", "authored read failure")

        self.mock.get_invoice = unavailable
        with self.assertRaises(PayPalError):
            self.agent.approve(rid)
        self.assertEqual(self.agent.pending[rid].status, "PENDING")
        self.assertEqual(self.reminders_sent(), [])
        self.mock.get_invoice = original_get
        self.agent.approve(rid)
        self.assertEqual(len(self.reminders_sent()), 1)

    def test_drafting_refreshes_a_missed_partial_payment(self):
        self.pay(Decimal("300"), deliver=False)
        rid = self.reminder()
        self.assertIn("GBP 500", self.agent.pending[rid].payload["note"])
        self.assertEqual(self.reminders_sent(), [])

    def test_provider_recipient_change_invalidates_existing_approval(self):
        rid = self.reminder()
        self.mock.invoices[self.iid]["primary_recipients"][0]["billing_info"][
            "email_address"] = "other@example.test"
        with self.assertRaises(ValueError):
            self.agent.approve(rid)
        self.assertEqual(self.agent.pending[rid].status, "REJECTED")
        self.assertEqual(self.reminders_sent(), [])

    def test_unchanged_browser_bridge_cancels_stale_partial_payment_reminder(self):
        demo = runpy.run_path(str(ROOT / "web-demo/python/bridge.py"))["Demo"]()
        demo.clock.day = date(2026, 10, 1)
        text = (ROOT / "fixtures/02_gbp_proofreading.txt").read_text()
        first = demo.dispatch({"action": "draft", "text": text})["state"]["pending"][0]
        demo.dispatch({"action": "approve", "action_id": first["id"]})
        demo.dispatch({"action": "advance", "day": "2026-11-10"})
        old = demo.dispatch({"action": "chase"})["state"]["pending"][0]
        after = demo.dispatch({"action": "payment", "invoice_id": first["invoice_id"],
                               "amount": "300"})
        self.assertEqual(after["state"]["pending"], [])
        self.assertEqual(demo.agent.pending[old["id"]].status, "REJECTED")
        self.assertEqual(after["state"]["ledger"][0]["balance"], "500.00")
        fresh = demo.dispatch({"action": "chase"})["state"]["pending"][0]
        self.assertIn("GBP 500", fresh["payload"]["note"])
        self.assertFalse(any(r[1].endswith("/remind") for r in demo.mock.requests))
        demo.dispatch({"action": "approve", "action_id": fresh["id"]})
        self.assertEqual(sum(r[1].endswith("/remind") for r in demo.mock.requests), 1)


if __name__ == "__main__":
    unittest.main()
