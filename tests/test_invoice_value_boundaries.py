"""Exercise invoice values at extraction, serialization and draft receiving boundaries."""
import json
from datetime import date
from decimal import Decimal

import pytest

from ledgerly.agent import Agent
from ledgerly.extract import Extraction, LLMExtractor, RulesExtractor, validate
from ledgerly.paypal import SandboxMock, build_invoice


SOURCE = "From: Client <client@example.test>\n\n- 2 x Work @ $10\nNet 30\n"
INVOICER = {"name": "Freelancer", "email_address": "freelancer@example.test"}


def payload(**changes):
    return {
        "client_name": "Client", "client_email": "client@example.test", "currency": "USD",
        "line_items": [{"desc": "Work", "qty": "2", "unit_price": "10", "currency": "USD"}],
        "due_days": 30, "amount_paid": "0", "confidence": 1.0, **changes,
    }


def line_payload(**changes):
    return payload(line_items=[{"desc": "Work", "qty": "2", "unit_price": "10",
                                "currency": "USD", **changes}])


def draft(data, extractor=None):
    mock = SandboxMock()
    extractor = extractor or LLMExtractor(lambda _: json.dumps(data))
    agent = Agent(mock, INVOICER, extractor=extractor, today=lambda: date(2026, 10, 8))
    return agent.tool_create_invoice(SOURCE), agent, mock


@pytest.mark.parametrize("data", [
    line_payload(qty=None),
    line_payload(qty="0"),
    line_payload(qty="-1"),
    line_payload(qty="1000001"),
    line_payload(qty="0.000001"),
    line_payload(unit_price="0.015"),
    line_payload(currency="EUR"),
    line_payload(currency="XYZ"),
    payload(currency="XYZ", line_items=[{"desc": "Work", "qty": 1,
                                        "unit_price": "10", "currency": "XYZ"}]),
    payload(amount_paid="-1"),
    payload(amount_paid="0.001"),
    line_payload(qty="0.5", unit_price="0.01"),
])
def test_invalid_invoice_is_reviewable_before_any_provider_call(data):
    result, agent, mock = draft(data)
    assert result["ok"] is False and result["needs_review"] is True
    assert any(issue["severity"] == "error" for issue in result["issues"])
    assert mock.requests == []
    assert mock.invoices == {} and agent.ledger == {} and agent.list_pending() == []


@pytest.mark.parametrize("field", ["qty", "unit_price", "amount_paid"])
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_model_values_return_review_without_decimal_errors(field, value):
    data = payload(amount_paid=value) if field == "amount_paid" else line_payload(**{field: value})
    result, agent, mock = draft(data)
    assert result["ok"] is False and result["needs_review"] is True
    assert mock.requests == [] and agent.list_pending() == []


@pytest.mark.parametrize("field", ["qty", "unit_price", "amount_paid"])
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_direct_decimal_values_are_refused_by_validator_and_builder(field, value):
    ex = Extraction.from_dict(payload())
    target = ex if field == "amount_paid" else ex.line_items[0]
    setattr(target, field, Decimal(value))
    assert any(i.severity == "error" for i in validate(ex))
    with pytest.raises(ValueError):
        build_invoice(ex, INVOICER, "N", date(2026, 10, 8))


def test_custom_extractor_cannot_skip_the_core_validation_before_drafting():
    ex = Extraction.from_dict(line_payload(currency="EUR"))
    ex.confidence = 1.0

    class AlreadyReviewed:
        def extract(self, _):
            return ex

    result, agent, mock = draft({}, extractor=AlreadyReviewed())
    assert result["ok"] is False and result["needs_review"] is True
    assert mock.requests == [] and agent.list_pending() == []
    assert ex.issues == []  # admission does not mutate the custom extractor's value


@pytest.mark.parametrize("data", [line_payload(currency="EUR"), line_payload(qty=None),
                                  line_payload(unit_price="0.015"), payload(amount_paid="-1")])
def test_direct_builder_revalidates_even_when_issue_list_is_empty(data):
    ex = Extraction.from_dict(data)
    assert ex.issues == []
    with pytest.raises(ValueError):
        build_invoice(ex, INVOICER, "N", date(2026, 10, 8))


def test_rules_keep_the_entire_price_instead_of_truncating_at_two_decimals():
    source = SOURCE.replace("$10", "$0.015")
    ex = RulesExtractor().extract(source)
    assert ex.line_items[0].unit_price == Decimal("0.015")
    assert any(i.field == "line_items[0].unit_price" and i.severity == "error" for i in ex.issues)
    mock = SandboxMock()
    result = Agent(mock, INVOICER).tool_create_invoice(source)
    assert result["needs_review"] is True and mock.requests == []


@pytest.mark.parametrize("qty,price,currency", [
    ("0.5", "85.00", "USD"), ("1E+2", "0.01", "USD"),
    ("2.000000", "10.000", "USD"), ("0.5", "100", "JPY"),
])
def test_accepted_values_preserve_currency_and_amount_across_the_real_draft_path(qty, price, currency):
    data = payload(currency=currency, line_items=[{"desc": "Work", "qty": qty,
                    "unit_price": price, "currency": currency}])
    result, agent, mock = draft(data)
    assert result["ok"] is True, result
    summary = result["invoices"][0]
    invoice = mock.invoices[summary["invoice_id"]]
    assert invoice["detail"]["currency_code"] == currency
    assert Decimal(invoice["items"][0]["unit_amount"]["value"]) == Decimal(price)
    assert Decimal(invoice["items"][0]["quantity"]) == Decimal(qty)
    assert "E" not in invoice["items"][0]["quantity"]
    assert Decimal(summary["total"]) == Decimal(invoice["amount"]["value"])
    assert agent.ledger[summary["invoice_id"]].total == Decimal(invoice["amount"]["value"])
    assert len(agent.list_pending()) == 1
    assert not any(path.endswith(("/send", "/remind", "/payments")) for _, path, _ in mock.requests)


def test_one_invalid_currency_part_prevents_all_drafts():
    data = payload(line_items=[
        {"desc": "Good", "qty": "1", "unit_price": "10", "currency": "USD"},
        {"desc": "Bad", "qty": "1", "unit_price": "0.015", "currency": "EUR"},
    ])
    result, _, mock = draft(data)
    assert result["needs_review"] is True and mock.requests == []
