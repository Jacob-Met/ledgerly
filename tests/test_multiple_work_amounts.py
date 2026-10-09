"""Require correction before drafting a work line containing several money amounts."""
from datetime import date
from decimal import Decimal
import unittest

from ledgerly.agent import Agent, RulePlanner
from ledgerly.extract import RulesExtractor
from ledgerly.paypal import SandboxMock

HEADER = "From: Mira Example <mira@client.example>\nSubject: Design job\n\nNet 15\n"
INVOICER = {"name": "Freelancer Example", "email_address": "me@freelancer.example"}


def run_job(body):
    source = HEADER + body + "\n"
    mock = SandboxMock()
    agent = Agent(mock, INVOICER, today=lambda: date(2026, 10, 8))
    result = agent.run("invoice:" + source, RulePlanner())
    calls = [row for row in result["history"] if row["role"] == "tool"]
    return source, mock, agent, result, calls


class MultipleWorkAmounts(unittest.TestCase):
    def test_ordinary_multi_amount_lines_require_correction_before_any_draft(self):
        lines = [
            "Design — $100 + $25 printing",
            "Design — $100 or $150 with source files",
            "Design — $100 + EUR 25 printing",
            "2 x Design @ $100 each (total $200)",
            "2 x Design @ $100 each (total $190)",
            "Design — $100 less $20 discount",
            "- Budget planning — $100 + $25 printing",
        ]
        for line in lines:
            with self.subTest(line=line):
                source, mock, agent, result, calls = run_job(
                    "Consultation — $40\n" + line + "\nDelivery — $10")
                ex = RulesExtractor().extract(source)
                blocking = [issue for issue in ex.errors if issue.field == "line_items"]
                self.assertTrue(blocking, ex.to_dict())
                self.assertTrue(any(line in issue.message for issue in blocking))
                self.assertEqual([item.desc for item in ex.line_items], ["Consultation", "Delivery"])
                self.assertEqual(len(calls), 1)
                self.assertFalse(calls[0]["result"]["ok"])
                self.assertTrue(calls[0]["result"]["needs_review"])
                self.assertIn("needs human review", result["final"])
                self.assertEqual(mock.requests, [])
                self.assertEqual(mock.invoices, {})
                self.assertEqual(agent.ledger, {})
                self.assertEqual(result["pending"], [])

    def test_single_price_and_separate_work_lines_keep_their_original_values(self):
        cases = [
            ("Design — $100", [("USD", "100")]),
            ("2 x Design @ $100 each", [("USD", "200")]),
            ("2 hours of Editing at £40/hr", [("GBP", "80")]),
            ("Design — $100\nPrinting — $25", [("USD", "125")]),
            ("Design — $100\nTotal: $100", [("USD", "100")]),
            ("Budget planning — $100", [("USD", "100")]),
            ("Prices are in CAD.\nDesign — $100", [("CAD", "100")]),
            ("Design — $100\nPrinting — EUR 25", [("EUR", "25"), ("USD", "100")]),
            ("| Item | Qty | Rate |\n| --- | --- | --- |\n| Design | 2 | $100 |",
             [("USD", "200")]),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                source, mock, agent, result, calls = run_job(body)
                self.assertEqual(RulesExtractor().extract(source).errors, [])
                created = calls[0]["result"]
                self.assertTrue(created["ok"], created)
                self.assertEqual([(row["currency"], row["total"]) for row in created["invoices"]], expected)
                self.assertEqual(len(result["pending"]), len(expected))
                self.assertTrue(all(row["status"] == "DRAFT" for row in mock.invoices.values()))
                self.assertFalse([req for req in mock.requests if req[1].endswith(("/send", "/remind", "/payments"))])

    def test_existing_summary_classification_and_payment_admission_are_unchanged(self):
        source, mock, agent, result, calls = run_job(
            "Design — $100\nTotal: $100\nWe already paid a $25 deposit.")
        ex = RulesExtractor().extract(source)
        self.assertEqual(ex.errors, [])
        self.assertEqual(ex.amount_paid, Decimal("25"))
        self.assertEqual([item.desc for item in ex.line_items], ["Design"])
        self.assertTrue(calls[0]["result"]["ok"])
        self.assertEqual(result["pending"][0]["payload"]["prepaid"], "25")
        self.assertFalse([req for req in mock.requests if req[1].endswith(("/send", "/remind", "/payments"))])
        source, mock, agent, result, calls = run_job(
            "Design — $100\nWe already paid $25; the remaining $75 is due next week.")
        self.assertTrue(any(issue.field == "amount_paid" for issue in RulesExtractor().extract(source).errors))
        self.assertFalse(calls[0]["result"]["ok"])
        self.assertEqual(mock.requests, [])
        self.assertEqual(result["pending"], [])


if __name__ == "__main__":
    unittest.main()
