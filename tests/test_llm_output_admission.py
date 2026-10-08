"""Malformed model content must stop before any invoice allocation.

Contributor: estate-7c2609b6545f/commons_execution.
Uses real extraction, validation, Agent and SandboxMock; only complete() is injected.
Run with unittest or pytest. No model, network, provider or outgoing action is used.
"""
import copy
import json
import math
import unittest
from datetime import date
from decimal import Decimal

from ledgerly.agent import Agent
from ledgerly.extract import HybridExtractor, LLMExtractor, RulesExtractor
from ledgerly.paypal import SandboxMock

SOURCE = "From: Avery <avery@client.example>\n\n- 2 x Illustration @ $75\nNet 15\n"
INVOICER = {"name": "Local fixture", "email_address": "seller@ledgerly.example"}


def payload():
    return {
        "client_name": "Avery", "client_email": "avery@client.example",
        "currency": "USD",
        "line_items": [{"desc": "Illustration", "qty": 2, "unit_price": 75}],
        "due_days": 15, "amount_paid": 0, "confidence": 0.9, "issues": [],
    }


def response_with(key, value):
    result = payload()
    result[key] = value
    return result


class TestLLMOutputAdmission(unittest.TestCase):
    def extract(self, value, *, raw=False, source=SOURCE):
        calls = []
        def complete(prompt):
            calls.append(prompt)
            return value if raw else json.dumps(value)
        result = LLMExtractor(complete).extract(source)
        self.assertEqual(len(calls), 1)
        return result

    def assert_unusable(self, ex):
        self.assertEqual(ex.source, "llm")
        self.assertEqual(ex.confidence, 0.0)
        self.assertEqual(ex.line_items, [])
        self.assertTrue(any(i.field == "*" and i.severity == "error"
                            and i.message.startswith("LLM output unusable:")
                            for i in ex.issues))
        json.dumps(ex.to_dict(), allow_nan=False)

    def test_valid_fenced_response_and_compatible_numeric_text(self):
        value = payload()
        value["client_email"] = "AVERY@CLIENT.EXAMPLE"
        value["line_items"][0].update(qty="2.0", unit_price="75.00", unit="items")
        value.update(due_days="15", confidence="0.9")
        fence = chr(96) * 3
        ex = self.extract(fence + "json\n" + json.dumps(value) + "\n" + fence, raw=True)
        self.assertEqual(ex.client_email, "avery@client.example")
        self.assertEqual(ex.line_items[0].to_dict(), {
            "desc": "Illustration", "qty": "2.0", "unit_price": "75.00",
            "currency": "USD", "unit": "items",
        })
        self.assertEqual(ex.total(), Decimal("150"))
        self.assertEqual(ex.due_days, 15)
        self.assertEqual(ex.confidence, 0.9)
        self.assertEqual(ex.errors, [])

    def test_malformed_field_shapes_are_unusable(self):
        cases = [
            ("client_email", ["avery@client.example"]),
            ("client_email", 42), ("client_name", {"name": "Avery"}),
            ("currency", {"code": "USD"}), ("currency", ["USD"]),
            ("line_items", {"desc": "Illustration"}),
            ("line_items", ["Illustration"]), ("line_items", [None]),
        ]
        for key, value in cases:
            with self.subTest(field=key, value=value):
                self.assert_unusable(self.extract(response_with(key, value)))
        for key, value in (("desc", ["Illustration"]), ("currency", ["USD"]),
                           ("unit", {"label": "items"})):
            with self.subTest(item_field=key):
                item = payload()
                item["line_items"][0][key] = value
                self.assert_unusable(self.extract(item))

    def test_malformed_issue_shapes_are_not_silently_discarded(self):
        good = {"field": "client_name", "severity": "info", "message": "Review name."}
        cases = [
            "warning", good, ["warning"], [None],
            [dict(good, severity=["warning"])],
            [dict(good, field=["client_name"])],
            [dict(good, message={"text": "Review name."})],
            [dict(good, severity="fatal")],
            [{"field": "client_name", "severity": "info"}],
            [dict(good, extra=True)],
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assert_unusable(self.extract(response_with("issues", value)))
        ex = self.extract(response_with("issues", [good]))
        self.assertEqual([i.to_dict() for i in ex.issues], [good])
        self.assertEqual(ex.confidence, 0.9)

    def test_confidence_must_be_finite_in_range_and_not_boolean(self):
        for value in ("NaN", "Infinity", "-Infinity", float("nan"), float("inf"),
                      -0.2, 1.2, True, False, 10 ** 400):
            with self.subTest(value=repr(value)):
                self.assert_unusable(self.extract(response_with("confidence", value)))
        for value in (0, 0.5, 1, "0.75"):
            with self.subTest(valid=value):
                ex = self.extract(response_with("confidence", value))
                self.assertEqual(ex.confidence, float(value))
                self.assertEqual(ex.errors, [])

    def test_supplied_due_days_are_integral_without_boolean_coercion(self):
        for value in (True, False, 1.75, -0.5, float("inf"), ["15"]):
            with self.subTest(value=value):
                self.assert_unusable(self.extract(response_with("due_days", value)))
        for value in (None, 0, 15, 15.0, "15", 365):
            with self.subTest(valid=value):
                ex = self.extract(response_with("due_days", value))
                self.assertEqual(ex.due_days, None if value is None else int(value))
                self.assertEqual(ex.errors, [])

    def test_nonstring_and_invalid_json_return_existing_refusal(self):
        for value in (None, {}, [], 42, b"{}", "not JSON", "[]"):
            with self.subTest(value=value):
                self.assert_unusable(self.extract(value, raw=True))

    def test_missing_and_nullable_optional_values_preserve_existing_defaults(self):
        value = payload()
        for key in ("confidence", "amount_paid", "issues"):
            del value[key]
        ex = self.extract(value)
        self.assertEqual(ex.confidence, 0.5)
        self.assertEqual(ex.amount_paid, Decimal(0))
        self.assertEqual(ex.errors, [])
        value = payload()
        for key in ("client_name", "currency", "line_items", "due_days", "issues", "amount_paid"):
            value[key] = None
        ex = self.extract(value)
        self.assertEqual(ex.client_email, "avery@client.example")
        self.assertIsNone(ex.client_name)
        self.assertIsNone(ex.due_days)
        self.assertTrue(math.isfinite(ex.confidence))
        self.assertFalse(any(i.message.startswith("LLM output unusable:") for i in ex.issues))
        self.assertTrue(ex.errors)

    def test_existing_grounding_precision_and_business_validation_remain(self):
        ex = self.extract(response_with("client_email", "invented@elsewhere.example"))
        self.assertIsNone(ex.client_email)
        self.assertTrue(any("hallucination" in i.message for i in ex.errors))
        value = payload()
        value["line_items"][0]["unit_price"] = "75.001"
        ex = self.extract(value)
        self.assertTrue(any(i.field == "line_items[0].unit_price" for i in ex.errors))
        self.assertFalse(any(i.message.startswith("LLM output unusable:") for i in ex.issues))
        ex = self.extract(response_with("due_days", -1))
        self.assertTrue(any(i.field == "due_days" for i in ex.errors))
        self.assertFalse(any(i.message.startswith("LLM output unusable:") for i in ex.issues))

    def test_agent_refuses_before_allocation_preserves_work_and_allows_healthy_retry(self):
        for key, value in (
            ("client_email", ["avery@client.example"]), ("client_name", {"name": "Avery"}),
            ("confidence", "NaN"), ("due_days", 1.75), ("issues", ["warning"]),
            ("amount_paid", []), ("amount_paid", {}), ("amount_paid", False),
        ):
            with self.subTest(field=key):
                current = [payload()]
                calls = []
                def complete(prompt):
                    calls.append(prompt)
                    return json.dumps(current[0])
                mock = SandboxMock()
                agent = Agent(mock, INVOICER, extractor=LLMExtractor(complete),
                              today=lambda: date(2026, 10, 1))
                first = agent.tool_create_invoice(SOURCE)
                self.assertTrue(first["ok"])
                self.assertEqual(first["invoices"][0]["invoice_number"], "LDG-0001")
                before = copy.deepcopy((mock.requests, mock.invoices, mock._seq,
                                        agent.ledger, agent.pending, agent.audit,
                                        agent._seen_events, agent.client.blocked))
                current[0] = response_with(key, value)
                result = agent.tool_create_invoice(SOURCE)
                self.assertFalse(result["ok"])
                self.assertTrue(result["needs_review"])
                self.assertEqual(result["confidence"], 0.0)
                self.assertEqual((mock.requests, mock.invoices, mock._seq,
                                  agent.ledger, agent.pending, agent.audit,
                                  agent._seen_events, agent.client.blocked), before)
                current[0] = payload()
                retry = agent.tool_create_invoice(SOURCE)
                self.assertTrue(retry["ok"])
                self.assertEqual(retry["invoices"][0]["invoice_number"], "LDG-0002")
                self.assertEqual(len(mock.invoices), 2)
                self.assertEqual(len(agent.pending), 2)
                self.assertEqual(len(calls), 3)
                self.assertTrue(all(inv["status"] == "DRAFT" for inv in mock.invoices.values()))
                self.assertFalse(any(path.endswith("/send") for _, path, _ in mock.requests))

    def test_amount_paid_shape_refusal_preserves_legacy_numeric_values(self):
        for value in ([], {}, False, True):
            with self.subTest(malformed=value):
                self.assert_unusable(self.extract(response_with("amount_paid", value)))
        for value in (0, None, "", "0", "25.00", 25, 25.0):
            with self.subTest(compatible=value):
                ex = self.extract(response_with("amount_paid", value))
                self.assertEqual(ex.errors, [])
                self.assertEqual(ex.confidence, 0.9)
                self.assertEqual(ex.amount_paid, Decimal(str(value or 0)))
                if value == "25.00":
                    self.assertEqual(str(ex.amount_paid), "25.00")

    def test_hybrid_malformed_fallback_preserves_primary_review_errors(self):
        calls = []
        def complete(prompt):
            calls.append(prompt)
            return json.dumps(response_with("client_email", ["avery@client.example"]))
        extractor = HybridExtractor(RulesExtractor(), LLMExtractor(complete), threshold=1.0)
        mock = SandboxMock()
        agent = Agent(mock, INVOICER, extractor=extractor)
        result = agent.tool_create_invoice("- 2 x Illustration @ $75\nNet 15\n")
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_review"])
        self.assertTrue(any(i["field"] == "client_email" and i["severity"] == "error"
                            for i in result["issues"]))
        self.assertEqual(len(calls), 1)
        self.assertEqual(mock.requests, [])
        self.assertEqual(mock.invoices, {})
        self.assertEqual(agent.pending, {})

    def test_completion_transport_exception_is_not_malformed_content(self):
        def unavailable(_prompt):
            raise RuntimeError("fixture completion unavailable")
        with self.assertRaisesRegex(RuntimeError, "fixture completion unavailable"):
            LLMExtractor(unavailable).extract(SOURCE)


if __name__ == "__main__":
    unittest.main()
