"""Changed-input challenges added after the first unchanged 18-test receiving run."""
import copy
import unittest
from unittest.mock import patch

import test_reminder_receiving as receiving
from ledgerly.paypal import PayPalError, Response


class ProviderChangeReceiving(unittest.TestCase):
    def setUp(self):
        self.fixture = receiving.AgentReceiving(methodName="runTest")
        self.fixture.setUp()
        self.agent = self.fixture.agent
        self.mock = self.fixture.mock
        self.iid = self.fixture.iid

    def redraft_or_safe_refusal(self):
        try:
            out = self.agent.tool_send_reminder(self.iid)
        except (ValueError, KeyError, PayPalError):
            out = {"ok": False}
        if not out["ok"]:
            self.assertFalse(any(p["kind"] == "send_reminder" for p in self.agent.list_pending()))
            self.assertEqual(receiving.reminders(self.mock), [])
            return None
        return self.agent.pending[out["approval_id"]]

    def test_provider_total_edit_cannot_be_rebound_to_old_local_amount(self):
        old_id = self.fixture.queue()
        inv = self.mock.invoices[self.iid]
        inv["items"][0]["quantity"] = "10.5"
        inv["amount"]["value"] = "500.00"
        inv["due_amount"]["value"] = "500.00"
        self.fixture.assert_no_send_and_permit_closed(old_id)
        fresh = self.redraft_or_safe_refusal()
        if fresh is not None:
            self.assertIn("GBP 500", fresh.payload["note"])
            self.assertNotIn("GBP 800", fresh.payload["note"])
            self.agent.approve(fresh.id)
            self.assertIn("GBP 500", receiving.reminders(self.mock)[0][2]["note"])

    def test_future_provider_due_date_blocks_redraft_as_overdue(self):
        old_id = self.fixture.queue()
        self.mock.invoices[self.iid]["detail"]["payment_term"]["due_date"] = "2026-12-01"
        self.fixture.assert_no_send_and_permit_closed(old_id)
        fresh = self.redraft_or_safe_refusal()
        self.assertIsNone(fresh, "invoice has a future provider due date; no overdue draft is justified")

    def test_changed_provider_recipient_cannot_be_approved_with_old_review_name(self):
        old_id = self.fixture.queue()
        recipient = self.mock.invoices[self.iid]["primary_recipients"][0]["billing_info"]
        recipient["email_address"] = "morgan@example.test"
        recipient["name"] = {"given_name": "Morgan", "surname": "Reviewer"}
        self.fixture.assert_no_send_and_permit_closed(old_id)
        fresh = self.redraft_or_safe_refusal()
        if fresh is not None:
            self.assertIn("morgan@example.test", fresh.summary)
            self.assertIn("Hi Morgan", fresh.payload["note"])
            self.assertNotIn("alex@example.test", fresh.summary)
            self.assertNotIn("Hi Alex", fresh.payload["note"])

    def test_wrong_invoice_identity_read_cannot_create_approval(self):
        body = self.mock.get_invoice(self.iid).body
        body["id"] = "INV2-OTHER-INVOICE"
        before = copy.deepcopy(self.agent.ledger[self.iid].to_dict())
        with patch.object(self.mock, "get_invoice", return_value=Response(200, body)):
            fresh = self.redraft_or_safe_refusal()
        self.assertIsNone(fresh, "a read for a different invoice cannot justify this invoice's reminder")
        self.assertEqual(self.agent.ledger[self.iid].to_dict(), before)

    def test_missing_provider_due_amount_cannot_create_approval(self):
        body = self.mock.get_invoice(self.iid).body
        del body["due_amount"]
        with patch.object(self.mock, "get_invoice", return_value=Response(200, body)):
            fresh = self.redraft_or_safe_refusal()
        self.assertIsNone(fresh, "incomplete provider money facts cannot be bound as a fresh review")

    def test_nonfinite_provider_read_leaves_cached_facts_and_permit_unchanged(self):
        old_id = self.fixture.queue()
        before = copy.deepcopy(self.agent.ledger[self.iid].to_dict())
        body = self.mock.get_invoice(self.iid).body
        body["payments"]["paid_amount"]["value"] = "300.00"
        body["due_amount"]["value"] = "NaN"
        body["status"] = "PARTIALLY_PAID"
        with patch.object(self.mock, "get_invoice", return_value=Response(200, body)):
            self.fixture.assert_no_send_and_permit_closed(old_id)
        self.assertEqual(self.agent.ledger[self.iid].to_dict(), before)

    def test_returned_pending_snapshot_cannot_mutate_reviewed_payload(self):
        aid = self.fixture.queue()
        original = copy.deepcopy(self.agent.pending[aid].payload)
        snapshot = self.agent.list_pending()[0]
        snapshot["payload"]["note"] = "Tampered by display code"
        self.assertEqual(self.agent.pending[aid].payload, original)
        self.agent.approve(aid)
        self.assertEqual(receiving.reminders(self.mock)[0][2]["note"], original["note"])

    def test_preflight_outage_recovery_needs_explicit_retry_and_sends_once(self):
        aid = self.fixture.queue()
        failure = PayPalError(503, "SERVICE_UNAVAILABLE", "Synthetic provider outage")
        with patch.object(self.mock, "get_invoice", side_effect=failure):
            with self.assertRaises(PayPalError):
                self.agent.approve(aid)
        self.assertEqual(receiving.reminders(self.mock), [])
        self.assertEqual(self.agent.pending[aid].status, "PENDING")
        self.agent.approve(aid)
        self.assertEqual(len(receiving.reminders(self.mock)), 1)
        with self.assertRaises(ValueError):
            self.agent.approve(aid)

    def test_delivery_metadata_and_money_format_do_not_churn_same_review(self):
        aid = self.fixture.queue()
        inv = self.mock.invoices[self.iid]
        inv["detail"]["metadata"]["last_update_time"] = "2026-11-10T15:00:00Z"
        inv["amount"]["value"] = "800.0"
        inv["due_amount"]["value"] = "800.000"
        inv["payments"]["paid_amount"]["value"] = "0.000"
        self.agent.tool_get_status(self.iid)
        self.assertEqual(self.agent.pending[aid].status, "PENDING")
        self.assertTrue(self.agent.approve(aid)["reminded"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
