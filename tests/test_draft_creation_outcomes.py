"""Recovery facts for an interrupted multi-currency draft operation.

These tests use the real Agent and SandboxMock. Faults are confined to client
call/receipt boundaries; provider-created invoices remain observable separately
from the identities that the Agent actually received.
"""
import copy
from datetime import date
import unittest

from ledgerly.agent import Agent, RulePlanner
from ledgerly.paypal import PayPalError, Response, SandboxMock

SOURCE = (
    "From: Alex Client <alex@example.test>\n\n"
    "Editing — EUR 120\nDesign — GBP 80\nConsultation — USD 60\nNet 14\n"
)
CURRENCIES = ["EUR", "GBP", "USD"]
TOTALS = ["120", "80", "60"]
INVOICER = {"name": "Test Freelancer", "email_address": "freelancer@example.test"}


class InterruptedMock(SandboxMock):
    def __init__(self, fault=None, at=2):
        super().__init__()
        self.fault, self.at = fault, at
        self.number_calls = 0
        self.create_calls = 0
        self.failure = None

    def generate_next_invoice_number(self):
        self.number_calls += 1
        if self.number_calls == self.at:
            if self.fault == "number_failure":
                raise TimeoutError("Synthetic invoice-number response loss")
            if self.fault == "number_receipt":
                return Response(200, {"invoice_number": None})
        return super().generate_next_invoice_number()

    def create_draft_invoice(self, invoice, prefer_representation=False):
        self.create_calls += 1
        if self.create_calls == self.at and self.fault == "provider_error":
            self.failure = PayPalError(503, "SERVICE_UNAVAILABLE", "Synthetic refusal", "DRAFT_UNAVAILABLE")
            raise self.failure
        response = super().create_draft_invoice(invoice, prefer_representation)
        if self.create_calls == self.at:
            if self.fault == "lost_response":
                raise TimeoutError("Synthetic response loss after actual mock creation")
            if self.fault == "empty_receipt":
                return Response(201, {})
            if self.fault == "duplicate_receipt":
                return Response(201, {"id": next(iter(self.invoices))})
            if self.fault == "conflicting_receipt":
                return Response(201, {**response.body, "id": "ANOTHER-INVOICE"})
            if self.fault == "non_success_receipt":
                return Response(503, response.body)
        return response


def make_agent(client, **kwargs):
    return Agent(client, copy.deepcopy(INVOICER), today=lambda: date(2026, 10, 8), **kwargs)


def run_create(agent):
    run = agent.run("invoice:" + SOURCE, RulePlanner())
    first = next(row["result"] for row in run["history"] if row["role"] == "tool")
    return first, run


class TestDraftCreationOutcomes(unittest.TestCase):
    def assert_known(self, result, agent, count):
        self.assertEqual([row["currency"] for row in result["invoices"]], CURRENCIES[:count])
        self.assertEqual([row["total"] for row in result["invoices"]], TOTALS[:count])
        self.assertEqual(len(agent.ledger), count)
        self.assertEqual(len(agent.list_pending()), count)
        for row in result["invoices"]:
            invoice_id = row["invoice_id"]
            self.assertIn(invoice_id, agent.ledger)
            entry = agent.ledger[invoice_id]
            approval = agent.pending[row["approval_id"]]
            self.assertEqual(entry.currency, row["currency"])
            self.assertEqual(entry.invoice_number, row["invoice_number"])
            self.assertEqual(str(entry.total), row["total"])
            self.assertEqual(entry.status, "DRAFT")
            self.assertEqual(approval.invoice_id, invoice_id)
            self.assertEqual(approval.status, "PENDING")
            self.assertEqual(approval.payload["invoice"]["detail"]["currency_code"], row["currency"])
            self.assertEqual(approval.payload["invoice"]["detail"]["invoice_number"], row["invoice_number"])
        forbidden = ("/send", "/remind", "/payments")
        self.assertFalse(any(path.endswith(forbidden) for _, path, _ in agent.client.requests))

    def assert_failure(self, result, agent, count, stage, outcome, at):
        self.assertIs(result["ok"], False)
        self.assertIs(result["creation_incomplete"], True)
        self.assert_known(result, agent, count)
        failure = result["draft_failure"]
        self.assertEqual(failure["currency"], CURRENCIES[at - 1])
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["outcome"], outcome)
        self.assertEqual(result["unattempted_currencies"], CURRENCIES[at:])
        self.assertEqual(result["confidence"], 0.9)
        self.assertEqual([issue["field"] for issue in result["issues"]], ["currency"])
        self.assertIn("retrying can create duplicates", result["message"])
        for row in result["invoices"]:
            self.assertIn(row["invoice_id"], result["message"])
        self.assertIn(failure["currency"], result["message"])

    def test_success_contract_and_exact_known_drafts(self):
        client = InterruptedMock()
        agent = make_agent(client)
        result, run = run_create(agent)
        self.assertEqual(set(result), {"ok", "invoices", "confidence", "issues", "message"})
        self.assertIs(result["ok"], True)
        self.assert_known(result, agent, 3)
        self.assertEqual(client.number_calls, 3)
        self.assertEqual(client.create_calls, 3)
        self.assertEqual(len(client.invoices), 3)
        self.assertEqual(len([x for x in run["history"] if x["role"] == "tool"]), 4)

    def test_number_failure_retains_known_drafts_and_never_attempts_failed_currency(self):
        for at in (1, 2, 3):
            with self.subTest(at=at):
                client = InterruptedMock("number_failure", at)
                agent = make_agent(client)
                result, run = run_create(agent)
                self.assert_failure(result, agent, at - 1, "invoice_number", "NOT_ATTEMPTED", at)
                self.assertIsNone(result["draft_failure"]["invoice_number"])
                self.assertEqual(client.number_calls, at)
                self.assertEqual(client.create_calls, at - 1)
                self.assertEqual(len(client.invoices), at - 1)
                self.assertIn("No draft request was made", run["final"])

    def test_unusable_number_receipt_does_not_attempt_create(self):
        client = InterruptedMock("number_receipt")
        agent = make_agent(client)
        result, _ = run_create(agent)
        self.assert_failure(result, agent, 1, "invoice_number", "NOT_ATTEMPTED", 2)
        self.assertIsNone(result["draft_failure"]["invoice_number"])
        self.assertEqual(client.create_calls, 1)

    def test_local_body_failure_keeps_known_allocated_number(self):
        client = InterruptedMock()
        agent = make_agent(client)
        del agent.invoicer["email_address"]
        result, _ = run_create(agent)
        self.assert_failure(result, agent, 0, "draft_body", "NOT_ATTEMPTED", 1)
        self.assertEqual(result["draft_failure"]["invoice_number"], "LDG-0001")
        self.assertEqual(client.number_calls, 1)
        self.assertEqual(client.create_calls, 0)
        self.assertEqual(client.invoices, {})

    def test_provider_error_is_unknown_and_detaches_provider_error_body(self):
        client = InterruptedMock("provider_error")
        agent = make_agent(client)
        result, _ = run_create(agent)
        self.assert_failure(result, agent, 1, "create_draft", "UNKNOWN", 2)
        failure = result["draft_failure"]
        self.assertEqual(failure["invoice_number"], "LDG-0002")
        self.assertEqual(failure["error"]["http_status"], 503)
        self.assertEqual(failure["error"]["provider"], client.failure.body)
        self.assertEqual(client.number_calls, 2)
        self.assertEqual(client.create_calls, 2)
        self.assertEqual(len(client.invoices), 1)
        failure["error"]["provider"]["details"][0]["issue"] = "CHANGED"
        self.assertEqual(client.failure.body["details"][0]["issue"], "DRAFT_UNAVAILABLE")

    def test_lost_response_preserves_actual_mock_creation_as_unknown(self):
        for at in (1, 2, 3):
            with self.subTest(at=at):
                client = InterruptedMock("lost_response", at)
                agent = make_agent(client)
                result, run = run_create(agent)
                self.assert_failure(result, agent, at - 1, "create_draft", "UNKNOWN", at)
                self.assertEqual(client.number_calls, at)
                self.assertEqual(client.create_calls, at)
                self.assertEqual(len(client.invoices), at)
                self.assertIn("UNKNOWN", run["final"])
                unknown_id = list(client.invoices)[-1]
                self.assertNotIn(unknown_id, agent.ledger)
                self.assertNotIn(unknown_id, [a.invoice_id for a in agent.pending.values()])

    def test_unusable_or_conflicting_receipts_never_invent_confirmed_drafts(self):
        for fault in ("empty_receipt", "duplicate_receipt", "conflicting_receipt", "non_success_receipt"):
            with self.subTest(fault=fault):
                client = InterruptedMock(fault)
                agent = make_agent(client)
                result, _ = run_create(agent)
                self.assert_failure(result, agent, 1, "draft_response", "UNKNOWN", 2)
                self.assertEqual(result["draft_failure"]["invoice_number"], "LDG-0002")
                self.assertEqual(client.number_calls, 2)
                self.assertEqual(client.create_calls, 2)
                self.assertEqual(len(client.invoices), 2)
                self.assertEqual(agent.ledger[next(iter(client.invoices))].currency, "EUR")

    def test_complete_invoice_representation_remains_accepted(self):
        class RepresentationMock(SandboxMock):
            def create_draft_invoice(self, invoice, prefer_representation=False):
                return super().create_draft_invoice(invoice, True)
        client = RepresentationMock()
        agent = make_agent(client)
        result, _ = run_create(agent)
        self.assertIs(result["ok"], True)
        self.assert_known(result, agent, 3)

    def test_returned_recovery_rows_are_detached_from_ledger_and_approval(self):
        client = InterruptedMock("lost_response")
        agent = make_agent(client)
        result, _ = run_create(agent)
        self.assert_failure(result, agent, 1, "create_draft", "UNKNOWN", 2)
        invoice_id = result["invoices"][0]["invoice_id"]
        approval_id = result["invoices"][0]["approval_id"]
        pending_before = agent.pending[approval_id].to_dict()
        result["invoices"][0].update(invoice_id="CHANGED", invoice_number="CHANGED", total="0")
        result["draft_failure"]["currency"] = "JPY"
        result["issues"][0]["message"] = "CHANGED"
        self.assertEqual(agent.ledger[invoice_id].currency, "EUR")
        self.assertEqual(str(agent.ledger[invoice_id].total), "120")
        self.assertEqual(agent.pending[approval_id].to_dict(), pending_before)

    def test_invalid_values_still_refuse_before_any_provider_effect(self):
        client = InterruptedMock()
        agent = make_agent(client)
        result = agent.tool_create_invoice(SOURCE.replace("EUR 120", "EUR 0.015"))
        self.assertIs(result["ok"], False)
        self.assertIs(result["needs_review"], True)
        self.assertNotIn("creation_incomplete", result)
        self.assertEqual(client.number_calls, 0)
        self.assertEqual(client.create_calls, 0)
        self.assertEqual(client.requests, [])

    def test_retained_draft_still_uses_the_existing_explicit_approval(self):
        client = InterruptedMock("lost_response")
        agent = make_agent(client)
        result, _ = run_create(agent)
        self.assert_known(result, agent, 1)
        approval_id = result["invoices"][0]["approval_id"]
        invoice_id = result["invoices"][0]["invoice_id"]
        agent.approve(approval_id, approver="synthetic receiving")
        self.assertEqual(agent.pending[approval_id].status, "APPROVED")
        self.assertEqual(client.invoices[invoice_id]["status"], "SENT")
        self.assertEqual(client.invoices[list(client.invoices)[-1]]["status"], "DRAFT")
        self.assertEqual(client.create_calls, 2)


if __name__ == "__main__":
    unittest.main()
