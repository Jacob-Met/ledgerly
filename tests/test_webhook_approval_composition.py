"""Bounded receiving of PR21 webhook refresh with current PR24 approval outcomes.

The source directory is explicit. These controls use native Agent/SandboxMock only.
They preserve webhook/approval behavior during invoice-value receiving; no provider is activated.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, time, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

import pytest

SOURCE = Path(os.environ.get('LEDGERLY_SOURCE', Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(SOURCE))
from ledgerly.agent import Agent, ApprovalRequired
from ledgerly.paypal import SandboxMock


class Clock:
    day = date(2026, 10, 1)

    def __call__(self):
        return self.day


class InterruptedMock(SandboxMock):
    def __init__(self, clock):
        super().__init__(now=lambda: datetime.combine(clock(), time.min, tzinfo=timezone.utc))
        self.fail_read = False
        self.fail_reminder_response = False
        self.fail_read_after_payment = False

    def get_invoice(self, invoice_id):
        result = super().get_invoice(invoice_id)
        if self.fail_read:
            self.fail_read = False
            raise TimeoutError('receiving: unavailable current invoice read')
        return result

    def remind_invoice(self, invoice_id, body=None):
        result = super().remind_invoice(invoice_id, body)
        if self.fail_reminder_response:
            self.fail_reminder_response = False
            raise TimeoutError('receiving: completed reminder response lost')
        return result

    def record_payment(self, invoice_id, body):
        result = super().record_payment(invoice_id, body)
        if self.fail_read_after_payment:
            self.fail_read_after_payment = False
            self.fail_read = True
        return result


def case(fixture='02_gbp_proofreading.txt'):
    clock = Clock()
    mock = InterruptedMock(clock)
    agent = Agent(mock, {'name': 'Receiving', 'email_address': 'receiving@example.invalid'},
                  today=clock, webhook_verifier=mock.verify_webhook_signature)
    result = agent.tool_create_invoice((SOURCE / 'fixtures' / fixture).read_text())
    assert result['ok'], result
    return agent, mock, clock, result['invoices'][0]


def deliver(agent, mock, event):
    raw = json.dumps(event).encode('utf-8')
    return agent.handle_webhook(raw, mock.sign(raw))


def outgoing(mock, suffix):
    return [entry for entry in mock.requests if entry[1].endswith(suffix)]


def assert_consumed_without_retry(agent, mock, action_id, expected_suffix):
    action = agent.pending[action_id]
    assert action.status == 'FAILED'
    assert action.result['outcome'] == 'UNKNOWN'
    assert action.result['error_type'] == 'TimeoutError'
    before = copy.deepcopy(mock.requests)
    with pytest.raises(ValueError, match='already FAILED'):
        agent.approve(action_id)
    with pytest.raises(ApprovalRequired):
        agent.client.remind_invoice(action.invoice_id)
    assert mock.requests == before
    assert len(outgoing(mock, expected_suffix)) == 1


def test_delayed_snapshot_preserves_review_then_lost_send_response_consumes_same_id():
    agent, mock, clock, invoice = case()
    iid = invoice['invoice_id']
    agent.approve(invoice['approval_id'])
    older = mock.simulate_payer_payment(iid, Decimal('100'))
    newer = mock.simulate_payer_payment(iid, Decimal('200'))
    deliver(agent, mock, newer)
    clock.day = date(2026, 11, 10)
    action_id = agent.tool_send_reminder(iid)['approval_id']
    reviewed = copy.deepcopy(agent.pending[action_id].payload)
    assert 'GBP 500' in reviewed['note']
    deliver(agent, mock, older)
    assert agent.ledger[iid].balance == Decimal('500')
    assert agent.pending[action_id].status == 'PENDING'
    assert agent.pending[action_id].payload == reviewed
    assert outgoing(mock, '/remind') == []

    mock.fail_reminder_response = True
    with pytest.raises(TimeoutError, match='completed reminder response lost'):
        agent.approve(action_id)
    sent = outgoing(mock, '/remind')
    assert len(sent) == 1
    assert sent[0][2]['subject'] == reviewed['subject']
    assert sent[0][2]['note'] == reviewed['note']
    failed = copy.deepcopy(agent.pending[action_id].to_dict())
    assert deliver(agent, mock, older)['duplicate'] is True
    assert agent.pending[action_id].to_dict() == failed
    assert_consumed_without_retry(agent, mock, action_id, '/remind')


def test_unavailable_webhook_read_and_approval_preflight_are_separately_retryable():
    agent, mock, clock, invoice = case()
    iid = invoice['invoice_id']
    agent.approve(invoice['approval_id'])
    clock.day = date(2026, 11, 10)
    action_id = agent.tool_send_reminder(iid)['approval_id']
    reviewed = copy.deepcopy(agent.pending[action_id].to_dict())
    event = mock.make_webhook_event('INVOICING.INVOICE.UPDATED', iid)
    before = agent.export_state()
    seen = copy.deepcopy(agent._seen_events)
    mock.fail_read = True
    with pytest.raises(TimeoutError, match='current invoice read'):
        deliver(agent, mock, event)
    assert agent.export_state() == before
    assert agent._seen_events == seen
    assert outgoing(mock, '/remind') == []
    assert deliver(agent, mock, event)['ok'] is True
    assert agent.pending[action_id].to_dict() == reviewed

    before = agent.export_state()
    mock.fail_read = True
    with pytest.raises(TimeoutError, match='current invoice read'):
        agent.approve(action_id)
    assert agent.export_state() == before
    assert agent.pending[action_id].to_dict() == reviewed
    assert outgoing(mock, '/remind') == []
    assert agent.approve(action_id) == {'reminded': True}
    assert agent.pending[action_id].status == 'APPROVED'
    assert len(outgoing(mock, '/remind')) == 1
    requests = copy.deepcopy(mock.requests)
    with pytest.raises(ValueError, match='already APPROVED'):
        agent.approve(action_id)
    assert mock.requests == requests


def test_webhook_can_refresh_after_uncertain_deposit_without_reopening_send_approval():
    agent, mock, _, invoice = case('07_partial_payment_deposit.txt')
    iid, action_id = invoice['invoice_id'], invoice['approval_id']
    mock.fail_read_after_payment = True
    with pytest.raises(TimeoutError, match='current invoice read'):
        agent.approve(action_id)
    provider = mock.invoices[iid]
    assert Decimal(provider['payments']['paid_amount']['value']) == Decimal('1000')
    assert len(provider['payments']['transactions']) == 1
    assert len(outgoing(mock, '/send')) == 1
    assert len(outgoing(mock, '/payments')) == 1
    failed = copy.deepcopy(agent.pending[action_id].to_dict())

    event = mock.make_webhook_event('INVOICING.INVOICE.UPDATED', iid)
    assert deliver(agent, mock, event)['ok'] is True
    assert agent.ledger[iid].paid_amount == Decimal('1000')
    assert agent.pending[action_id].to_dict() == failed
    assert_consumed_without_retry(agent, mock, action_id, '/send')
    assert len(outgoing(mock, '/payments')) == 1
