"""Receiving tests for read-only completed reviews through the actual Demo."""
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web-demo/python"))
import bridge


class CompletedReviewTests(unittest.TestCase):
    def setUp(self):
        self.previous_session = bridge.SESSION
        self.demo = bridge.Demo()
        self.demo.clock.day = date(2026, 1, 2)
        bridge.SESSION = self.demo
        self.email = (ROOT / "fixtures/01_simple_usd_hourly.txt").read_text()
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("External HTTP is forbidden in this sandbox control"))
        self.network.start()

    def tearDown(self):
        self.network.stop()
        bridge.SESSION = self.previous_session

    def call(self, action, **payload):
        return json.loads(bridge.handle_json(json.dumps({"action": action, **payload})))

    def draft(self, text=None):
        reply = self.call("draft", text=self.email if text is None else text)
        self.assertTrue(reply["ok"], reply)
        return copy.deepcopy(reply["state"]["pending"][-1])

    def history(self):
        return self.demo.snapshot()["completed_reviews"]

    def reminder(self):
        invoice = self.draft()
        self.assertTrue(self.call("approve", action_id=invoice["id"])["ok"])
        due = self.demo.agent.ledger[invoice["invoice_id"]].due_on
        self.assertIsNotNone(due)
        self.assertTrue(self.call("advance", day=(due + timedelta(days=1)).isoformat())["ok"])
        reply = self.call("chase")
        self.assertTrue(reply["ok"], reply)
        return copy.deepcopy(next(a for a in reply["state"]["pending"] if a["kind"] == "send_reminder"))

    def test_empty_and_pending_do_not_become_completed_reviews(self):
        self.assertEqual(self.history(), [])
        action = self.draft()
        before = self.demo.agent.export_state()
        requests = copy.deepcopy(self.demo.mock.requests)
        self.assertEqual(self.history(), [])
        self.assertEqual(self.demo.snapshot()["pending"], [action])
        self.assertEqual(self.demo.agent.export_state(), before)
        self.assertEqual(self.demo.mock.requests, requests)
        with self.assertRaises(bridge.ApprovalRequired):
            self.demo.agent.client.send_invoice(action["invoice_id"])
        self.assertEqual(self.demo.mock.requests, requests)

    def test_approved_and_rejected_original_proposals_remain_inspectable(self):
        approved = self.draft()
        self.assertTrue(self.call("approve", action_id=approved["id"])["ok"])
        rejected = self.draft()
        self.assertTrue(self.call("reject", action_id=rejected["id"])["ok"])
        requests = copy.deepcopy(self.demo.mock.requests)
        rows = self.history()
        self.assertEqual([r["id"] for r in rows], [rejected["id"], approved["id"]])
        self.assertEqual([r["status"] for r in rows], ["REJECTED", "APPROVED"])
        self.assertEqual(rows[0]["result"], {"reason": "Rejected by the browser visitor"})
        self.assertEqual([r["payload"] for r in rows], [rejected["payload"], approved["payload"]])
        self.assertEqual([r["created_at"] for r in rows], [rejected["created_at"], approved["created_at"]])
        self.assertEqual(self.demo.snapshot()["pending"], [])
        self.assertEqual(self.demo.mock.requests, requests)

    def test_original_proposal_and_result_are_detached_from_later_records(self):
        queued = self.draft()
        self.assertTrue(self.call("approve", action_id=queued["id"])["ok"])
        original_result = copy.deepcopy(self.demo.agent.pending[queued["id"]].result)
        provider = self.demo.mock.invoices[queued["invoice_id"]]
        provider["items"][0]["unit_amount"]["value"] = "999.00"
        agent_before = self.demo.agent.export_state()
        provider_before = copy.deepcopy(self.demo.mock.invoices)
        requests = copy.deepcopy(self.demo.mock.requests)
        displayed = self.history()[0]
        self.assertEqual(displayed["payload"], queued["payload"])
        displayed["payload"]["invoice"]["items"][0]["unit_amount"]["value"] = "123.00"
        displayed["result"]["payer_view"] = "authored display-only mutation"
        self.assertEqual(self.history()[0]["payload"], queued["payload"])
        self.assertEqual(self.history()[0]["result"], original_result)
        self.assertEqual(self.demo.agent.export_state(), agent_before)
        self.assertEqual(self.demo.mock.invoices, provider_before)
        self.assertEqual(self.demo.mock.requests, requests)

    def test_actual_send_then_lost_response_retains_unknown_without_replay(self):
        queued = self.draft()
        original = self.demo.mock.send_invoice
        def sent_then_lost(*args, **kwargs):
            original(*args, **kwargs)
            raise TimeoutError("Authored lost response after the real mock send")
        with patch.object(self.demo.mock, "send_invoice", side_effect=sent_then_lost):
            reply = self.call("approve", action_id=queued["id"])
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], "TimeoutError")
        self.assertEqual(self.demo.mock.invoices[queued["invoice_id"]]["status"], "SENT")
        self.assertEqual(len(reply["state"]["completed_reviews"]), 1)
        row = reply["state"]["completed_reviews"][0]
        self.assertEqual(row["id"], queued["id"])
        self.assertEqual(row["status"], "FAILED")
        self.assertEqual(row["payload"], queued["payload"])
        self.assertEqual(row["result"]["outcome"], "UNKNOWN")
        self.assertEqual(row["result"]["error_type"], "TimeoutError")
        self.assertIn("Check the invoice", row["result"]["reason"])
        requests = copy.deepcopy(self.demo.mock.requests)
        retry = self.call("approve", action_id=queued["id"])
        self.assertFalse(retry["ok"])
        self.assertEqual(self.history(), [row])
        self.assertEqual(self.demo.mock.requests, requests)

    def test_provider_refusal_does_not_acquire_an_invented_unknown_outcome(self):
        queued = self.draft()
        self.demo.mock.invoices[queued["invoice_id"]]["status"] = "CANCELLED"
        reply = self.call("approve", action_id=queued["id"])
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], "PayPalError")
        self.assertEqual(len(reply["state"]["completed_reviews"]), 1)
        row = reply["state"]["completed_reviews"][0]
        self.assertEqual(row["status"], "FAILED")
        self.assertEqual(row["result"]["name"], "UNPROCESSABLE_ENTITY")
        self.assertNotIn("outcome", row["result"])
        self.assertEqual(row["payload"], queued["payload"])
        self.assertEqual(row["result"], self.demo.agent.pending[queued["id"]].result)

    def test_automatic_invalidation_keeps_the_original_reminder_and_reason(self):
        queued = self.reminder()
        before_requests = copy.deepcopy(self.demo.mock.requests)
        reply = self.call("advance", day=(self.demo.clock.day + timedelta(days=1)).isoformat())
        self.assertTrue(reply["ok"], reply)
        row = next(r for r in reply["state"]["completed_reviews"] if r["id"] == queued["id"])
        self.assertEqual(row["status"], "REJECTED")
        self.assertTrue(row["result"]["reason"].startswith("auto:"))
        self.assertNotEqual(row["result"]["reason"], "Rejected by the browser visitor")
        self.assertEqual(row["payload"], queued["payload"])
        self.assertEqual(reply["state"]["pending"], [])
        self.assertEqual(self.demo.mock.requests, before_requests)

    def test_failed_read_only_preflight_remains_pending_until_explicit_success(self):
        queued = self.reminder()
        with patch.object(self.demo.mock, "get_invoice", side_effect=TimeoutError("Authored read-only preflight failure")):
            reply = self.call("approve", action_id=queued["id"])
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["state"]["pending"], [queued])
        self.assertNotIn(queued["id"], [r["id"] for r in reply["state"]["completed_reviews"]])
        sent = self.call("approve", action_id=queued["id"])
        self.assertTrue(sent["ok"], sent)
        completed = next(r for r in sent["state"]["completed_reviews"] if r["id"] == queued["id"])
        self.assertEqual(completed["status"], "APPROVED")
        self.assertEqual(completed["result"], {"reminded": True})
        self.assertEqual(completed["payload"], queued["payload"])
        self.assertEqual(len([r for r in self.demo.mock.requests if r[1].endswith("/remind")]), 1)

    def test_history_retains_actions_beyond_the_short_audit_window(self):
        queued = []
        for _ in range(23):
            action = self.draft()
            queued.append(action)
            self.assertTrue(self.call("reject", action_id=action["id"])["ok"])
        snapshot = self.demo.snapshot()
        self.assertEqual(len(snapshot["audit"]), 18)
        self.assertEqual(len(snapshot["completed_reviews"]), 23)
        self.assertEqual([r["id"] for r in snapshot["completed_reviews"]], [r["id"] for r in reversed(queued)])
        self.assertEqual([r["payload"] for r in snapshot["completed_reviews"]], [r["payload"] for r in reversed(queued)])

    def test_reviewed_literal_text_and_decimal_fields_retain_queued_values(self):
        analyzed = self.call("analyze", text=self.email)
        self.assertTrue(analyzed["ok"], analyzed)
        fields = {"client_name": "Zoë <img src=x onerror=window.injected=1>",
                  "client_email": "fictional@example.test", "due_days": "30", "amount_paid": "0",
                  "line_items": [{"desc": "Révision <script>literal()</script>\nsecond line",
                                  "qty": "1.50", "unit_price": "80.00", "currency": "EUR", "unit": "hr"}]}
        checked = self.call("review", text=self.email, fields=fields, confirmed=True)
        self.assertTrue(checked["ok"], checked)
        self.assertTrue(checked["result"]["valid"], checked)
        draft = self.call("draft", text=self.email, review_id=checked["result"]["review_id"])
        self.assertTrue(draft["ok"], draft)
        action = copy.deepcopy(draft["state"]["pending"][0])
        self.assertTrue(self.call("reject", action_id=action["id"])["ok"])
        row = self.history()[0]
        self.assertEqual(row["payload"], action["payload"])
        item = row["payload"]["invoice"]["items"][0]
        self.assertEqual(item["unit_amount"]["value"], "80.00")
        self.assertEqual(item["unit_amount"]["currency_code"], "EUR")
        self.assertEqual(item["name"], fields["line_items"][0]["desc"])
        self.assertIn("Zoë", json.dumps(row, ensure_ascii=False))

    def test_explicit_reset_discards_completed_reviews_and_old_action_ids(self):
        action = self.draft()
        self.assertTrue(self.call("reject", action_id=action["id"])["ok"])
        self.assertEqual(len(self.history()), 1)
        reset = self.call("reset")
        self.assertTrue(reset["ok"], reset)
        self.assertEqual(reset["state"]["completed_reviews"], [])
        self.assertEqual(reset["state"]["pending"], [])
        self.assertEqual(reset["state"]["ledger"], [])
        self.assertFalse(self.call("approve", action_id=action["id"])["ok"])
        self.assertEqual(self.history(), [])


if __name__ == "__main__":
    unittest.main()
