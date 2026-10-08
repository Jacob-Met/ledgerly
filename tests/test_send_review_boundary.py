"""Approval behavior against authored provider changes and read failures."""
from copy import deepcopy
from decimal import Decimal
from urllib.error import URLError

import pytest

from conftest import INVOICER, load
from ledgerly.agent import Agent, ApprovalRequired
from ledgerly.paypal import PayPalError, Response, SandboxMock


def draft(clock, fixture="01_simple_usd_hourly.txt"):
    mock = SandboxMock()
    agent = Agent(mock, INVOICER, today=clock)
    result = agent.tool_create_invoice(load(fixture))
    assert result["ok"], result
    invoice = result["invoices"][0]
    return agent, mock, invoice["invoice_id"], invoice["approval_id"]


def posts_since(mock, offset):
    return [row for row in mock.requests[offset:] if row[0] == "POST"]


def assert_rejected_without_send(agent, mock, invoice_id, action_id):
    original = deepcopy(agent.pending[action_id].payload)
    offset = len(mock.requests)
    with pytest.raises(ValueError, match="already REJECTED.*review"):
        agent.approve(action_id)
    action = agent.pending[action_id]
    assert action.status == "REJECTED"
    assert action.payload == original
    assert action.result["reason"]
    assert posts_since(mock, offset) == []
    assert agent.client._permits == set()
    event = agent.audit[-1]
    assert event["event"] == "invoice_send_invalidated"
    assert event["action"] == action_id
    assert event["invoice"] == invoice_id
    assert event["reason"] == action.result["reason"]
    before_retry = list(mock.requests)
    with pytest.raises(ValueError, match="already REJECTED"):
        agent.approve(action_id)
    assert mock.requests == before_retry
    assert all(row["id"] != action_id for row in agent.list_pending())
    with pytest.raises(ApprovalRequired):
        agent.client.send_invoice(invoice_id)
    assert mock.requests == before_retry


@pytest.mark.parametrize("changed_field", [
    "cc-recipient", "shipping-recipient", "item-description", "item-count",
    "same-total-unit-price", "note", "invoice-number", "invoice-date",
    "new-terms", "tip-permission", "same-total-adjustments",
])
def test_material_content_changes_require_a_fresh_review(clock, changed_field):
    agent, mock, invoice_id, action_id = draft(clock)
    invoice = mock.invoices[invoice_id]
    if changed_field == "cc-recipient":
        invoice["additional_recipients"] = ["another@fixture.example"]
    elif changed_field == "shipping-recipient":
        invoice["primary_recipients"][0]["shipping_info"] = {"name": {"given_name": "Another Person"}}
    elif changed_field == "item-description":
        invoice["items"][0]["description"] = "New unreviewed work details"
    elif changed_field == "item-count":
        extra = deepcopy(invoice["items"][0])
        extra["quantity"] = "0"
        invoice["items"].append(extra)
    elif changed_field == "same-total-unit-price":
        item = invoice["items"][0]
        item["quantity"] = str(Decimal(item["quantity"]) * 2)
        item["unit_amount"]["value"] = str(Decimal(item["unit_amount"]["value"]) / 2)
    elif changed_field == "note":
        invoice["detail"]["note"] = "Different outgoing message"
    elif changed_field == "invoice-number":
        invoice["detail"]["invoice_number"] = "ANOTHER-INVOICE"
    elif changed_field == "invoice-date":
        invoice["detail"]["invoice_date"] = "2026-12-31"
    elif changed_field == "new-terms":
        invoice["detail"]["terms_and_conditions"] = "Unreviewed cancellation charge"
    elif changed_field == "tip-permission":
        invoice["configuration"]["allow_tip"] = True
    elif changed_field == "same-total-adjustments":
        invoice["amount"]["breakdown"]["shipping"] = {
            "amount": {"currency_code": "USD", "value": "10.00"}}
        invoice["amount"]["breakdown"]["discount"] = {
            "invoice_discount": {"amount": {"currency_code": "USD", "value": "10.00"}}}
    assert_rejected_without_send(agent, mock, invoice_id, action_id)
    assert mock.invoices[invoice_id]["status"] == "DRAFT"


def test_known_response_metadata_and_numeric_spelling_allow_the_reviewed_send(clock):
    agent, mock, invoice_id, action_id = draft(clock)
    reviewed = deepcopy(agent.pending[action_id].payload)
    invoice = mock.invoices[invoice_id]
    invoice["detail"]["metadata"]["last_update_time"] = "2026-10-01T01:00:00Z"
    invoice["parent_id"] = "provider-group-id"
    invoice["additional_recipients"] = []
    for number, item in enumerate(invoice["items"]):
        item["id"] = f"provider-item-{number}"
        item["quantity"] = str(Decimal(item["quantity"]).quantize(Decimal("0.000")))
        item["unit_amount"]["value"] = str(Decimal(item["unit_amount"]["value"]).quantize(Decimal("0.000")))
    get_invoice = mock.get_invoice

    def fresh(invoice_id):
        assert agent.client._permits == set()
        response = get_invoice(invoice_id)
        response.body.pop("payments")  # Unpaid provider draft examples omit history.
        return response

    mock.get_invoice = fresh
    offset = len(mock.requests)
    agent.approve(action_id)
    assert [row[:2] for row in mock.requests[offset:]] == [
        ("GET", f"/v2/invoicing/invoices/{invoice_id}"),
        ("POST", f"/v2/invoicing/invoices/{invoice_id}/send"),
    ]
    assert agent.pending[action_id].status == "APPROVED"
    assert agent.pending[action_id].payload == reviewed
    assert agent.client._permits == set()


@pytest.mark.parametrize("bad_read", [
    "not-an-object", "wrong-id", "missing-status", "missing-items", "boolean-quantity",
    "unknown-status", "blank-status", "padded-status",
    "missing-total", "nonfinite-total", "inconsistent-balance", "non-object-breakdown",
    "payment-history", "non-object-payments", "missing-recipients", "non-object-invoicer",
])
def test_unusable_read_holds_original_review_and_can_retry(clock, bad_read):
    agent, mock, invoice_id, action_id = draft(clock)
    original = agent.pending[action_id].to_dict()
    ledger = agent.ledger[invoice_id].to_dict()
    audit = deepcopy(agent.audit)
    get_invoice = mock.get_invoice

    def malformed(invoice_id):
        assert agent.client._permits == set()
        response = get_invoice(invoice_id)
        invoice = response.body
        if bad_read == "not-an-object":
            return Response(200, [])
        if bad_read == "wrong-id":
            invoice["id"] = "ANOTHER-INVOICE"
        elif bad_read == "missing-status":
            invoice.pop("status")
        elif bad_read in {"unknown-status", "blank-status", "padded-status"}:
            invoice["status"] = {"unknown-status": "UNAVAILABLE", "blank-status": " ",
                                 "padded-status": "DRAFT "}[bad_read]
        elif bad_read == "missing-items":
            invoice.pop("items")
        elif bad_read == "boolean-quantity":
            invoice["items"][0]["quantity"] = True
        elif bad_read == "missing-total":
            invoice.pop("amount")
        elif bad_read == "nonfinite-total":
            invoice["amount"]["value"] = "NaN"
        elif bad_read == "inconsistent-balance":
            invoice["due_amount"]["value"] = "1"
        elif bad_read == "non-object-breakdown":
            invoice["amount"]["breakdown"] = []
        elif bad_read == "payment-history":
            invoice["payments"]["transactions"] = [{"payment_id": "prior-provider-payment"}]
        elif bad_read == "non-object-payments":
            invoice["payments"] = []
        elif bad_read == "missing-recipients":
            invoice.pop("primary_recipients")
        elif bad_read == "non-object-invoicer":
            invoice["invoicer"] = []
        return response

    mock.get_invoice = malformed
    offset = len(mock.requests)
    with pytest.raises(ValueError):
        agent.approve(action_id)
    assert posts_since(mock, offset) == []
    assert agent.pending[action_id].to_dict() == original
    assert agent.ledger[invoice_id].to_dict() == ledger
    assert agent.audit == audit
    assert agent.client._permits == set()
    mock.get_invoice = get_invoice
    agent.approve(action_id)
    assert agent.pending[action_id].status == "APPROVED"
    assert len(posts_since(mock, offset)) == 1


@pytest.mark.parametrize("error", [
    TimeoutError("authored read timeout"), URLError("authored unavailable read"),
    PayPalError(503, "SERVICE_UNAVAILABLE", "authored provider read failure"),
])
def test_failed_read_is_not_an_unknown_outgoing_outcome(clock, error):
    agent, mock, invoice_id, action_id = draft(clock)
    original = agent.pending[action_id].to_dict()
    audit = deepcopy(agent.audit)
    get_invoice = mock.get_invoice

    def unavailable(invoice_id):
        get_invoice(invoice_id)
        raise error

    mock.get_invoice = unavailable
    offset = len(mock.requests)
    with pytest.raises(type(error)) as caught:
        agent.approve(action_id)
    assert caught.value is error
    assert agent.pending[action_id].to_dict() == original
    assert agent.audit == audit
    assert posts_since(mock, offset) == []
    assert agent.client._permits == set()
    mock.get_invoice = get_invoice
    agent.approve(action_id)
    assert len(posts_since(mock, offset)) == 1


@pytest.mark.parametrize("status", ["CANCELLED", "SENT", "PAID"])
def test_known_non_draft_is_rejected_before_any_send_attempt(clock, status):
    agent, mock, invoice_id, action_id = draft(clock)
    mock.invoices[invoice_id]["status"] = status
    assert_rejected_without_send(agent, mock, invoice_id, action_id)
    assert mock.invoices[invoice_id]["status"] == status


def test_outgoing_deposit_must_still_match_the_human_review(clock):
    agent, mock, invoice_id, action_id = draft(clock, "07_partial_payment_deposit.txt")
    agent.ledger[invoice_id].prepaid += Decimal("1")
    assert_rejected_without_send(agent, mock, invoice_id, action_id)
    assert mock.invoices[invoice_id]["payments"]["transactions"] == []
