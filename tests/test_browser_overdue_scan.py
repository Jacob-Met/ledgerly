"""The browser's deterministic overdue scan reaches every current invoice."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web-demo" / "python"))
from bridge import Demo
from ledgerly.agent import ApprovalRequired
from ledgerly.paypal import SandboxMock

SOURCE = (ROOT / "fixtures" / "01_simple_usd_hourly.txt").read_text()


class BrowserOverdueScan(unittest.TestCase):
    def invoices(self, count):
        demo = Demo()
        demo.clock.day = date(2026, 10, 8)
        self.assertIsInstance(demo.mock, SandboxMock)
        ids = []
        for index in range(count):
            text = SOURCE.replace("Landing page copy - let's go", f"Fictional batch invoice {index + 1}")
            draft = demo.dispatch({"action": "draft", "text": text})
            self.assertTrue(draft["result"]["unauthorized_send_blocked"])
            self.assertEqual(len(draft["state"]["pending"]), 1)
            action = draft["state"]["pending"][0]
            self.assertEqual(action["kind"], "send_invoice")
            sent = demo.dispatch({"action": "approve", "action_id": action["id"]})
            self.assertTrue(sent["result"]["approved"])
            ids.append(action["invoice_id"])
        if ids:
            due = demo.agent.ledger[ids[0]].due_on
            demo.dispatch({"action": "advance", "day": (due + timedelta(days=1)).isoformat()})
        return demo, ids

    @staticmethod
    def reminder_requests(demo):
        return [(path, body) for method, path, body in demo.mock.requests
                if method == "POST" and path.endswith("/remind")]

    def scan(self, demo):
        reply = demo.dispatch({"action": "chase"})
        self.last_scan_message = reply["result"]["final"]
        self.assertEqual(reply["state"]["external_calls"], 0)
        self.assertTrue(all(a["kind"] == "send_reminder" for a in reply["state"]["pending"]))
        return reply["state"]["pending"]

    def seed_reminders(self, demo, ids):
        for invoice_id in ids:
            self.assertTrue(demo.agent.tool_send_reminder(invoice_id)["ok"])
        return deepcopy(demo.agent.list_pending())

    def test_empty_and_small_ledgers_keep_normal_scan_behavior(self):
        for count in (0, 1, 10):
            with self.subTest(invoice_count=count):
                demo, ids = self.invoices(count)
                pending = self.scan(demo)
                self.assertEqual([a["invoice_id"] for a in pending], ids)
                self.assertNotEqual(self.last_scan_message, "step limit reached")
                self.assertEqual(self.reminder_requests(demo), [])
                self.assertEqual(self.scan(demo), pending)

    def test_larger_fresh_batch_reaches_every_invoice_without_sending(self):
        demo, ids = self.invoices(13)
        pending = self.scan(demo)
        self.assertEqual([a["invoice_id"] for a in pending], ids)
        self.assertNotEqual(self.last_scan_message, "step limit reached")
        self.assertEqual(len({a["id"] for a in pending}), 13)
        self.assertEqual(self.reminder_requests(demo), [])
        self.assertEqual(self.scan(demo), pending)
        with self.assertRaises(ApprovalRequired):
            demo.agent.client.remind_invoice(ids[-1])
        self.assertEqual(self.reminder_requests(demo), [])

    def test_pending_prefix_does_not_hide_tail_invoices(self):
        demo, ids = self.invoices(13)
        first = self.seed_reminders(demo, ids[:11])
        pending = self.scan(demo)
        self.assertEqual(pending[:11], first)
        self.assertEqual([a["invoice_id"] for a in pending[11:]], ids[11:])
        self.assertEqual(self.reminder_requests(demo), [])
        self.assertEqual(self.scan(demo), pending)

    def test_cooldown_prefix_reaches_tail_and_approval_stays_per_action(self):
        demo, ids = self.invoices(13)
        first = self.seed_reminders(demo, ids[:11])
        for action in first:
            demo.dispatch({"action": "approve", "action_id": action["id"]})
        self.assertEqual(len(self.reminder_requests(demo)), 11)
        tail = self.scan(demo)
        self.assertEqual([a["invoice_id"] for a in tail], ids[11:])
        self.assertEqual(len(self.reminder_requests(demo)), 11)
        self.assertEqual(self.scan(demo), tail)
        demo.dispatch({"action": "approve", "action_id": tail[1]["id"]})
        self.assertEqual(demo.agent.ledger[ids[-1]].reminders_sent, 1)
        self.assertEqual(demo.agent.ledger[ids[-2]].reminders_sent, 0)
        self.assertEqual(demo.agent.list_pending(), [tail[0]])
        path, body = self.reminder_requests(demo)[-1]
        self.assertTrue(path.endswith("/" + ids[-1] + "/remind"))
        self.assertEqual(body["subject"], tail[1]["payload"]["subject"])
        self.assertEqual(body["note"], tail[1]["payload"]["note"])
        demo.dispatch({"action": "reject", "action_id": tail[0]["id"]})
        self.assertEqual(demo.agent.list_pending(), [])
        for action in tail:
            with self.assertRaises(ValueError):
                demo.agent.approve(action["id"])
        self.assertEqual(len(self.reminder_requests(demo)), 12)

    def test_scan_observes_changed_tail_invoices_and_replaces_only_stale_actions(self):
        demo, ids = self.invoices(13)
        original = self.seed_reminders(demo, ids)
        # Provider-side changes are real SandboxMock operations. Withhold their
        # webhook delivery so the scan must refresh the stale local invoice facts.
        demo.mock.simulate_payer_payment(ids[-2])
        demo.mock.simulate_payer_payment(ids[-1], Decimal("100"))
        self.assertEqual(demo.agent.ledger[ids[-2]].status, "SENT")
        self.assertEqual(demo.agent.ledger[ids[-1]].paid_amount, Decimal(0))
        pending = self.scan(demo)
        self.assertEqual(demo.agent.ledger[ids[-2]].status, "PAID")
        self.assertEqual(demo.agent.ledger[ids[-1]].paid_amount, Decimal("100"))
        self.assertEqual(pending[:11], original[:11])
        self.assertEqual(len(pending), 12)
        replacement = pending[-1]
        self.assertEqual(replacement["invoice_id"], ids[-1])
        self.assertNotEqual(replacement["id"], original[-1]["id"])
        self.assertNotEqual(replacement["payload"]["note"], original[-1]["payload"]["note"])
        self.assertEqual(demo.agent.pending[original[-1]["id"]].payload, original[-1]["payload"])
        self.assertEqual(demo.agent.pending[original[-2]["id"]].payload, original[-2]["payload"])
        self.assertEqual(self.reminder_requests(demo), [])
        for old in original[-2:]:
            with self.assertRaises(ValueError):
                demo.agent.approve(old["id"])
        demo.dispatch({"action": "approve", "action_id": replacement["id"]})
        self.assertEqual(len(self.reminder_requests(demo)), 1)
        path, body = self.reminder_requests(demo)[0]
        self.assertTrue(path.endswith("/" + ids[-1] + "/remind"))
        self.assertEqual(body["note"], replacement["payload"]["note"])

    def test_unrelated_planner_retains_general_step_guard(self):
        class RepeatedReadPlanner:
            def next_step(self, goal, history, tools):
                return {"tool": "list_overdue", "args": {}}

        demo = Demo()
        result = demo.agent.run("bounded read control", RepeatedReadPlanner())
        self.assertEqual(result["final"], "step limit reached")
        self.assertEqual(len([h for h in result["history"] if h["role"] == "tool"]), 12)
        self.assertEqual(result["pending"], [])
        self.assertEqual(demo.mock.requests, [])


if __name__ == "__main__":
    unittest.main()
