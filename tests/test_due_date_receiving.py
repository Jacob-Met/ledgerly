"""Keep positive-term invoice deadlines stable while a draft awaits approval."""

from datetime import date
from decimal import Decimal

import pytest

from conftest import load
from ledgerly.agent import LedgerEntry, RulePlanner
from ledgerly.extract import RulesExtractor


def draft_with_terms(agent, days):
    text = load("01_simple_usd_hourly.txt").replace("Net 15", f"Net {days}")
    result = agent.tool_create_invoice(text)
    assert result["ok"], result
    assert len(result["invoices"]) == 1
    return result["invoices"][0]


@pytest.mark.parametrize(
    "days,drafted_on,approved_on,expected_due",
    [
        (15, "2026-10-01", "2026-10-08", "2026-10-16"),
        # Net 12 becomes DUE_ON_DATE_SPECIFIED in the existing provider builder.
        (12, "2026-10-01", "2026-10-08", "2026-10-13"),
        (12, "2026-01-25", "2026-02-02", "2026-02-06"),
        (12, "2026-12-25", "2027-01-02", "2027-01-06"),
        (12, "2028-02-20", "2028-02-27", "2028-03-03"),
        (12, "2027-02-20", "2027-02-27", "2027-03-04"),
        (15, "2026-10-01", "2026-10-01", "2026-10-16"),
        (12, "2026-10-01", "2026-10-20", "2026-10-13"),
    ],
    ids=[
        "delayed-net-15", "delayed-specified-date", "month-boundary",
        "year-boundary", "leap-year", "non-leap-year", "same-day",
        "approval-after-deadline",
    ],
)
def test_approval_retains_the_positive_term_draft_deadline(
    agent, mock, clock, days, drafted_on, approved_on, expected_due,
):
    clock.d = date.fromisoformat(drafted_on)
    invoice = draft_with_terms(agent, days)
    invoice_id = invoice["invoice_id"]
    entry = agent.ledger[invoice_id]
    term = mock.get_invoice(invoice_id).body["detail"]["payment_term"]
    assert term["due_date"] == expected_due
    assert term["term_type"] == ("NET_15" if days == 15 else "DUE_ON_DATE_SPECIFIED")

    # Even an old draft cannot become overdue before the visitor sends it.
    clock.d = date.fromisoformat(approved_on)
    assert entry.due_on is None
    assert entry.to_dict()["due_on"] is None
    assert agent.tool_list_overdue()["overdue"] == []
    assert not any(path.endswith("/send") for _, path, _ in mock.requests)

    agent.approve(invoice["approval_id"])
    assert entry.sent_on == date.fromisoformat(approved_on)
    assert entry.due_on == date.fromisoformat(expected_due)
    assert entry.to_dict()["due_on"] == expected_due
    assert mock.get_invoice(invoice_id).body["detail"]["payment_term"] == term
    assert sum(path.endswith("/send") for _, path, _ in mock.requests) == 1


def test_delayed_approval_chase_uses_the_date_on_the_invoice(agent, mock, clock):
    clock.d = date(2026, 10, 1)
    invoice = draft_with_terms(agent, 12)
    clock.d = date(2026, 10, 8)
    agent.approve(invoice["approval_id"])

    clock.d = date(2026, 10, 13)
    assert agent.tool_list_overdue()["overdue"] == []
    clock.d = date(2026, 10, 14)
    overdue = agent.tool_list_overdue()["overdue"]
    assert [(row["invoice_id"], row["days_overdue"]) for row in overdue] == [
        (invoice["invoice_id"], 1),
    ]

    agent.run("chase", RulePlanner())
    reminders = [action for action in agent.list_pending() if action["kind"] == "send_reminder"]
    assert len(reminders) == 1
    reminder = reminders[0]
    assert "(1d overdue," in reminder["summary"]
    assert "was due on Oct 13, 2026" in reminder["payload"]["note"]
    assert not any(path.endswith("/remind") for _, path, _ in mock.requests)

    agent.approve(reminder["id"])
    sent = [body for _, path, body in mock.requests if path.endswith("/remind")]
    assert len(sent) == 1
    assert sent[0]["note"] == reminder["payload"]["note"]


@pytest.mark.parametrize("days", [0, None], ids=["due-on-receipt", "no-due-date"])
def test_receipt_and_missing_terms_keep_their_existing_behavior(agent, mock, clock, days):
    class TermsExtractor:
        def extract(self, text):
            extraction = RulesExtractor().extract(text)
            extraction.due_days = days
            return extraction

    agent.extractor = TermsExtractor()
    clock.d = date(2026, 10, 1)
    result = agent.tool_create_invoice(load("01_simple_usd_hourly.txt"))
    assert result["ok"], result
    invoice = result["invoices"][0]
    entry = agent.ledger[invoice["invoice_id"]]
    assert entry.due_on is None
    term = mock.get_invoice(invoice["invoice_id"]).body["detail"]["payment_term"]
    assert term["term_type"] == ("DUE_ON_RECEIPT" if days == 0 else "NO_DUE_DATE")

    clock.d = date(2026, 10, 8)
    agent.approve(invoice["approval_id"])
    assert entry.sent_on == date(2026, 10, 8)
    assert entry.due_on == (date(2026, 10, 8) if days == 0 else None)
    clock.d = date(2026, 10, 9)
    assert entry.days_overdue(clock.d) == (1 if days == 0 else 0)


def test_legacy_positional_ledger_entry_keeps_its_send_date_fallback():
    entry = LedgerEntry(
        "INV-LEGACY", "LDG-LEGACY", "Client", "client@example.test", "USD",
        Decimal("100"), 12, "SENT", date(2026, 10, 8), Decimal("10"),
        2, date(2026, 10, 7), Decimal("5"),
    )
    assert entry.paid_amount == Decimal("10")
    assert entry.reminders_sent == 2
    assert entry.last_reminder_on == date(2026, 10, 7)
    assert entry.prepaid == Decimal("5")
    assert entry.due_on == date(2026, 10, 20)
