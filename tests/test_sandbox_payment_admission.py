"""Actual sandbox/bridge payment admission, with network entry points blocked."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from decimal import Decimal, DecimalException, localcontext
from pathlib import Path
from unittest.mock import patch

import ledgerly
from ledgerly.agent import ApprovalRequired
from ledgerly.paypal import HttpPayPalClient

ROOT = Path(ledgerly.__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web-demo/python"))
SPEC = importlib.util.spec_from_file_location(
    "sandbox_payment_admission_bridge", ROOT / "web-demo/python/bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class SandboxPaymentAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        for target in ("urllib.request.urlopen", "socket.create_connection"):
            self.guards.enter_context(patch(target, side_effect=AssertionError("network forbidden")))
        self.guards.enter_context(patch.object(
            HttpPayPalClient, "__init__", side_effect=AssertionError("HTTP client forbidden")))

    def approved_demo(self, fixture="02_gbp_proofreading.txt", *, text=None):
        demo = bridge.Demo()
        demo.clock.day = date(2026, 10, 8)
        drafted = demo.dispatch({
            "action": "draft", "text": (ROOT / "fixtures" / fixture).read_text(encoding="utf-8") if text is None else text})
        self.assertTrue(drafted["result"]["unauthorized_send_blocked"])
        action = drafted["state"]["pending"][0]
        demo.dispatch({"action": "approve", "action_id": action["id"]})
        return demo, action["invoice_id"]

    @staticmethod
    def retained(demo, invoice_id):
        return (copy.deepcopy(demo.mock.invoices[invoice_id]),
                demo.agent.export_state(), copy.deepcopy(demo.last_event))

    @staticmethod
    def request(demo, **request):
        with patch.object(bridge, "SESSION", demo):
            return json.loads(bridge.handle_json(json.dumps(request)))

    def test_invalid_native_amounts_leave_invoice_unchanged_and_allow_same_instance_retry(self):
        for amount in ("-50", "-0", "0", "0.015", "NaN", "sNaN", "Infinity", "-Infinity",
                       "1e999999", "1e-999999"):
            with self.subTest(amount=amount):
                demo, invoice_id = self.approved_demo()
                invoice = demo.mock.invoices[invoice_id]
                before = self.retained(demo, invoice_id)
                requests = copy.deepcopy(demo.mock.requests)
                with self.assertRaises(ValueError):
                    demo.mock.simulate_payer_payment(invoice_id, Decimal(amount))
                self.assertEqual(self.retained(demo, invoice_id), before)
                self.assertEqual(demo.mock.requests, requests)
                self.assertIs(demo.mock.invoices[invoice_id], invoice)
                accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="20.00")
                self.assertTrue(accepted["ok"], accepted)
                self.assertEqual(len(invoice["payments"]["transactions"]), 1)
                self.assertEqual(invoice["payments"]["paid_amount"]["value"], "20.00")
                self.assertEqual(Decimal(accepted["state"]["ledger"][0]["paid_amount"]), Decimal("20.00"))

    def test_supplied_zero_and_malformed_json_do_not_become_full_payments(self):
        for amount in (0, 0.0, False, [], {}, "0", "-50", "NaN", "0.015"):
            with self.subTest(amount=amount):
                demo, invoice_id = self.approved_demo()
                before = self.retained(demo, invoice_id)
                count = len(demo.mock.requests)
                refused = self.request(demo, action="payment", invoice_id=invoice_id, amount=amount)
                self.assertFalse(refused["ok"], refused)
                self.assertEqual(self.retained(demo, invoice_id), before)
                self.assertEqual(len(demo.mock.requests), count)
                accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="25")
                self.assertTrue(accepted["ok"], accepted)
                self.assertEqual(Decimal(accepted["state"]["ledger"][0]["paid_amount"]), Decimal("25.00"))
                self.assertEqual(len(demo.mock.invoices[invoice_id]["payments"]["transactions"]), 1)

    def test_blank_null_and_absent_amount_keep_explicit_full_balance_behavior(self):
        for supplied in ({"amount": ""}, {"amount": None}, {}):
            with self.subTest(supplied=supplied):
                demo, invoice_id = self.approved_demo()
                accepted = self.request(demo, action="payment", invoice_id=invoice_id, **supplied)
                self.assertTrue(accepted["ok"], accepted)
                self.assertEqual(accepted["state"]["ledger"][0]["status"], "PAID")
                self.assertEqual(Decimal(accepted["state"]["ledger"][0]["paid_amount"]), Decimal("800.00"))
                replay = demo.dispatch({"action": "replay"})
                self.assertTrue(replay["result"]["duplicate"])
                self.assertEqual(len(demo.mock.invoices[invoice_id]["payments"]["transactions"]), 1)

    def test_currency_exact_partial_and_full_payments_preserve_existing_values(self):
        for fixture, partial, expected in (
            ("02_gbp_proofreading.txt", "12.3400", "12.34"),
            ("08_jpy_zero_decimal.txt", "100.0", "100"),
        ):
            with self.subTest(fixture=fixture):
                demo, invoice_id = self.approved_demo(fixture)
                original = copy.deepcopy(demo.mock.invoices[invoice_id])
                partial_result = self.request(demo, action="payment", invoice_id=invoice_id, amount=partial)
                self.assertTrue(partial_result["ok"], partial_result)
                invoice = demo.mock.invoices[invoice_id]
                self.assertEqual(invoice["payments"]["paid_amount"]["value"], expected)
                self.assertEqual(invoice["status"], "PARTIALLY_PAID")
                self.assertEqual(invoice["detail"], original["detail"])
                self.assertEqual(invoice["items"], original["items"])
                full = self.request(demo, action="payment", invoice_id=invoice_id)
                self.assertTrue(full["ok"], full)
                self.assertEqual(invoice["status"], "PAID")
                self.assertEqual(Decimal(invoice["due_amount"]["value"]), Decimal(0))
                self.assertEqual(len(invoice["payments"]["transactions"]), 2)

    def test_subunit_line_total_reaches_review_before_draft_allocation(self):
        text = (ROOT / "fixtures/02_gbp_proofreading.txt").read_text(encoding="utf-8")
        text = text.replace("18 hours @ £40/hr", "1.5 hours @ £0.01/hr")
        text = text.replace("Style sheet preparation: 2 hrs @ £40/hr\n", "")
        demo = bridge.Demo()
        refused = demo.agent.tool_create_invoice(text)
        self.assertFalse(refused["ok"], refused)
        self.assertTrue(refused["needs_review"], refused)
        self.assertTrue(any(issue["field"] == "line_items[0].amount"
                            for issue in refused["issues"]), refused)
        self.assertEqual(demo.mock.requests, [])
        self.assertEqual(demo.mock.invoices, {})
        self.assertEqual(demo.mock._seq, 0)
        self.assertEqual(demo.agent.ledger, {})
        self.assertEqual(demo.agent.pending, {})

    def test_rounded_invoice_total_remains_payable_after_repeated_input_refusals(self):
        # Receive an existing provider record with historical line-total rounding.
        # New Ledgerly drafts now require exact line amounts; that separate gate
        # must not weaken this payment regression's fractional-total fixture.
        demo, invoice_id = self.approved_demo()
        invoice = demo.mock.invoices[invoice_id]
        invoice["items"] = invoice["items"][:1]
        invoice["items"][0]["quantity"] = "1.5"
        invoice["items"][0]["unit_amount"]["value"] = "0.01"
        demo.mock._recalc(invoice)
        demo.agent._refresh_invoice(invoice_id)
        self.assertEqual(invoice["items"][0]["quantity"], "1.5")
        self.assertEqual(invoice["items"][0]["unit_amount"]["value"], "0.01")
        self.assertEqual(invoice["amount"]["value"], "0.02")
        before = self.retained(demo, invoice_id)
        for amount in ("NaN", "-1", "0", "0.015"):
            with self.subTest(amount=amount):
                refused = self.request(demo, action="payment", invoice_id=invoice_id, amount=amount)
                self.assertFalse(refused["ok"], refused)
                self.assertEqual(self.retained(demo, invoice_id), before)
        partial = self.request(demo, action="payment", invoice_id=invoice_id, amount="0.01")
        self.assertTrue(partial["ok"], partial)
        self.assertEqual(invoice["payments"]["paid_amount"]["value"], "0.01")
        self.assertEqual(invoice["due_amount"]["value"], "0.01")
        completed = self.request(demo, action="payment", invoice_id=invoice_id)
        self.assertTrue(completed["ok"], completed)
        self.assertEqual(invoice["status"], "PAID")
        self.assertEqual(invoice["payments"]["paid_amount"]["value"], "0.02")
        self.assertEqual(len(invoice["payments"]["transactions"]), 2)

    def test_zero_decimal_currency_refuses_fraction_without_changing_the_invoice(self):
        demo, invoice_id = self.approved_demo("08_jpy_zero_decimal.txt")
        before = self.retained(demo, invoice_id)
        refused = self.request(demo, action="payment", invoice_id=invoice_id, amount="0.5")
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(self.retained(demo, invoice_id), before)
        accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="1")
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(accepted["state"]["ledger"][0]["paid_amount"], "1")

    def test_external_payment_uses_the_same_refusal_before_record_mutation(self):
        for amount in ("-1", "0", "0.015", "NaN", "Infinity"):
            with self.subTest(amount=amount):
                demo, invoice_id = self.approved_demo()
                before = self.retained(demo, invoice_id)
                with self.assertRaises(ValueError):
                    demo.mock.record_payment(invoice_id, {
                        "amount": {"currency_code": "GBP", "value": amount}, "method": "BANK_TRANSFER"})
                self.assertEqual(self.retained(demo, invoice_id), before)
                accepted = demo.mock.record_payment(invoice_id, {
                    "amount": {"currency_code": "GBP", "value": "20.00"}, "method": "BANK_TRANSFER"})
                self.assertEqual(accepted.status, 200)
                invoice = demo.mock.invoices[invoice_id]
                self.assertEqual(len(invoice["payments"]["transactions"]), 1)
                self.assertEqual(invoice["payments"]["paid_amount"]["value"], "20.00")
                self.assertEqual(invoice["payments"]["transactions"][0]["type"], "EXTERNAL")

    def test_recalculation_exception_preserves_record_and_valid_retry(self):
        demo, invoice_id = self.approved_demo()
        before = self.retained(demo, invoice_id)
        original = demo.mock._recalc

        def recalculate_then_fail(invoice):
            original(invoice)
            raise RuntimeError("authored failure after recalculation")

        with patch.object(demo.mock, "_recalc", side_effect=recalculate_then_fail):
            with self.assertRaisesRegex(RuntimeError, "authored failure"):
                demo.mock.simulate_payer_payment(invoice_id, Decimal("20.00"))
        self.assertEqual(self.retained(demo, invoice_id), before)
        accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="20.00")
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(len(demo.mock.invoices[invoice_id]["payments"]["transactions"]), 1)

    def test_decimal_recalculation_failure_preserves_record_for_normal_context_retry(self):
        demo, invoice_id = self.approved_demo()
        before = self.retained(demo, invoice_id)
        with localcontext() as context:
            context.prec = 4
            with self.assertRaises((ValueError, DecimalException)):
                demo.mock.simulate_payer_payment(invoice_id, Decimal("1.00"))
        self.assertEqual(self.retained(demo, invoice_id), before)
        accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="1.00")
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(len(demo.mock.invoices[invoice_id]["payments"]["transactions"]), 1)

    def test_refusal_keeps_existing_webhook_and_pending_reminder_review(self):
        demo, invoice_id = self.approved_demo()
        first = self.request(demo, action="payment", invoice_id=invoice_id, amount="50.00")
        self.assertTrue(first["ok"], first)
        demo.dispatch({"action": "advance", "day": (demo.clock.day + timedelta(days=45)).isoformat()})
        scan = demo.dispatch({"action": "chase"})
        self.assertEqual(len(scan["state"]["pending"]), 1)
        before = self.retained(demo, invoice_id)
        count = len(demo.mock.requests)
        refused = self.request(demo, action="payment", invoice_id=invoice_id, amount="NaN")
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(self.retained(demo, invoice_id), before)
        self.assertEqual(len(demo.mock.requests), count)
        replay = demo.dispatch({"action": "replay"})
        self.assertTrue(replay["result"]["duplicate"])
        accepted = self.request(demo, action="payment", invoice_id=invoice_id, amount="20.00")
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(accepted["state"]["pending"], [])
        self.assertEqual(Decimal(accepted["state"]["ledger"][0]["paid_amount"]), Decimal("70.00"))

    def test_approved_prior_deposit_still_uses_the_existing_gate(self):
        demo = bridge.Demo()
        draft = demo.dispatch({"action": "draft", "text": (
            ROOT / "fixtures/07_partial_payment_deposit.txt").read_text(encoding="utf-8")})
        action = draft["state"]["pending"][0]
        invoice_id = action["invoice_id"]
        self.assertEqual(demo.mock.invoices[invoice_id]["payments"]["transactions"], [])
        requests = copy.deepcopy(demo.mock.requests)
        with self.assertRaises(ApprovalRequired):
            demo.agent.client.record_payment(invoice_id, {
                "amount": {"currency_code": "USD", "value": "1000.00"}})
        self.assertEqual(demo.mock.requests, requests)
        accepted = demo.dispatch({"action": "approve", "action_id": action["id"]})
        self.assertTrue(accepted["result"]["approved"])
        invoice = demo.mock.invoices[invoice_id]
        self.assertEqual(invoice["status"], "PARTIALLY_PAID")
        self.assertEqual(invoice["payments"]["paid_amount"]["value"], "1000.00")
        self.assertEqual(invoice["due_amount"]["value"], "2500.00")
        self.assertEqual(len(invoice["payments"]["transactions"]), 1)
        self.assertEqual(invoice["payments"]["transactions"][0]["type"], "EXTERNAL")

    def test_postcommit_webhook_read_failure_keeps_existing_replay_semantics(self):
        demo, invoice_id = self.approved_demo()
        with patch.object(demo.mock, "get_invoice", side_effect=TimeoutError("authored current read failure")):
            failed = self.request(demo, action="payment", invoice_id=invoice_id, amount="50.00")
        self.assertFalse(failed["ok"], failed)
        invoice = demo.mock.invoices[invoice_id]
        self.assertEqual(invoice["payments"]["paid_amount"]["value"], "50.00")
        self.assertEqual(len(invoice["payments"]["transactions"]), 1)
        self.assertIsNotNone(demo.last_event)
        replay = demo.dispatch({"action": "replay"})
        self.assertTrue(replay["result"]["ok"])
        self.assertEqual(Decimal(replay["state"]["ledger"][0]["paid_amount"]), Decimal("50.00"))
        self.assertEqual(len(invoice["payments"]["transactions"]), 1)
        self.assertEqual(replay["state"]["external_calls"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
