"""Webhook admission must retain current invoice facts across replay and retry.

These twelve regression cases were reproduced against the exact merged reminder
implementation before changing webhook admission. All effects use SandboxMock.
"""


import copy


import json


from datetime import date


from decimal import Decimal


import pytest


from conftest import load


from ledgerly.paypal import PayPalError, WebhookError


def sent(agent):
    invoice = agent.tool_create_invoice(load("02_gbp_proofreading.txt"))["invoices"][0]
    agent.approve(invoice["approval_id"])
    return invoice["invoice_id"]


def outgoing(mock):
    return [request for request in mock.requests if request[1].endswith(("/send", "/remind", "/payments"))]


def deliver(agent, mock, event, **json_options):
    agent.webhook_verifier = mock.verify_webhook_signature
    raw = json.dumps(event, **json_options).encode("utf-8")
    return agent.handle_webhook(raw, mock.sign(raw))


def pending_reminder(agent, clock, invoice_id):
    clock.d = date(2026, 11, 10)
    result = agent.tool_send_reminder(invoice_id)
    assert result["ok"], result
    return agent.pending[result["approval_id"]]


def test_delayed_partial_payment_cannot_reopen_a_currently_paid_invoice(agent, mock, clock):
    invoice_id = sent(agent)
    older_partial = mock.simulate_payer_payment(invoice_id, Decimal("300"))
    newer_paid = mock.simulate_payer_payment(invoice_id)
    before = copy.deepcopy(outgoing(mock))

    assert deliver(agent, mock, newer_paid)["to"] == "PAID"
    result = deliver(agent, mock, older_partial)

    assert result == {"ok": True, "invoice_id": invoice_id, "from": "PAID", "to": "PAID"}
    assert agent.ledger[invoice_id].paid_amount == Decimal("800")
    assert agent.ledger[invoice_id].balance == 0
    clock.d = date(2026, 11, 10)
    assert agent.tool_list_overdue()["overdue"] == []
    assert agent.tool_send_reminder(invoice_id)["ok"] is False
    assert outgoing(mock) == before


def test_fresh_refund_state_is_preserved_when_an_older_paid_event_arrives(agent, mock):
    invoice_id = sent(agent)
    older_paid = mock.simulate_payer_payment(invoice_id)
    mock.invoices[invoice_id]["status"] = "REFUNDED"
    current_refund = mock.make_webhook_event("INVOICING.INVOICE.REFUNDED", invoice_id)

    assert deliver(agent, mock, current_refund)["to"] == "REFUNDED"
    assert deliver(agent, mock, older_paid)["to"] == "REFUNDED"
    assert agent.ledger[invoice_id].status == "REFUNDED"


def test_failed_current_read_does_not_consume_the_original_webhook(agent, mock, clock, monkeypatch):
    invoice_id = sent(agent)
    old = pending_reminder(agent, clock, invoice_id)
    event = mock.simulate_payer_payment(invoice_id)
    entry_before = agent.ledger[invoice_id].to_dict()
    action_before = copy.deepcopy(old.to_dict())
    effects_before = copy.deepcopy(outgoing(mock))
    original_get = mock.get_invoice

    def unavailable(_):
        raise PayPalError(503, "SERVICE_UNAVAILABLE", "Fixture current-state read failed")

    monkeypatch.setattr(mock, "get_invoice", unavailable)
    with pytest.raises(PayPalError):
        deliver(agent, mock, event)
    assert agent.ledger[invoice_id].to_dict() == entry_before
    assert old.to_dict() == action_before
    assert outgoing(mock) == effects_before

    monkeypatch.setattr(mock, "get_invoice", original_get)
    result = deliver(agent, mock, event)
    assert result["to"] == "PAID" and not result.get("duplicate")
    assert old.status == "REJECTED"
    assert deliver(agent, mock, event)["duplicate"] is True


def test_unknown_invoice_notification_can_be_received_after_local_invoice_arrives(agent, mock):
    invoice_id = sent(agent)
    event = mock.simulate_payer_payment(invoice_id)
    retained_entry = agent.ledger.pop(invoice_id)
    assert deliver(agent, mock, event)["ok"] is False

    agent.ledger[invoice_id] = retained_entry
    result = deliver(agent, mock, event)

    assert result.get("to") == "PAID" and not result.get("duplicate")
    assert retained_entry.balance == 0


def test_event_id_replays_match_content_and_conflicting_payload_is_not_a_duplicate(agent, mock):
    invoice_id = sent(agent)
    event = mock.simulate_payer_payment(invoice_id)
    deliver(agent, mock, event)
    reads_before = len([request for request in mock.requests if request[0] == "GET"])

    assert deliver(agent, mock, event, indent=2, sort_keys=True)["duplicate"] is True
    assert len([request for request in mock.requests if request[0] == "GET"]) == reads_before
    changed = copy.deepcopy(event)
    changed["summary"] = "Different content under the already processed event ID"
    with pytest.raises(WebhookError, match="identity"):
        deliver(agent, mock, changed)
    assert agent.ledger[invoice_id].status == "PAID"
    assert len([request for request in mock.requests if request[0] == "GET"]) == reads_before


@pytest.mark.parametrize("event_id", [None, "", " ", " WH-LEADING", "WH-TRAILING ", 7, ["WH-LIST"]])
def test_invalid_event_identity_is_rejected_before_current_read(agent, mock, event_id):
    invoice_id = sent(agent)
    event = mock.simulate_payer_payment(invoice_id)
    event["id"] = event_id
    before = agent.ledger[invoice_id].to_dict()
    reads_before = len([request for request in mock.requests if request[0] == "GET"])

    with pytest.raises(WebhookError, match="event ID"):
        deliver(agent, mock, event)

    assert agent.ledger[invoice_id].to_dict() == before
    assert len([request for request in mock.requests if request[0] == "GET"]) == reads_before
