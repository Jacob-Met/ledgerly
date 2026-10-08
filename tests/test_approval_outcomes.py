"""Unknown outgoing outcomes must not make the same approval replayable."""
from datetime import datetime, time, timezone
from decimal import Decimal
from urllib.error import URLError
import json

import pytest

from conftest import INVOICER, load
from ledgerly.agent import Agent, ApprovalRequired
from ledgerly.paypal import PayPalError, Response, SandboxMock


class InterruptedMock(SandboxMock):
    """Inject a response fault around real, observable SandboxMock operations."""

    def __init__(self, clock):
        super().__init__(now=lambda: datetime.combine(clock(), time.min, tzinfo=timezone.utc))
        self.phase = None
        self.error = None

    def fail(self, phase, error):
        self.phase, self.error = phase, error

    def _raise_at(self, phase):
        if self.phase == phase:
            self.phase = None
            raise self.error

    def send_invoice(self, invoice_id, body=None):
        self._raise_at("before_send")
        result = super().send_invoice(invoice_id, body)
        self._raise_at("after_send")
        if self.phase == "malformed_send":
            self.phase = None
            return Response(200, None)
        return result

    def remind_invoice(self, invoice_id, body=None):
        result = super().remind_invoice(invoice_id, body)
        self._raise_at("after_reminder")
        return result

    def record_payment(self, invoice_id, body):
        result = super().record_payment(invoice_id, body)
        self._raise_at("after_payment")
        if self.phase == "after_deposit_status":
            self.phase = "read"
        return result

    def get_invoice(self, invoice_id):
        result = super().get_invoice(invoice_id)
        self._raise_at("read")
        return result


def setup_invoice(clock, fixture="01_simple_usd_hourly.txt"):
    mock = InterruptedMock(clock)
    agent = Agent(mock, INVOICER, today=clock)
    created = agent.tool_create_invoice(load(fixture))
    assert created["ok"], created
    return agent, mock, created["invoices"][0]


def queue_reminder(agent, invoice, clock):
    agent.approve(invoice["approval_id"])
    clock.d = clock.d.replace(day=20)
    drafted = agent.tool_send_reminder(invoice["invoice_id"])
    assert drafted["ok"], drafted
    return drafted["approval_id"]


def outgoing(mock, suffix):
    return [request for request in mock.requests if request[1].endswith(suffix)]


def assert_consumed(agent, mock, action_id, error_type):
    action = agent.pending[action_id]
    assert action.status == "FAILED"
    assert action.result["outcome"] == "UNKNOWN"
    assert action.result["error_type"] == error_type
    assert "Check the invoice" in action.result["reason"]
    assert all(row["id"] != action_id for row in agent.list_pending())
    event = json.loads(agent.export_state())["audit"][-1]
    assert event["event"] == "approve_failed"
    assert event["action"] == action_id
    assert event["outcome"] == "UNKNOWN"
    assert event["reason"] == action.result["reason"]

    before_retry = list(mock.requests)
    with pytest.raises(ValueError, match="already FAILED.*Check the invoice"):
        agent.approve(action_id)
    assert mock.requests == before_retry  # Even another preflight GET is unnecessary.

    invoice_id = action.invoice_id
    for call in (
        lambda: agent.client.send_invoice(invoice_id),
        lambda: agent.client.remind_invoice(invoice_id),
        lambda: agent.client.record_payment(invoice_id, {"amount": {"currency_code": "USD", "value": "1"}}),
    ):
        with pytest.raises(ApprovalRequired):
            call()
    assert mock.requests == before_retry


@pytest.mark.parametrize("error", [
    TimeoutError("authored lost reminder response"),
    URLError("authored transport response failure"),
    json.JSONDecodeError("authored malformed response", "?", 0),
], ids=["timeout", "transport", "decode"])
def test_completed_reminder_with_lost_response_cannot_replay(clock, error):
    agent, mock, invoice = setup_invoice(clock)
    action_id = queue_reminder(agent, invoice, clock)
    mock.fail("after_reminder", error)

    with pytest.raises(type(error)) as caught:
        agent.approve(action_id)
    assert caught.value is error
    assert len(outgoing(mock, "/remind")) == 1
    assert agent.ledger[invoice["invoice_id"]].reminders_sent == 0
    assert_consumed(agent, mock, action_id, type(error).__name__)


@pytest.mark.parametrize("phase,expected_posts", [
    ("before_send", 0), ("after_send", 1),
])
def test_send_transport_failure_conservatively_consumes_approval(clock, phase, expected_posts):
    agent, mock, invoice = setup_invoice(clock)
    error = URLError("authored send transport interruption")
    mock.fail(phase, error)

    with pytest.raises(URLError) as caught:
        agent.approve(invoice["approval_id"])
    assert caught.value is error
    assert len(outgoing(mock, "/send")) == expected_posts
    assert_consumed(agent, mock, invoice["approval_id"], "URLError")


def test_malformed_success_response_after_send_does_not_reopen_approval(clock):
    agent, mock, invoice = setup_invoice(clock)
    mock.fail("malformed_send", None)

    with pytest.raises(AttributeError):
        agent.approve(invoice["approval_id"])
    assert mock.invoices[invoice["invoice_id"]]["status"] == "SENT"
    assert len(outgoing(mock, "/send")) == 1
    assert_consumed(agent, mock, invoice["approval_id"], "AttributeError")


@pytest.mark.parametrize("phase", ["after_payment", "after_deposit_status"])
def test_partial_send_sequence_cannot_replay_after_recorded_deposit(clock, phase):
    agent, mock, invoice = setup_invoice(clock, "07_partial_payment_deposit.txt")
    error = TimeoutError("authored response loss after deposit")
    mock.fail(phase, error)

    with pytest.raises(TimeoutError) as caught:
        agent.approve(invoice["approval_id"])
    assert caught.value is error
    provider = mock.invoices[invoice["invoice_id"]]
    assert provider["status"] == "PARTIALLY_PAID"
    assert Decimal(provider["payments"]["paid_amount"]["value"]) == Decimal("1000")
    assert len(provider["payments"]["transactions"]) == 1
    assert len(outgoing(mock, "/send")) == 1
    assert len(outgoing(mock, "/payments")) == 1
    assert_consumed(agent, mock, invoice["approval_id"], "TimeoutError")


@pytest.mark.parametrize("error", [
    TimeoutError("authored read timeout"),
    URLError("authored read transport failure"),
], ids=["timeout", "transport"])
def test_read_only_reminder_preflight_can_retry_same_id(clock, error):
    agent, mock, invoice = setup_invoice(clock)
    action_id = queue_reminder(agent, invoice, clock)
    before = agent.pending[action_id].to_dict()
    audit_count = len(agent.audit)
    mock.fail("read", error)

    with pytest.raises(type(error)) as caught:
        agent.approve(action_id)
    assert caught.value is error
    assert agent.pending[action_id].to_dict() == before
    assert len(agent.audit) == audit_count
    assert outgoing(mock, "/remind") == []
    assert [row["id"] for row in agent.list_pending()] == [action_id]

    assert agent.approve(action_id) == {"reminded": True}
    assert agent.pending[action_id].status == "APPROVED"
    assert len(outgoing(mock, "/remind")) == 1


def test_existing_paypal_refusal_retains_body_and_failure_audit(clock):
    agent, mock, invoice = setup_invoice(clock)
    # A provider-side status change makes the real mock reject the send.
    mock.invoices[invoice["invoice_id"]]["status"] = "CANCELLED"
    with pytest.raises(PayPalError) as caught:
        agent.approve(invoice["approval_id"])
    action = agent.pending[invoice["approval_id"]]
    assert action.status == "FAILED"
    assert action.result is caught.value.body
    assert action.result["name"] == "UNPROCESSABLE_ENTITY"
    assert "outcome" not in action.result
    assert agent.audit[-1]["event"] == "approve_failed"
    assert agent.audit[-1]["error"] == str(caught.value)
    before_retry = list(mock.requests)
    with pytest.raises(ValueError, match="already FAILED"):
        agent.approve(action.id)
    with pytest.raises(ApprovalRequired):
        agent.client.send_invoice(invoice["invoice_id"])
    assert mock.requests == before_retry
