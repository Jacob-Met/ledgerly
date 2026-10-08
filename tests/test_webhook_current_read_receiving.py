"""Independent receiving for webhook admission on the merged reminder owner code.

The source is selected by PYTHONPATH. All effects use native offline SandboxMock;
the reviewer never activates HttpPayPalClient or reads provider credentials.
"""

import copy
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from ledgerly.agent import Agent, ApprovalRequired
from ledgerly.paypal import PayPalError, SandboxMock, WebhookError


JOB = """From: Maya Reader <maya@example.invalid>
Subject: Manuscript proofreading

Proofreading: 18 hours @ £40/hr
Style sheet preparation: 2 hrs @ £40/hr
We pay within 30 days of invoice.
"""
INVOICER = {"name": "Receiving Freelancer", "email_address": "reviewer@example.invalid"}


class Clock:
    def __init__(self):
        self.day = date(2026, 10, 1)

    def __call__(self):
        return self.day


def case(count=1):
    clock = Clock()
    mock = SandboxMock(now=lambda: datetime.combine(clock.day, time.min, tzinfo=timezone.utc))
    agent = Agent(mock, INVOICER, today=clock, webhook_verifier=mock.verify_webhook_signature)
    invoices = []
    for _ in range(count):
        result = agent.tool_create_invoice(JOB)
        assert result["ok"], result
        row = result["invoices"][0]
        agent.approve(row["approval_id"])
        invoices.append(row["invoice_id"])
    clock.day = date(2026, 11, 10)
    mock.requests.clear()
    return agent, mock, clock, invoices


def queue(agent, invoice_id):
    result = agent.tool_send_reminder(invoice_id)
    assert result["ok"], result
    return result["approval_id"]


def updated(mock, invoice_id):
    return mock.make_webhook_event("INVOICING.INVOICE.UPDATED", invoice_id)


def event_invoice(event):
    resource = event["resource"]
    return resource.get("invoice", resource)


def deliver(agent, mock, event, **encoding):
    raw = json.dumps(event, **encoding).encode()
    return agent.handle_webhook(raw, mock.sign(raw))


def state(agent):
    # Observe exact cached facts without invoking list_pending's date refresh.
    return copy.deepcopy({
        "ledger": {iid: vars(entry) for iid, entry in agent.ledger.items()},
        "actions": {aid: action.to_dict() for aid, action in agent.pending.items()},
    })


def outgoing(mock):
    return [request for request in mock.requests
            if request[1].endswith(("/send", "/remind", "/payments"))]


def assert_closed(agent, mock, invoice_id):
    assert outgoing(mock) == []
    with pytest.raises(ApprovalRequired):
        agent.client.remind_invoice(invoice_id)
    assert outgoing(mock) == []


def test_delayed_partial_event_observes_current_full_payment_without_restoring_old_balance():
    agent, mock, _, (iid,) = case()
    aid = queue(agent, iid)
    reviewed = copy.deepcopy(agent.pending[aid].payload)
    old = mock.simulate_payer_payment(iid, Decimal("100"))
    mock.simulate_payer_payment(iid, Decimal("700"))
    mock.requests.clear()

    result = deliver(agent, mock, old)

    assert result["ok"] and result["to"] == "PAID"
    assert agent.ledger[iid].status == "PAID"
    assert agent.ledger[iid].paid_amount == Decimal("800")
    assert agent.ledger[iid].balance == 0
    assert agent.pending[aid].status == "REJECTED"
    assert agent.pending[aid].payload == reviewed
    assert mock.requests == [("GET", f"/v2/invoicing/invoices/{iid}", None)]
    assert_closed(agent, mock, iid)


def test_delayed_event_preserves_current_review_and_only_human_approval_sends_exact_text_once():
    agent, mock, _, (iid,) = case()
    old = mock.simulate_payer_payment(iid, Decimal("100"))
    mock.simulate_payer_payment(iid, Decimal("200"))
    aid = queue(agent, iid)  # Owner refresh already reviewed the current GBP 500.
    reviewed = copy.deepcopy(agent.pending[aid].payload)
    assert "GBP 500" in reviewed["note"]
    mock.requests.clear()

    deliver(agent, mock, old)

    assert agent.ledger[iid].paid_amount == Decimal("300")
    assert agent.ledger[iid].balance == Decimal("500")
    assert agent.pending[aid].status == "PENDING"
    assert agent.pending[aid].payload == reviewed
    assert mock.requests == [("GET", f"/v2/invoicing/invoices/{iid}", None)]
    assert_closed(agent, mock, iid)
    assert agent.approve(aid)["reminded"] is True
    sent = outgoing(mock)
    assert len(sent) == 1 and sent[0][1].endswith("/remind")
    assert sent[0][2]["subject"] == reviewed["subject"]
    assert sent[0][2]["note"] == reviewed["note"]
    with pytest.raises(ValueError):
        agent.approve(aid)
    assert len(outgoing(mock)) == 1


@pytest.mark.parametrize("term", [
    {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "2026-12-05"},
    {"term_type": "NO_DUE_DATE"},
])
def test_current_provider_edits_and_due_date_are_applied_only_to_notified_invoice(term):
    agent, mock, _, (iid, other) = case(2)
    aid, other_aid = queue(agent, iid), queue(agent, other)
    reviewed = copy.deepcopy(agent.pending[aid].payload)
    other_entry = copy.deepcopy(vars(agent.ledger[other]))
    other_review = agent.pending[other_aid].to_dict()
    old = updated(mock, iid)
    inv = mock.invoices[iid]
    inv["detail"]["invoice_number"] = "CURRENT-0042"
    inv["detail"]["currency_code"] = "EUR"
    inv["detail"]["payment_term"] = copy.deepcopy(term)
    inv["amount"] = {"currency_code": "EUR", "value": "500.00"}
    inv["due_amount"] = {"currency_code": "EUR", "value": "500.00"}
    inv["payments"]["paid_amount"] = {"currency_code": "EUR", "value": "0.00"}
    for item in inv["items"]:
        item["unit_amount"] = {"currency_code": "EUR", "value": "25.00"}
    inv["primary_recipients"][0]["billing_info"].update({
        "email_address": "current-recipient@example.invalid",
        "name": {"given_name": "Current", "surname": "Recipient"},
    })
    mock.requests.clear()

    deliver(agent, mock, old)

    entry = agent.ledger[iid]
    assert (entry.currency, entry.total, entry.invoice_number) == ("EUR", Decimal("500"), "CURRENT-0042")
    assert (entry.client_name, entry.client_email) == ("Current Recipient", "current-recipient@example.invalid")
    expected_due = date(2026, 12, 5) if "due_date" in term else None
    assert entry.due_on == expected_due
    assert agent.pending[aid].status == "REJECTED"
    assert agent.pending[aid].payload == reviewed
    assert vars(agent.ledger[other]) == other_entry
    assert agent.pending[other_aid].to_dict() == other_review
    assert mock.requests == [("GET", f"/v2/invoicing/invoices/{iid}", None)]
    assert agent.tool_send_reminder(iid)["ok"] is False
    assert_closed(agent, mock, iid)


@pytest.mark.parametrize("fault", ["outage", "wrong-invoice", "missing-due", "nonfinite-total", "incoherent-due"])
def test_failed_current_read_does_not_mutate_or_consume_event_and_can_retry_same_notification(fault):
    agent, mock, _, (iid,) = case()
    aid = queue(agent, iid)
    event = updated(mock, iid)
    before = state(agent)
    original_get = mock.get_invoice

    def bad_read(invoice_id):
        response = original_get(invoice_id)
        if fault == "outage":
            raise PayPalError(503, "UNAVAILABLE", "Independent receiving read outage")
        if fault == "wrong-invoice":
            response.body["id"] = "INV2-OTHER"
        elif fault == "missing-due":
            response.body.pop("due_amount")
        elif fault == "nonfinite-total":
            response.body["amount"]["value"] = "Infinity"
        elif fault == "incoherent-due":
            response.body["due_amount"]["value"] = "799.00"
        return response

    mock.requests.clear()
    with patch.object(mock, "get_invoice", side_effect=bad_read):
        with pytest.raises((PayPalError, ValueError)):
            deliver(agent, mock, event)
    assert state(agent) == before
    assert agent.pending[aid].status == "PENDING"
    assert event["id"] not in agent._seen_events
    assert_closed(agent, mock, iid)
    mock.requests.clear()

    result = deliver(agent, mock, event)
    assert result["ok"] and not result.get("duplicate", False)
    assert state(agent) == before
    assert mock.requests == [("GET", f"/v2/invoicing/invoices/{iid}", None)]
    mock.requests.clear()
    assert deliver(agent, mock, event)["duplicate"] is True
    assert mock.requests == []


def test_unknown_local_invoice_remains_retryable_after_local_registration_without_early_provider_read():
    agent, mock, _, (iid,) = case()
    event = updated(mock, iid)
    entry = agent.ledger.pop(iid)
    mock.requests.clear()
    try:
        result = deliver(agent, mock, event)
        assert result["ok"] is False and result["message"] == "unknown invoice"
        assert mock.requests == []
        assert event["id"] not in agent._seen_events
    finally:
        agent.ledger[iid] = entry

    result = deliver(agent, mock, event)
    assert result["ok"] and not result.get("duplicate", False)
    assert mock.requests == [("GET", f"/v2/invoicing/invoices/{iid}", None)]
    assert_closed(agent, mock, iid)


def test_verified_reencoded_duplicate_preserves_state_without_second_current_read():
    agent, mock, _, (iid,) = case()
    queue(agent, iid)
    event = updated(mock, iid)
    deliver(agent, mock, event, separators=(",", ":"))
    before = state(agent)
    mock.requests.clear()
    with patch.object(mock, "get_invoice", side_effect=AssertionError("duplicate must not reread")):
        result = deliver(agent, mock, event, sort_keys=True, indent=2)
    assert result["ok"] and result["duplicate"] is True
    assert state(agent) == before
    assert mock.requests == []
    assert_closed(agent, mock, iid)


@pytest.mark.parametrize("change", ["invoice-rebind", "paid-snapshot", "envelope"])
def test_accepted_event_id_cannot_be_reused_for_changed_content_or_another_invoice(change):
    agent, mock, _, (iid, other) = case(2)
    queue(agent, iid)
    queue(agent, other)
    event = updated(mock, iid)
    deliver(agent, mock, event)
    before = state(agent)
    conflict = copy.deepcopy(event)
    if change == "invoice-rebind":
        event_invoice(conflict)["id"] = other
    elif change == "paid-snapshot":
        event_invoice(conflict)["status"] = "PARTIALLY_PAID"
        event_invoice(conflict)["payments"]["paid_amount"]["value"] = "100.00"
        event_invoice(conflict)["due_amount"]["value"] = "700.00"
    else:
        conflict["create_time"] = "2026-11-09T00:00:00Z"
    mock.requests.clear()

    with pytest.raises(WebhookError):
        deliver(agent, mock, conflict)

    assert state(agent) == before
    assert mock.requests == []
    assert_closed(agent, mock, iid)
    assert deliver(agent, mock, event)["duplicate"] is True


def test_duplicate_never_bypasses_signature_verification():
    agent, mock, _, (iid,) = case()
    queue(agent, iid)
    event = updated(mock, iid)
    raw = json.dumps(event).encode()
    agent.handle_webhook(raw, mock.sign(raw))
    before = state(agent)
    headers = mock.sign(raw)
    headers["PAYPAL-TRANSMISSION-SIG"] = "independent-invalid-signature"
    mock.requests.clear()
    with pytest.raises(WebhookError):
        agent.handle_webhook(raw, headers)
    assert state(agent) == before
    assert mock.requests == []
    assert_closed(agent, mock, iid)
    assert agent.handle_webhook(raw, mock.sign(raw))["duplicate"] is True


@pytest.mark.parametrize("field,value", [
    ("event", ""), ("event", "  "), ("event", True), ("event", ["WH-X"]),
    ("invoice", True), ("invoice", ["INV-X"]), ("invoice", " INV-X "),
])
def test_noncanonical_identity_is_refused_before_read_or_state_change(field, value):
    agent, mock, _, (iid,) = case()
    queue(agent, iid)
    event = updated(mock, iid)
    if field == "event":
        event["id"] = value
    else:
        event_invoice(event)["id"] = value
    before = state(agent)
    mock.requests.clear()
    with pytest.raises(WebhookError):
        deliver(agent, mock, event)
    assert state(agent) == before
    assert mock.requests == []
    assert_closed(agent, mock, iid)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_json_metadata_is_refused_without_consuming_a_known_notification(number):
    agent, mock, _, (iid,) = case()
    queue(agent, iid)
    event = updated(mock, iid)
    event["metadata"] = {"unrepresentable": number}
    before = state(agent)
    mock.requests.clear()
    with pytest.raises(WebhookError):
        deliver(agent, mock, event)
    assert state(agent) == before
    assert event["id"] not in agent._seen_events
    assert mock.requests == []
    assert_closed(agent, mock, iid)


def test_new_notification_keeps_owner_review_date_invalidation_and_retains_reviewed_words():
    agent, mock, clock, (iid,) = case()
    aid = queue(agent, iid)
    reviewed = copy.deepcopy(agent.pending[aid].payload)
    event = updated(mock, iid)
    clock.day += timedelta(days=1)
    mock.requests.clear()

    deliver(agent, mock, event)

    assert agent.pending[aid].status == "REJECTED"
    assert agent.pending[aid].payload == reviewed
    with pytest.raises(ValueError):
        agent.approve(aid)
    assert_closed(agent, mock, iid)
    fresh = queue(agent, iid)
    assert fresh != aid
    assert "11 days" in agent.pending[fresh].payload["subject"]
