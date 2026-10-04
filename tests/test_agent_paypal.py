import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from conftest import INVOICER, load
from ledgerly.agent import Agent, ApprovalRequired, RulePlanner
from ledgerly.paypal import (
    PayPalError, SandboxMock, WebhookError, build_invoice, parse_webhook_event,
)
from ledgerly.extract import RulesExtractor


def sends(mock):
    return [r for r in mock.requests if r[1].endswith(("/send", "/remind", "/payments"))]


def create(agent, fixture):
    res = agent.tool_create_invoice(load(fixture))
    assert res["ok"], res
    return res["invoices"]


# ---------------- request shapes

def test_build_invoice_shape_matches_invoicing_v2():
    ex = RulesExtractor().extract(load("01_simple_usd_hourly.txt"))
    body = build_invoice(ex, INVOICER, "LDG-0001", date(2026, 10, 1))
    assert body["detail"]["currency_code"] == "USD"
    assert body["detail"]["payment_term"] == {"term_type": "NET_15", "due_date": "2026-10-16"}
    assert body["primary_recipients"][0]["billing_info"] == {
        "name": {"given_name": "Maya", "surname": "Chen"}, "email_address": "maya.chen@brightfern.example"}
    assert body["items"][0] == {"name": "Copywriting", "quantity": "12",
                                "unit_amount": {"currency_code": "USD", "value": "85.00"},
                                "unit_of_measure": "HOURS"}


def test_jpy_amounts_have_no_decimals():
    ex = RulesExtractor().extract(load("08_jpy_zero_decimal.txt"))
    body = build_invoice(ex, INVOICER, "N", date(2026, 10, 1))
    assert body["items"][0]["unit_amount"] == {"currency_code": "JPY", "value": "6000"}


def test_mock_create_returns_link_and_draft_status(mock):
    ex = RulesExtractor().extract(load("02_gbp_proofreading.txt"))
    r = mock.create_draft_invoice(build_invoice(ex, INVOICER, "N1", date(2026, 10, 1)))
    assert r.status == 201 and r.body["rel"] == "self" and "/v2/invoicing/invoices/INV2-" in r.body["href"]
    inv = mock.get_invoice(r.body["href"].rsplit("/", 1)[-1]).body
    assert inv["status"] == "DRAFT"
    assert inv["amount"]["value"] == "800.00" and inv["due_amount"]["value"] == "800.00"


def test_mock_rejects_unknown_invoice(mock):
    with pytest.raises(PayPalError) as e:
        mock.get_invoice("INV2-NOPE")
    assert e.value.http_status == 404 and e.value.body["name"] == "RESOURCE_NOT_FOUND"


def test_mock_cannot_send_twice(mock):
    ex = RulesExtractor().extract(load("01_simple_usd_hourly.txt"))
    iid = mock.create_draft_invoice(build_invoice(ex, INVOICER, "N", date(2026, 10, 1)), True).body["id"]
    mock.send_invoice(iid)
    with pytest.raises(PayPalError) as e:
        mock.send_invoice(iid)
    assert e.value.http_status == 422


# ---------------- approval gate

def test_create_invoice_does_not_send(agent, mock):
    invs = create(agent, "01_simple_usd_hourly.txt")
    assert sends(mock) == []
    assert mock.get_invoice(invs[0]["invoice_id"]).body["status"] == "DRAFT"
    assert len(agent.list_pending()) == 1


def test_gated_client_blocks_send_without_approval(agent, mock):
    iid = create(agent, "01_simple_usd_hourly.txt")[0]["invoice_id"]
    for call in (lambda: agent.client.send_invoice(iid),
                 lambda: agent.client.remind_invoice(iid),
                 lambda: agent.client.record_payment(iid, {"amount": {"currency_code": "USD", "value": "1"}})):
        with pytest.raises(ApprovalRequired):
            call()
    assert sends(mock) == []
    assert len(agent.client.blocked) == 3


def test_approve_sends_exactly_once(agent, mock):
    inv = create(agent, "01_simple_usd_hourly.txt")[0]
    agent.approve(inv["approval_id"])
    assert [r[1] for r in sends(mock)] == [f"/v2/invoicing/invoices/{inv['invoice_id']}/send"]
    assert mock.get_invoice(inv["invoice_id"]).body["status"] == "SENT"
    with pytest.raises(ValueError):
        agent.approve(inv["approval_id"])  # one-shot
    with pytest.raises(ApprovalRequired):
        agent.client.send_invoice(inv["invoice_id"])  # permit closed again


def test_reject_never_sends(agent, mock):
    inv = create(agent, "02_gbp_proofreading.txt")[0]
    agent.reject(inv["approval_id"], "wrong rate")
    assert sends(mock) == [] and agent.list_pending() == []


def test_planner_cannot_call_approve_or_send(agent, mock):
    create(agent, "01_simple_usd_hourly.txt")

    class Evil:
        def __init__(self):
            self.n = 0

        def next_step(self, goal, history, tools):
            self.n += 1
            steps = [{"tool": "approve", "args": {"action_id": "x"}},
                     {"tool": "send_invoice", "args": {"invoice_id": "x"}},
                     {"tool": "_queue", "args": {}}]
            return steps[self.n - 1] if self.n <= len(steps) else {"final": "done"}

    out = agent.run("anything", Evil())
    msgs = [h["result"]["message"] for h in out["history"] if h["role"] == "tool"]
    assert all("unknown or forbidden tool" in m for m in msgs)
    assert sends(mock) == []


def test_prompt_injection_email_still_requires_approval(agent, mock):
    out = agent.run("invoice:" + load("12_prompt_injection.txt"), RulePlanner())
    assert sends(mock) == []
    pend = agent.list_pending()
    assert len(pend) == 1 and pend[0]["kind"] == "send_invoice"
    assert "victor@quickflip.example" in pend[0]["summary"] and "refund" not in pend[0]["summary"].lower()
    assert "awaiting approval" in out["final"]


def test_low_confidence_needs_review_creates_nothing(agent, mock):
    for f in ("05_missing_email.txt", "06_ambiguous_qty.txt"):
        res = agent.tool_create_invoice(load(f))
        assert res["ok"] is False and res["needs_review"]
    assert mock.invoices == {} and agent.list_pending() == []


def test_multi_currency_creates_two_drafts_two_approvals(agent, mock):
    invs = create(agent, "04_multi_currency.txt")
    assert sorted((i["currency"], i["total"]) for i in invs) == [("EUR", "360"), ("USD", "1900")]
    assert len(agent.list_pending()) == 2 and sends(mock) == []


def test_partial_payment_deposit_recorded_only_after_approval(agent, mock):
    inv = create(agent, "07_partial_payment_deposit.txt")[0]
    assert sends(mock) == []
    assert "deposit" in agent.list_pending()[0]["summary"]
    res = agent.approve(inv["approval_id"])
    assert "deposit_payment_id" in res
    body = mock.get_invoice(inv["invoice_id"]).body
    assert body["status"] == "PARTIALLY_PAID"
    assert body["due_amount"]["value"] == "2500.00"
    assert body["configuration"]["partial_payment"]["allow_partial_payment"] is True


# ---------------- webhooks

def _sent(agent, fixture):
    inv = create(agent, fixture)[0]
    agent.approve(inv["approval_id"])
    return inv["invoice_id"]


def test_webhook_paid_transition(agent, mock):
    iid = _sent(agent, "01_simple_usd_hourly.txt")
    event = mock.simulate_payer_payment(iid)
    assert event["event_type"] == "INVOICING.INVOICE.PAID"
    res = agent.handle_webhook(json.dumps(event).encode())
    assert res == {"ok": True, "invoice_id": iid, "from": "SENT", "to": "PAID"}
    assert agent.ledger[iid].balance == 0
    assert agent.tool_get_status(iid)["status"] == "PAID"


def test_webhook_partial_then_full(agent, mock):
    iid = _sent(agent, "02_gbp_proofreading.txt")
    ev1 = mock.simulate_payer_payment(iid, Decimal("300"))
    assert agent.handle_webhook(json.dumps(ev1).encode())["to"] == "PARTIALLY_PAID"
    assert agent.ledger[iid].balance == Decimal("500")
    ev2 = mock.simulate_payer_payment(iid)
    assert agent.handle_webhook(json.dumps(ev2).encode())["to"] == "PAID"


def test_webhook_duplicate_is_idempotent(agent, mock):
    iid = _sent(agent, "01_simple_usd_hourly.txt")
    raw = json.dumps(mock.simulate_payer_payment(iid)).encode()
    agent.handle_webhook(raw)
    assert agent.handle_webhook(raw)["duplicate"] is True


def test_webhook_signature_verification(mock, clock):
    agent = Agent(mock, INVOICER, today=clock, webhook_verifier=mock.verify_webhook_signature)
    iid = _sent(agent, "01_simple_usd_hourly.txt")
    raw = json.dumps(mock.simulate_payer_payment(iid)).encode()
    headers = mock.sign(raw)
    tampered = raw.replace(b'"PAID"', b'"PAID" ', 1)
    with pytest.raises(WebhookError):
        agent.handle_webhook(tampered, headers)
    assert agent.ledger[iid].status == "SENT"
    assert agent.handle_webhook(raw, headers)["to"] == "PAID"


@pytest.mark.parametrize("bad", [
    b"not json",
    json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}}).encode(),
    json.dumps({"event_type": "INVOICING.INVOICE.PAID", "resource": {"invoice": {"status": "PAID"}}}).encode(),
    json.dumps({"event_type": "INVOICING.INVOICE.PAID", "resource": {"invoice": {"id": "X", "status": "SENT"}}}).encode(),
])
def test_webhook_parser_rejects_bad_events(bad):
    with pytest.raises(WebhookError):
        parse_webhook_event(bad)


# ---------------- overdue reminders

def test_overdue_reminder_drafted_queued_and_gated(agent, mock, clock):
    iid = _sent(agent, "01_simple_usd_hourly.txt")  # Net 15 from 2026-10-01 -> due 10-16
    clock.d = date(2026, 10, 16)
    assert agent.tool_list_overdue()["overdue"] == []
    assert agent.tool_send_reminder(iid)["ok"] is False

    clock.d = date(2026, 10, 20)
    out = agent.run("chase", RulePlanner())
    tool_results = [h["result"] for h in out["history"] if h["role"] == "tool"]
    assert tool_results[0]["overdue"][0]["days_overdue"] == 4
    draft = tool_results[1]["draft"]
    assert draft["tone"] == "friendly" and "Hi Maya" in draft["note"] and "USD 1,320" in draft["note"]
    assert not any(r[1].endswith("/remind") for r in mock.requests)  # gated

    pend = [a for a in agent.list_pending() if a["kind"] == "send_reminder"]
    agent.approve(pend[0]["id"])
    reminds = [r for r in mock.requests if r[1].endswith("/remind")]
    assert len(reminds) == 1 and reminds[0][2]["subject"].startswith("Friendly reminder")
    assert agent.ledger[iid].reminders_sent == 1

    clock.d = date(2026, 10, 23)  # cooldown
    assert "cooling down" in agent.tool_send_reminder(iid)["message"]


@pytest.mark.parametrize("days_late,tone", [(3, "friendly"), (15, "firm"), (45, "final")])
def test_reminder_tone_escalates(agent, clock, days_late, tone):
    iid = _sent(agent, "02_gbp_proofreading.txt")  # Net 30 -> due 10-31
    clock.d = date(2026, 10, 31) + timedelta(days=days_late)
    assert agent.tool_send_reminder(iid)["draft"]["tone"] == tone


def test_reminder_mentions_partial_balance(agent, mock, clock):
    iid = _sent(agent, "02_gbp_proofreading.txt")
    agent.handle_webhook(json.dumps(mock.simulate_payer_payment(iid, Decimal("300"))).encode())
    clock.d = date(2026, 11, 10)
    note = agent.tool_send_reminder(iid)["draft"]["note"]
    assert "GBP 300" in note and "GBP 500" in note


def test_paid_invoice_gets_no_reminder_and_pending_reminder_is_cancelled(agent, mock, clock):
    iid = _sent(agent, "01_simple_usd_hourly.txt")
    clock.d = date(2026, 10, 25)
    rid = agent.tool_send_reminder(iid)["approval_id"]
    agent.handle_webhook(json.dumps(mock.simulate_payer_payment(iid)).encode())
    assert agent.pending[rid].status == "REJECTED"
    assert agent.tool_send_reminder(iid)["ok"] is False
    assert agent.tool_list_overdue()["overdue"] == []
    assert not any(r[1].endswith("/remind") for r in mock.requests)


def test_network_client_refuses_without_opt_in(monkeypatch):
    from ledgerly.paypal import HttpPayPalClient
    monkeypatch.delenv("LEDGERLY_ALLOW_NETWORK", raising=False)
    with pytest.raises(RuntimeError):
        HttpPayPalClient("id", "secret")
