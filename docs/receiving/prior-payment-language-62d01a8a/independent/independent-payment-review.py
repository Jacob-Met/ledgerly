"""Independent payment-evidence and reviewed-invoice checks with native mocks.

Set LEDGERLY_REVIEW_ROOT to one frozen source directory. Only SandboxMock is
instantiated; the network client and provider credentials are never used.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("LEDGERLY_REVIEW_ROOT", HERE / "baseline")).resolve()
sys.path.insert(0, str(SOURCE))
from ledgerly.agent import Agent, ApprovalRequired, RulePlanner
from ledgerly.extract import RulesExtractor
from ledgerly.paypal import SandboxMock

spec = importlib.util.spec_from_file_location("independent_human_review", SOURCE / "web-demo/python/review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

FUTURE = "We'll have paid a $500 deposit by Friday."
INVOICER = {"name": "Independent Review Fixture", "email_address": "sender@example.test"}


def message(statement):
    return "From: Review Client <client@example.test>\n\nWebsite build — $1,000\nNet 30.\n" + statement


def make_agent(extractor=None):
    mock = SandboxMock(now=lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
    agent = Agent(mock, INVOICER, extractor=extractor, today=lambda: date(2026, 10, 8))
    return agent, mock


def outgoing(mock, suffix):
    return [body for method, path, body in mock.requests if method == "POST" and path.endswith(suffix)]


def correction(amount):
    return review.prepare_review({
        "client_name": "Review Client", "client_email": "client@example.test",
        "due_days": "30", "amount_paid": str(amount),
        "line_items": [{"desc": "Website build", "qty": "1", "unit_price": "1000",
                        "currency": "USD", "unit": ""}],
    })


class PaymentEvidenceReview(unittest.TestCase):
    def require_review(self, statement, expected_paid=Decimal(0)):
        text = message(statement)
        ex = RulesExtractor().extract(text)
        self.assertEqual(ex.total(), Decimal(1000), "Payment language must not become billed work")
        self.assertEqual(ex.amount_paid, expected_paid)
        errors = [i for i in ex.errors if i.field == "amount_paid"]
        self.assertTrue(errors, "Uncertain prior-payment evidence needs a field-level blocking issue")
        self.assertTrue(any("review" in i.message.lower() or "confirm" in i.message.lower() for i in errors))
        agent, mock = make_agent()
        result = agent.tool_create_invoice(text)
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_review"])
        self.assertEqual(mock.requests, [], "Review must happen before even a provider draft/number request")
        self.assertEqual(mock.invoices, {})
        self.assertEqual(agent.ledger, {})
        self.assertEqual(agent.pending, {})
        return ex

    def test_future_perfect_contractions_are_not_completed_payments(self):
        for text in (
            FUTURE,
            "We’ll have paid a $500 deposit by Friday.",
            "I'll have paid a $500 deposit by tomorrow.",
        ):
            with self.subTest(text=text):
                self.require_review(text)

    def test_inverted_counterfactuals_require_review(self):
        for text in (
            "Had we paid a $500 deposit, we'd have a receipt.",
            "Had we already paid a $500 deposit, we'd proceed.",
        ):
            with self.subTest(text=text):
                self.require_review(text)

    def test_inline_quoted_previous_project_is_not_current_payment(self):
        for text in (
            "Earlier you wrote 'we paid a $500 deposit' for another project.",
            "Earlier you wrote ‘we paid a $500 deposit’ for another project.",
            "Example wording: `we paid a $500 deposit`.",
        ):
            with self.subTest(text=text):
                self.require_review(text)

    def test_negated_receipt_contractions_require_review(self):
        for text in (
            "We haven't paid a $500 deposit.",
            "We haven’t paid a $500 deposit.",
            "The $500 deposit hasn't been paid.",
        ):
            with self.subTest(text=text):
                self.require_review(text)

    def test_unsettled_receipt_tail_is_not_discarded(self):
        for text in (
            "We already paid a $500 deposit, subject to successful clearance.",
            "We already paid a $500 deposit but it is awaiting confirmation.",
        ):
            with self.subTest(text=text):
                self.require_review(text)

    def test_supported_receipt_plus_uncertain_line_preserves_blocking_issue(self):
        text = "We already paid a $200 deposit by bank transfer last week.\n" + FUTURE
        self.require_review(text, expected_paid=Decimal(200))

    def test_quoted_email_thread_remains_excluded_without_fake_payment(self):
        text = message("  > We already paid a $500 deposit by bank transfer last week.")
        ex = RulesExtractor().extract(text)
        self.assertEqual(ex.amount_paid, Decimal(0))
        self.assertEqual(ex.errors, [])
        agent, mock = make_agent()
        result = agent.tool_create_invoice(text)
        self.assertTrue(result["ok"])
        row = result["invoices"][0]
        self.assertEqual(row["total"], "1000")
        self.assertEqual(agent.pending[row["approval_id"]].payload["prepaid"], "0")
        self.assertEqual(outgoing(mock, "/send"), [])
        self.assertEqual(outgoing(mock, "/payments"), [])
        agent.approve(row["approval_id"], approver="independent fixture")
        self.assertEqual(outgoing(mock, "/payments"), [])
        self.assertEqual(mock.invoices[row["invoice_id"]]["payments"]["paid_amount"]["value"], "0.00")

    def test_original_supported_receipt_still_requires_explicit_approval(self):
        text = (SOURCE / "fixtures/07_partial_payment_deposit.txt").read_text()
        ex = RulesExtractor().extract(text)
        self.assertEqual(ex.amount_paid, Decimal(1000))
        self.assertEqual(ex.total(), Decimal(3500))
        self.assertEqual(ex.errors, [])
        agent, mock = make_agent()
        result = agent.tool_create_invoice(text)
        self.assertTrue(result["ok"])
        row = result["invoices"][0]
        self.assertEqual(agent.pending[row["approval_id"]].payload["prepaid"], "1000")
        self.assertEqual(outgoing(mock, "/send"), [])
        self.assertEqual(outgoing(mock, "/payments"), [])
        with self.assertRaises(ApprovalRequired):
            agent.client.record_payment(row["invoice_id"], {"amount": {"currency_code": "USD", "value": "1000"}})
        self.assertEqual(outgoing(mock, "/payments"), [])
        agent.approve(row["approval_id"], approver="independent fixture")
        self.assertEqual(len(outgoing(mock, "/send")), 1)
        self.assertEqual([b["amount"]["value"] for b in outgoing(mock, "/payments")], ["1000"])
        self.assertEqual(agent.ledger[row["invoice_id"]].balance, Decimal(2500))
        with self.assertRaises(ValueError):
            agent.approve(row["approval_id"], approver="independent fixture")
        self.assertEqual(len(outgoing(mock, "/payments")), 1)

    def test_human_zero_correction_produces_truthful_invoice_and_no_payment(self):
        text = message(FUTURE)
        adapter = review.ReviewableExtractor()
        agent, mock = make_agent(adapter)
        blocked = agent.run("invoice:" + text, RulePlanner())
        tool_result = next(h["result"] for h in blocked["history"] if h["role"] == "tool")
        self.assertTrue(tool_result.get("needs_review"))
        self.assertEqual(mock.requests, [])
        corrected = correction(0)
        self.assertEqual(corrected.source, "human_review")
        self.assertEqual(corrected.errors, [])
        with adapter.using(text, corrected):
            result = agent.tool_create_invoice(text)
        self.assertTrue(result["ok"])
        row = result["invoices"][0]
        action = agent.pending[row["approval_id"]]
        self.assertEqual(action.payload["prepaid"], "0")
        self.assertNotIn("received", action.summary.lower())
        self.assertNotIn("received", action.payload["invoice"]["detail"].get("note", "").lower())
        self.assertEqual(outgoing(mock, "/send"), [])
        self.assertEqual(outgoing(mock, "/payments"), [])
        request_count = len(mock.requests)
        rejected_again = agent.tool_create_invoice(text)
        self.assertTrue(rejected_again.get("needs_review"), "Correction must not become a persistent bypass")
        self.assertEqual(len(mock.requests), request_count)
        agent.approve(row["approval_id"], approver="independent fixture")
        self.assertEqual(len(outgoing(mock, "/send")), 1)
        self.assertEqual(outgoing(mock, "/payments"), [])
        self.assertEqual(agent.ledger[row["invoice_id"]].balance, Decimal(1000))

    def test_explicit_human_prior_payment_amount_is_used_only_after_approval(self):
        text = message(FUTURE)
        adapter = review.ReviewableExtractor()
        agent, mock = make_agent(adapter)
        corrected = correction(375)
        self.assertEqual(corrected.source, "human_review")
        self.assertEqual(corrected.errors, [])
        with adapter.using(text, corrected):
            result = agent.tool_create_invoice(text)
        self.assertTrue(result["ok"])
        row = result["invoices"][0]
        self.assertEqual(agent.pending[row["approval_id"]].payload["prepaid"], "375")
        self.assertEqual(outgoing(mock, "/payments"), [])
        agent.approve(row["approval_id"], approver="independent fixture")
        self.assertEqual([b["amount"]["value"] for b in outgoing(mock, "/payments")], ["375"])
        self.assertEqual(agent.ledger[row["invoice_id"]].balance, Decimal(625))

    def test_human_correction_is_bound_to_original_source(self):
        text = message(FUTURE)
        adapter = review.ReviewableExtractor()
        agent, mock = make_agent(adapter)
        with adapter.using(text, correction(0)):
            with self.assertRaisesRegex(ValueError, "source changed"):
                agent.tool_create_invoice(text + "\nAdditional work — $100")
        self.assertEqual(mock.requests, [])
        self.assertEqual(mock.invoices, {})
        self.assertEqual(agent.pending, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
