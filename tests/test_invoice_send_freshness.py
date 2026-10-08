"""Public approval receiving with authored out-of-band draft changes.

The existing SandboxMock record store represents the mutable provider invoice.
The test does not modify production source, make HTTP calls, or send messages.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import unittest

from ledgerly.agent import Agent
from ledgerly.paypal import SandboxMock

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = []


class InvoiceSendFreshness(unittest.TestCase):
    def prepared(self):
        mock = SandboxMock(now=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
        agent = Agent(mock, {"name": "Fixture Freelancer", "email_address": "freelancer@ledgerly.example"},
                      today=lambda: date(2026, 10, 1))
        result = agent.tool_create_invoice((ROOT / "fixtures/01_simple_usd_hourly.txt").read_text())
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["invoices"]), 1)
        invoice = result["invoices"][0]
        return mock, agent, invoice["invoice_id"], invoice["approval_id"]

    def observe(self, mock, agent, invoice_id, action_id, reviewed):
        before = len(mock.requests)
        error = None
        result = None
        try:
            result = agent.approve(action_id, approver="authored native fixture")
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        calls = deepcopy(mock.requests[before:])
        action = agent.pending[action_id]
        OBSERVATIONS.append({
            "case": self.id(), "reviewed_payload": reviewed,
            "current_provider_invoice": deepcopy(mock.invoices[invoice_id]),
            "approval_result": result, "exception": error,
            "action_status": action.status, "action_result": action.result,
            "calls_during_approval": calls,
            "reviewed_payload_preserved": action.payload == reviewed,
            "ledger": agent.ledger[invoice_id].to_dict(),
        })
        sends = [call for call in calls if call[0] == "POST" and call[1].endswith("/send")]
        return sends, error, action

    def refuses_changed_draft(self, change):
        mock, agent, invoice_id, action_id = self.prepared()
        reviewed = deepcopy(agent.pending[action_id].payload)
        change(mock.invoices[invoice_id])
        sends, error, action = self.observe(mock, agent, invoice_id, action_id, reviewed)
        self.assertEqual(sends, [], "approval must not dispatch a changed provider invoice")
        self.assertIsNotNone(error, "the caller must receive an explicit refusal")
        self.assertEqual(mock.invoices[invoice_id]["status"], "DRAFT")
        self.assertEqual(action.payload, reviewed, "retain the exact original review")

    def test_changed_billing_recipient_is_not_sent(self):
        def change(inv):
            inv["primary_recipients"][0]["billing_info"]["email_address"] = "different@client.example"
        self.refuses_changed_draft(change)

    def test_changed_work_at_the_same_total_is_not_sent(self):
        def change(inv):
            inv["items"][0]["name"] = "Different work the reviewer did not approve"
        self.refuses_changed_draft(change)

    def test_changed_payment_deadline_is_not_sent(self):
        def change(inv):
            inv["detail"]["payment_term"]["due_date"] = "2026-12-31"
        self.refuses_changed_draft(change)

    def test_unchanged_draft_keeps_the_explicit_single_send(self):
        mock, agent, invoice_id, action_id = self.prepared()
        reviewed = deepcopy(agent.pending[action_id].payload)
        sends, error, action = self.observe(mock, agent, invoice_id, action_id, reviewed)
        self.assertIsNone(error)
        self.assertEqual(len(sends), 1)
        self.assertEqual(action.status, "APPROVED")
        self.assertEqual(mock.invoices[invoice_id]["status"], "SENT")
        self.assertEqual(action.payload, reviewed)

    def test_provider_bookkeeping_metadata_keeps_the_same_review(self):
        mock, agent, invoice_id, action_id = self.prepared()
        reviewed = deepcopy(agent.pending[action_id].payload)
        mock.invoices[invoice_id]["detail"]["metadata"]["last_update_time"] = "2026-10-01T00:01:00Z"
        sends, error, action = self.observe(mock, agent, invoice_id, action_id, reviewed)
        self.assertIsNone(error)
        self.assertEqual(len(sends), 1)
        self.assertEqual(action.status, "APPROVED")
        self.assertEqual(action.payload, reviewed)

    @classmethod
    def tearDownClass(cls):
        if destination := os.environ.get("LEDGERLY_SEND_RECEIVING_REPORT"):
            source = ROOT / "ledgerly/agent.py"
            Path(destination).write_text(json.dumps({
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "observations": OBSERVATIONS,
            }, indent=2, default=str) + "\n")


if __name__ == "__main__":
    unittest.main()
