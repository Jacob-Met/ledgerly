"""Actual native extraction/draft/review controls; all provider effects are mocks."""
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerly.agent import Agent
from ledgerly.extract import RulesExtractor
from ledgerly.paypal import SandboxMock


def source(*lines):
    return ("From: Example Client <client@synthetic.example>\n\n"
            "- Website build: $2000\n" + "\n".join(lines) + "\nNet 30\n")


def new_agent():
    provider = SandboxMock()
    agent = Agent(provider, {"name": "Synthetic Freelancer", "email_address": "freelancer@synthetic.example"},
                  today=lambda: date(2026, 10, 8))
    return agent, provider


class PriorPaymentLanguageTests(unittest.TestCase):
    def assert_requires_payment_review(self, line):
        text = source(line)
        extraction = RulesExtractor().extract(text)
        self.assertEqual(extraction.amount_paid, Decimal(0), line)
        self.assertEqual(extraction.total(), Decimal(2000), line)
        self.assertTrue(any(issue.field == "amount_paid" and "review" in issue.message.lower()
                            for issue in extraction.errors), line)
        agent, provider = new_agent()
        outcome = agent.tool_create_invoice(text)
        self.assertFalse(outcome["ok"], line)
        self.assertTrue(outcome["needs_review"], line)
        self.assertEqual(provider.requests, [], line)
        self.assertEqual(agent.list_pending(), [], line)

    def test_negated_deposits_are_not_receipts(self):
        for line in [
            "The $500 deposit has not been paid.",
            "We have not paid the $500 deposit.",
            "The $500 deposit hasn't been paid.",
            "The $500 deposit hasn’t been paid.",
            "The $500 deposit was never received.",
            "It is not true that we already paid the $500 deposit.",
        ]:
            with self.subTest(line=line):
                self.assert_requires_payment_review(line)

    def test_future_requested_and_pending_deposits_need_review(self):
        for line in [
            "A deposit of $500 is due before work begins.",
            "I will pay a $500 deposit next week.",
            "Please pay a $500 deposit before work begins.",
            "The $500 deposit will be paid upfront.",
            "The $500 deposit payment is pending.",
            "A $500 advance payment is to be paid upfront.",
        ]:
            with self.subTest(line=line):
                self.assert_requires_payment_review(line)

    def test_conditional_payment_is_not_a_receipt(self):
        for line in [
            "If the $500 deposit is already paid, start work.",
            "When we have paid the $500 deposit, begin.",
            "Once the $500 deposit has been paid, start work.",
            "We should have paid the $500 deposit by Friday.",
            "Was the $500 deposit already paid?",
        ]:
            with self.subTest(line=line):
                self.assert_requires_payment_review(line)

    def test_unqualified_payment_labels_need_review(self):
        for line in ["Deposit: $500.", "A $500 advance payment.", "The deposit amount is $500."]:
            with self.subTest(line=line):
                self.assert_requires_payment_review(line)

    def test_quoted_unsettled_and_multi_amount_lines_need_review(self):
        for line in [
            'The client wrote "we already paid a $500 deposit".',
            "We already paid a $500 deposit, but it was refunded.",
            "We already paid $100; the remaining $400 deposit is due next week.",
            "We already paid a $500 deposit and a $200 advance payment.",
        ]:
            with self.subTest(line=line):
                self.assert_requires_payment_review(line)

    def test_supported_completed_payment_statements(self):
        for line in [
            "We already paid a $500 deposit by bank transfer last week.",
            "I already paid a $500 deposit by bank transfer.",
            "We have paid $500.",
            "The $500 retainer was paid upfront.",
            "The $500 deposit has been paid.",
            "A $500 advance payment was received.",
            "Prepaid $500.",
            "Deposit paid: $500.",
        ]:
            with self.subTest(line=line):
                extraction = RulesExtractor().extract(source(line))
                self.assertEqual(extraction.amount_paid, Decimal(500))
                self.assertEqual(extraction.total(), Decimal(2000))
                self.assertEqual(extraction.errors, [])

    def test_separate_confirmed_payments_accumulate(self):
        extraction = RulesExtractor().extract(source(
            "We already paid a $300 deposit.", "We have paid a $200 advance payment."))
        self.assertEqual(extraction.amount_paid, Decimal(500))
        self.assertEqual(extraction.errors, [])

    def test_quoted_history_cannot_supply_a_receipt(self):
        extraction = RulesExtractor().extract(source(
            "> We already paid a $500 deposit.", "  > I have paid $700 upfront."))
        self.assertEqual(extraction.amount_paid, Decimal(0))
        self.assertEqual(extraction.errors, [])

    def test_supported_deposit_still_requires_separate_send_approval(self):
        text = (ROOT / "fixtures/07_partial_payment_deposit.txt").read_text(encoding="utf-8")
        agent, provider = new_agent()
        outcome = agent.tool_create_invoice(text)
        self.assertTrue(outcome["ok"])
        self.assertEqual(len(agent.list_pending()), 1)
        self.assertFalse(any(path.endswith(("/send", "/payments")) for _, path, _ in provider.requests))
        invoice = outcome["invoices"][0]
        approved = agent.approve(invoice["approval_id"])
        self.assertIn("deposit_payment_id", approved)
        payments = [body for _, path, body in provider.requests if path.endswith("/payments")]
        self.assertEqual(len(payments), 1)
        self.assertEqual(Decimal(payments[0]["amount"]["value"]), Decimal(1000))
        entry = agent.ledger[invoice["invoice_id"]]
        self.assertEqual(entry.total, Decimal(3500))
        self.assertEqual(entry.balance, Decimal(2500))

    def test_one_uncertain_line_blocks_draft_even_after_a_confirmed_receipt(self):
        text = source("We already paid a $300 deposit.", "A further $200 deposit is due.")
        extraction = RulesExtractor().extract(text)
        self.assertEqual(extraction.amount_paid, Decimal(300))
        self.assertTrue(any(issue.field == "amount_paid" for issue in extraction.errors))
        agent, provider = new_agent()
        self.assertTrue(agent.tool_create_invoice(text)["needs_review"])
        self.assertEqual(provider.requests, [])

    def test_current_review_adapter_can_resolve_unknown_payment_without_recording_one(self):
        # Exercise the unchanged browser bridge natively, without a browser or Pyodide.
        sys.path.insert(0, str(ROOT / "web-demo/python"))
        spec = importlib.util.spec_from_file_location("prior_payment_bridge", ROOT / "web-demo/python/bridge.py")
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        demo = bridge.Demo()
        text = source("A $500 deposit is due before work begins.")
        analysis = demo.dispatch({"action": "analyze", "text": text})["result"]
        self.assertEqual(analysis["amount_paid"], "0")
        self.assertTrue(any(issue["field"] == "amount_paid" and issue["severity"] == "error"
                            for issue in analysis["issues"]))
        refused = demo.dispatch({"action": "draft", "text": text})
        self.assertEqual(refused["state"]["ledger"], [])
        self.assertEqual(demo.mock.requests, [])
        fields = {key: analysis[key] for key in ("client_name", "client_email", "line_items")}
        fields.update({"due_days": str(analysis["due_days"]), "amount_paid": "0"})
        for row in fields["line_items"]:
            row["unit"] = row["unit"] or ""
        checked = demo.dispatch({"action": "review", "text": text, "confirmed": True, "fields": fields})["result"]
        self.assertTrue(checked["valid"])
        drafted = demo.dispatch({"action": "draft", "text": text, "review_id": checked["review_id"]})
        action = drafted["state"]["pending"][0]
        demo.dispatch({"action": "approve", "action_id": action["id"]})
        self.assertFalse(any(path.endswith("/payments") for _, path, _ in demo.mock.requests))
        self.assertEqual(len(demo.agent.ledger), 1)
        self.assertEqual(next(iter(demo.agent.ledger.values())).balance, Decimal(2000))


if __name__ == "__main__":
    unittest.main()
