"""Preserve reviewed invoice descriptions at the existing 200-code-point writer boundary."""
import copy
import importlib.util
import json
from datetime import date
from pathlib import Path
import unittest

from ledgerly.agent import Agent
from ledgerly.extract import Extraction, LLMExtractor, RulesExtractor, validate
from ledgerly.paypal import SandboxMock, build_invoice

TODAY = date(2026, 10, 8)
SOURCE = "From: Client <client@example.test>\n\n- Work - $10\nNet 30\n"
INVOICER = {"name": "Freelancer", "email_address": "freelancer@example.test"}
PREFIX = "Deliver the revised manuscript. ".ljust(200, "x")
OVERSIZE = PREFIX + " Excludes translation rights."


def payload(description="Work", *, items=None):
    return {
        "client_name": "Client", "client_email": "client@example.test", "currency": "USD",
        "line_items": items if items is not None else [
            {"desc": description, "qty": "1", "unit_price": "10", "currency": "USD"}
        ],
        "due_days": 30, "amount_paid": "0", "confidence": 1.0,
    }


def invoice_state(agent, mock):
    return copy.deepcopy({
        "invoices": mock.invoices, "requests": mock.requests, "sequence": mock._seq,
        "ledger": {key: entry.to_dict() for key, entry in agent.ledger.items()},
        "pending": {key: action.to_dict() for key, action in agent.pending.items()},
    })


class DescriptionAdmissionTests(unittest.TestCase):
    def new_agent(self, data):
        mock = SandboxMock()
        extractor = LLMExtractor(lambda _: json.dumps(data, ensure_ascii=False))
        return Agent(mock, INVOICER, extractor=extractor, today=lambda: TODAY), mock

    def assert_refused_without_allocation(self, data):
        agent, mock = self.new_agent(data)
        before = invoice_state(agent, mock)
        result = agent.tool_create_invoice(SOURCE)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["needs_review"], result)
        self.assertTrue(any(issue["field"].endswith(".desc") and issue["severity"] == "error"
                            for issue in result["issues"]), result)
        self.assertEqual(invoice_state(agent, mock), before)
        return result

    def test_accepted_descriptions_reach_the_actual_invoice_without_changes(self):
        for description in [PREFIX[:199], PREFIX, "海" * 200, "😀" * 200,
                            'Editing "literal" <markup> & café']:
            with self.subTest(description_length=len(description), prefix=description[:8]):
                agent, mock = self.new_agent(payload(description))
                result = agent.tool_create_invoice(SOURCE)
                self.assertTrue(result["ok"], result)
                invoice = mock.invoices[result["invoices"][0]["invoice_id"]]
                self.assertEqual(invoice["items"][0]["name"], description)
                self.assertEqual(invoice["status"], "DRAFT")
                self.assertEqual(invoice["amount"]["value"], "10.00")
                self.assertEqual(len(agent.list_pending()), 1)
                self.assertFalse(any(path.endswith(("/send", "/remind", "/payments"))
                                     for _, path, _ in mock.requests))

    def test_model_oversize_descriptions_are_reviewable_before_allocation(self):
        for description in [PREFIX + "x", OVERSIZE, "海" * 201, "😀" * 201]:
            with self.subTest(length=len(description), prefix=description[:8]):
                data = payload(description)
                original = copy.deepcopy(data)
                self.assert_refused_without_allocation(data)
                extraction = LLMExtractor(lambda _: json.dumps(data, ensure_ascii=False)).extract(SOURCE)
                self.assertEqual(extraction.line_items[0].desc, description)
                self.assertEqual(data, original)

    def test_rules_preserve_the_full_description_and_hold_the_job(self):
        source = "From: Client <client@example.test>\n\n- " + OVERSIZE + " - $10\nNet 30\n"
        extraction = RulesExtractor().extract(source)
        self.assertEqual(extraction.line_items[0].desc, OVERSIZE)
        self.assertTrue(any(issue.field == "line_items[0].desc" and issue.severity == "error"
                            for issue in extraction.issues))
        mock = SandboxMock()
        agent = Agent(mock, INVOICER, today=lambda: TODAY)
        before = invoice_state(agent, mock)
        result = agent.tool_create_invoice(source)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["needs_review"])
        self.assertEqual(invoice_state(agent, mock), before)

    def test_custom_extractor_cannot_bypass_description_admission(self):
        extraction = Extraction.from_dict(payload(OVERSIZE))
        extraction.confidence = 1.0
        original = copy.deepcopy(extraction)

        class Checked:
            def extract(self, _):
                return extraction

        mock = SandboxMock()
        agent = Agent(mock, INVOICER, extractor=Checked(), today=lambda: TODAY)
        before = invoice_state(agent, mock)
        result = agent.tool_create_invoice(SOURCE)
        self.assertFalse(result["ok"], result)
        self.assertEqual(invoice_state(agent, mock), before)
        self.assertEqual(extraction, original)

    def test_direct_builder_refuses_before_slicing_a_description(self):
        extraction = Extraction.from_dict(payload(OVERSIZE))
        original = copy.deepcopy(extraction)
        with self.assertRaises(ValueError):
            build_invoice(extraction, INVOICER, "DIRECT", TODAY)
        self.assertEqual(extraction, original)

    def test_later_currency_refusal_preserves_prior_work_and_allows_a_corrected_retry(self):
        data = payload("Previously reviewed work")
        mock = SandboxMock()
        agent = Agent(mock, INVOICER, extractor=LLMExtractor(lambda _: json.dumps(data)),
                      today=lambda: TODAY)
        first = agent.tool_create_invoice(SOURCE)
        self.assertTrue(first["ok"])
        data["currency"] = "EUR"
        data["line_items"] = [
            {"desc": "Valid first currency", "qty": "1", "unit_price": "10", "currency": "EUR"},
            {"desc": OVERSIZE, "qty": "1", "unit_price": "20", "currency": "USD"},
        ]
        before = invoice_state(agent, mock)
        refused = agent.tool_create_invoice(SOURCE)
        self.assertFalse(refused["ok"], refused)
        self.assertTrue(any(issue["field"] == "line_items[1].desc"
                            for issue in refused["issues"]), refused)
        self.assertEqual(invoice_state(agent, mock), before)
        data["line_items"][1]["desc"] = "Corrected second currency"
        accepted = agent.tool_create_invoice(SOURCE)
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(len(accepted["invoices"]), 2)
        self.assertEqual(len(mock.invoices), 3)
        self.assertEqual(len(agent.list_pending()), 3)
        prior_id = first["invoices"][0]["invoice_id"]
        self.assertEqual(mock.invoices[prior_id], before["invoices"][prior_id])
        names = {invoice["items"][0]["name"] for invoice in mock.invoices.values()}
        self.assertEqual(names, {"Previously reviewed work", "Valid first currency",
                                 "Corrected second currency"})
        self.assertFalse(any(path.endswith(("/send", "/remind", "/payments"))
                             for _, path, _ in mock.requests))

    def test_human_review_keeps_oversize_text_available_for_correction(self):
        source = Path(__file__).resolve().parents[1] / "web-demo/python/review.py"
        spec = importlib.util.spec_from_file_location("description_admission_review", source)
        review = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(review)
        for description, accepted in [(PREFIX, True), ("😀" * 200, True), (OVERSIZE, False)]:
            with self.subTest(length=len(description)):
                fields = {
                    "client_name": "Client", "client_email": "client@example.test",
                    "due_days": "30", "amount_paid": "0",
                    "line_items": [{"desc": description, "qty": "1", "unit_price": "10",
                                    "currency": "USD", "unit": ""}],
                }
                original = copy.deepcopy(fields)
                extraction = review.prepare_review(fields)
                self.assertEqual(fields, original)
                self.assertEqual(extraction.line_items[0].desc, description)
                self.assertEqual(not extraction.errors, accepted)
                if not accepted:
                    self.assertTrue(any(issue.field == "line_items[0].desc"
                                        for issue in extraction.errors))

    def test_shared_validation_reports_the_exact_item_without_mutating_the_job(self):
        data = payload(items=[
            {"desc": "Unaffected first line", "qty": "1", "unit_price": "10", "currency": "USD"},
            {"desc": OVERSIZE, "qty": "1", "unit_price": "20", "currency": "USD"},
        ])
        extraction = Extraction.from_dict(data)
        original = copy.deepcopy(extraction)
        issues = validate(extraction)
        self.assertEqual([issue.field for issue in issues if issue.severity == "error"],
                         ["line_items[1].desc"])
        self.assertEqual(extraction, original)


if __name__ == "__main__":
    unittest.main()
