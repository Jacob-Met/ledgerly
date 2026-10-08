"""Consumer controls through the real browser Demo, Agent and SandboxMock."""
from copy import deepcopy
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web-demo" / "python"))
SPEC = importlib.util.spec_from_file_location("invoice_details_test_bridge", ROOT / "web-demo" / "python" / "bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class InvoiceDetailsTests(unittest.TestCase):
    def setUp(self):
        self.demo = bridge.Demo()
        self.demo.clock.day = date(2026, 10, 8)

    def draft(self, fixture="01_simple_usd_hourly.txt"):
        text = (ROOT / "fixtures" / fixture).read_text()
        result = self.demo.dispatch({"action": "draft", "text": text})
        self.assertTrue(result["result"]["unauthorized_send_blocked"])
        return result["state"]

    def record(self, snapshot, invoice_id=None):
        invoice_id = invoice_id or snapshot["ledger"][0]["invoice_id"]
        return next(row["record"] for row in snapshot["invoice_details"] if row["invoice_id"] == invoice_id)

    def approve(self, snapshot):
        for pending in snapshot["pending"]:
            self.demo.dispatch({"action": "approve", "action_id": pending["id"]})
        return self.demo.snapshot()

    def test_original_items_and_recipient_remain_after_explicit_approval(self):
        before = self.draft()
        self.assertEqual(before["mock_requests"], 3)
        original = self.record(before)
        after = self.approve(before)
        self.assertEqual(after["pending"], [])
        self.assertEqual(after["mock_requests"], before["mock_requests"] + 2)
        invoice_id = before["ledger"][0]["invoice_id"]
        self.assertEqual([request[:2] for request in self.demo.mock.requests[-2:]], [
            ("GET", f"/v2/invoicing/invoices/{invoice_id}"),
            ("POST", f"/v2/invoicing/invoices/{invoice_id}/send"),
        ])
        self.assertEqual(self.record(after)["status"], "SENT")
        for key in ("items", "primary_recipients", "invoicer"):
            self.assertEqual(self.record(after)[key], original[key])
        self.assertEqual(len(original["items"]), 2)
        self.assertEqual(after["external_calls"], 0)

    def test_detached_nested_records_do_not_expose_other_invoices_or_mutate_state(self):
        snapshot = self.draft()
        self.demo.mock.invoices["not-in-agent-ledger"] = {"id": "not-in-agent-ledger", "items": [{"name": "Other invoice"}]}
        before = deepcopy((self.demo.mock.invoices, self.demo.mock.requests, self.demo.agent.list_pending(), self.demo.agent.audit))
        snapshot = self.demo.snapshot()
        record = self.record(snapshot)
        self.assertNotIn("_has_recipient_email", record)
        self.assertNotIn("configuration", record)
        record["items"][0]["name"] = "Changed browser copy"
        record["detail"]["payment_term"]["due_date"] = "1900-01-01"
        record["payments"]["transactions"].append({"amount": "fake"})
        snapshot["invoice_details"].clear()
        self.assertEqual(before, (self.demo.mock.invoices, self.demo.mock.requests, self.demo.agent.list_pending(), self.demo.agent.audit))
        self.assertEqual(len(self.demo.snapshot()["invoice_details"]), 1)

    def test_new_analysis_and_rejected_action_preserve_the_original_record(self):
        initial = self.draft()
        original = deepcopy(self.record(initial))
        other = (ROOT / "fixtures" / "02_gbp_proofreading.txt").read_text()
        self.demo.dispatch({"action": "analyze", "text": other})
        rejected = self.demo.dispatch({"action": "reject", "action_id": initial["pending"][0]["id"]})["state"]
        self.assertEqual(rejected["pending"], [])
        self.assertEqual(self.record(rejected), original)
        self.assertEqual(rejected["mock_requests"], initial["mock_requests"])

    def test_payments_and_reminders_update_details_without_an_inspection_request(self):
        sent = self.approve(self.draft())
        invoice_id = sent["ledger"][0]["invoice_id"]
        paid = self.demo.dispatch({"action": "payment", "invoice_id": invoice_id, "amount": "100.25"})["state"]
        record = self.record(paid)
        self.assertEqual(record["status"], "PARTIALLY_PAID")
        self.assertEqual(record["payments"]["transactions"][0]["amount"]["value"], "100.25")
        self.assertEqual(record["payments"]["paid_amount"]["value"], "100.25")
        self.assertEqual(record["due_amount"]["value"], "1219.75")
        self.demo.dispatch({"action": "replay"})
        self.assertEqual(self.record(self.demo.snapshot()), record)
        due = date.fromisoformat(paid["ledger"][0]["due_on"]) + timedelta(days=1)
        self.demo.dispatch({"action": "advance", "day": due.isoformat()})
        queued = self.demo.dispatch({"action": "chase"})["state"]
        self.assertTrue(any(p["kind"] == "send_reminder" for p in queued["pending"]))
        before = deepcopy(self.demo.mock.requests)
        self.assertEqual(self.record(self.demo.snapshot()), self.record(queued))
        self.assertEqual(self.demo.mock.requests, before)

    def test_multi_currency_identity_and_zero_decimal_values_stay_separate(self):
        mixed = self.draft("04_multi_currency.txt")
        self.assertGreater(len(mixed["ledger"]), 1)
        for row in mixed["ledger"]:
            record = self.record(mixed, row["invoice_id"])
            self.assertEqual(record["id"], row["invoice_id"])
            self.assertEqual(record["detail"]["currency_code"], row["currency"])
            self.assertTrue(all(i["unit_amount"]["currency_code"] == row["currency"] for i in record["items"]))
        self.demo.dispatch({"action": "reset"})
        yen = self.draft("08_jpy_zero_decimal.txt")
        record = self.record(yen)
        self.assertEqual(record["amount"]["currency_code"], "JPY")
        self.assertNotIn(".", record["amount"]["value"])

    def test_missing_or_mismatched_retained_identity_is_not_substituted(self):
        snapshot = self.draft()
        invoice_id = snapshot["ledger"][0]["invoice_id"]
        before = deepcopy(self.demo.mock.requests)
        self.demo.mock.invoices[invoice_id]["id"] = "another-invoice"
        self.assertIsNone(self.record(self.demo.snapshot(), invoice_id))
        del self.demo.mock.invoices[invoice_id]
        self.assertIsNone(self.record(self.demo.snapshot(), invoice_id))
        self.assertEqual(self.demo.mock.requests, before)
        self.assertEqual(len(self.demo.snapshot()["ledger"]), 1)

    def test_provider_changes_and_original_decimal_text_are_copied_without_recalculation(self):
        snapshot = self.draft()
        invoice_id = snapshot["ledger"][0]["invoice_id"]
        record = self.demo.mock.invoices[invoice_id]
        record["status"] = "SYNTHETIC_PROVIDER_STATE"
        record["amount"]["value"] = "9007199254740993.000"
        record["items"][0]["quantity"] = "2.5000"
        record["detail"]["note"] = '<script>literal</script> & 日本語 😀\nsecond line\u2028third'
        del record["due_amount"]
        before = deepcopy(record)
        state = self.demo.snapshot()
        projected = self.record(state)
        self.assertEqual(state["ledger"][0]["status"], "DRAFT")
        self.assertEqual(projected["status"], "SYNTHETIC_PROVIDER_STATE")
        self.assertEqual(projected["amount"]["value"], "9007199254740993.000")
        self.assertEqual(projected["items"][0]["quantity"], "2.5000")
        self.assertNotIn("due_amount", projected)
        self.assertEqual(projected["detail"]["note"], record["detail"]["note"])
        self.assertEqual(json.loads(json.dumps(state, ensure_ascii=False))["invoice_details"], state["invoice_details"])
        self.assertEqual(record, before)

    def test_reset_removes_details_together_with_the_ledger(self):
        self.assertTrue(self.draft()["invoice_details"])
        state = self.demo.dispatch({"action": "reset"})["state"]
        self.assertEqual(state["invoice_details"], [])
        self.assertEqual(state["ledger"], [])
        self.assertEqual(state["mock_requests"], 0)


if __name__ == "__main__":
    unittest.main()
