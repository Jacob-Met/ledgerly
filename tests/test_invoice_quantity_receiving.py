"""Independent PR19 quantity boundary controls; stdlib only, SandboxMock only.

Run: python tests/test_invoice_quantity_receiving.py --source-root /absolute/native/source
Pytest discovers the same controls against this project by default.
The same cases run against the untouched author head and receiving candidate.
"""
import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
import unittest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    source_root = args.source_root.resolve()
else:
    source_root = Path(__file__).resolve().parents[1]
    remaining = []
sys.path.insert(0, str(source_root))

from ledgerly.agent import Agent, RulePlanner  # noqa: E402
from ledgerly.extract import RulesExtractor, parse_qty  # noqa: E402
from ledgerly.paypal import SandboxMock  # noqa: E402


OVERSIZED = "10000000000000000000000000000"
OVERSIZED_UPPER = "10000000000000000000000000001"
INVOICER = {"name": "Quantity Receiver", "email_address": "receiver@ledgerly.example"}


def job(form, *quantities):
    header = "From: Client Example <client@fictional.example>\nSubject: Editing invoice\n\nPrices are in USD.\nNet 15.\n"
    if form == "bullet":
        return header + "\n".join(f"- {qty} x Editing @ $4.00 each" for qty in quantities)
    return header + "| Item | Qty | Rate |\n| --- | --- | --- |\n" + "\n".join(
        f"| Editing | {qty} | $4.00 |" for qty in quantities
    )


def new_agent():
    mock = SandboxMock()
    return Agent(mock, INVOICER, today=lambda: date(2026, 10, 8)), mock


class QuantityReceiving(unittest.TestCase):
    def assert_review(self, form, qty, *, unknowable=False, preceding_valid=False):
        text = job(form, *(('2', qty) if preceding_valid else (qty,)))
        ex = RulesExtractor().extract(text)
        self.assertEqual(len(ex.line_items), 2 if preceding_valid else 1)
        item_index = len(ex.line_items) - 1
        self.assertTrue(any(issue.field == f"line_items[{item_index}].qty" for issue in ex.errors))
        if unknowable:
            self.assertIsNone(ex.line_items[item_index].qty)
            self.assertTrue(any("supported invoice arithmetic range" in issue.message for issue in ex.errors))
        # Real rendering/serialization also consumes unknown quantities safely.
        self.assertIsInstance(ex.to_dict(), dict)
        agent, mock = new_agent()
        result = agent.tool_create_invoice(text)
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_review"])
        self.assertEqual(mock.requests, [])
        self.assertEqual(mock.invoices, {})
        self.assertEqual(agent.ledger, {})
        self.assertEqual(agent.list_pending(), [])
        # The planner path must expose review, rather than only swallowing ValueError.
        loop_agent, loop_mock = new_agent()
        out = loop_agent.run("invoice:" + text, RulePlanner())
        calls = [entry for entry in out["history"] if entry["role"] == "tool"]
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["result"]["needs_review"])
        self.assertIn("needs human review", out["final"])
        self.assertEqual(loop_mock.requests, [])
        self.assertEqual(out["pending"], [])

    def assert_valid(self, form, qty, expected, *, warning=False):
        text = job(form, qty)
        ex = RulesExtractor().extract(text)
        self.assertEqual(ex.errors, [])
        self.assertEqual(len(ex.line_items), 1)
        self.assertEqual(ex.line_items[0].qty, Decimal(expected))
        self.assertEqual(ex.total(), Decimal(expected) * 4)
        self.assertEqual(any(issue.field == "line_items[0].qty" and issue.severity == "warning"
                            for issue in ex.issues), warning)
        agent, mock = new_agent()
        result = agent.tool_create_invoice(text)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(mock.invoices), 1)
        invoice = next(iter(mock.invoices.values()))
        self.assertEqual(invoice["items"][0]["quantity"], expected)
        self.assertEqual(invoice["items"][0]["unit_amount"], {"currency_code": "USD", "value": "4.00"})
        self.assertEqual(Decimal(invoice["amount"]["value"]), Decimal(expected) * 4)
        self.assertEqual(invoice["status"], "DRAFT")
        self.assertEqual(len(agent.list_pending()), 1)
        self.assertEqual([(r[0], r[1]) for r in mock.requests], [
            ("POST", "/v2/invoicing/generate-next-invoice-number"),
            ("POST", "/v2/invoicing/invoices"),
        ])

    def test_valid_maximum(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_valid(form, "1000000", "1000000")

    def test_valid_fraction(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_valid(form, "1.25", "1.25")

    def test_valid_grouped_fraction(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_valid(form, "1,234.50", "1234.5")

    def test_valid_existing_approximate_and_range_warnings(self):
        for form in ("bullet", "table"):
            for qty, expected in (("about 2.5", "2.5"), ("2-3", "2")):
                with self.subTest(form=form, qty=qty):
                    self.assert_valid(form, qty, expected, warning=True)

    def test_existing_next_integer_review(self):
        self.assertEqual(parse_qty("1000001"), (Decimal("1000001"), None))
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, "1000001")

    def test_oversized_plain_requires_review(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, OVERSIZED, unknowable=True)

    def test_oversized_approximate_requires_review(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, "about " + OVERSIZED, unknowable=True)

    def test_oversized_range_lower_requires_review(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, OVERSIZED + " to " + OVERSIZED_UPPER, unknowable=True)

    def test_oversized_approximate_range_lower_requires_review(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, "~ " + OVERSIZED + "-" + OVERSIZED_UPPER, unknowable=True)

    def test_valid_first_item_does_not_allocate_before_oversized_second(self):
        for form in ("bullet", "table"):
            with self.subTest(form=form):
                self.assert_review(form, OVERSIZED, unknowable=True, preceding_valid=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
