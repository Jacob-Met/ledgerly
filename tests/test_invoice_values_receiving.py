"""Independent exact-value receiving through extraction, draft and approval.

All provider operations use Ledgerly's native offline SandboxMock. A refused
complete job must not allocate an invoice number or create a partial draft.
"""

import copy
import json
from datetime import date
from decimal import Decimal

import pytest

from ledgerly.agent import Agent, ApprovalRequired
from ledgerly.extract import Extraction, LineItem, LLMExtractor, RulesExtractor, validate
from ledgerly.paypal import SandboxMock, build_invoice


INVOICER = {"name": "Receiving Fixture", "email_address": "reviewer@example.invalid"}
SOURCE_PREFIX = "From: Fixture Payer <payer@example.invalid>\n\n"
TODAY = date(2026, 10, 1)


class SuppliedExtraction:
    def __init__(self, extraction):
        self.extraction = extraction

    def extract(self, text):
        return self.extraction


def extraction(*, currency="USD", qty="1", price="100.00", paid="0"):
    return Extraction(
        "Fixture Payer", "payer@example.invalid", currency,
        [LineItem("Reviewed service", Decimal(qty), Decimal(price), currency)],
        30, Decimal(paid), confidence=1.0,
    )


def make_agent(extractor=None):
    mock = SandboxMock()
    agent = Agent(mock, INVOICER, extractor=extractor, today=lambda: TODAY)
    return agent, mock


def assert_refused_without_requests(agent, mock, result):
    assert result["ok"] is False, result
    assert result["needs_review"] is True, result
    assert any(issue["severity"] == "error" for issue in result["issues"]), result
    assert mock.requests == []
    assert mock.invoices == {}
    assert agent.ledger == {}
    assert agent.list_pending() == []


def assert_draft_amounts(agent, mock, result, currency, total):
    assert result["ok"] is True, result
    assert len(result["invoices"]) == 1
    row = result["invoices"][0]
    iid = row["invoice_id"]
    current = mock.get_invoice(iid).body
    assert row["currency"] == currency
    assert Decimal(row["total"]) == total
    assert agent.ledger[iid].total == total
    assert current["detail"]["currency_code"] == currency
    assert Decimal(current["amount"]["value"]) == total
    assert Decimal(current["due_amount"]["value"]) == total
    assert agent.pending[row["approval_id"]].status == "PENDING"
    assert not any(r[1].endswith(("/send", "/remind", "/payments")) for r in mock.requests)
    return row, current


@pytest.mark.parametrize("invalid", ["missing-quantity", "nonfinite-price", "currency-mismatch", "negative-deposit"])
def test_public_admission_rechecks_stale_issue_free_extraction_without_mutation(invalid):
    ex = extraction()
    if invalid == "missing-quantity":
        ex.line_items[0].qty = None
    elif invalid == "nonfinite-price":
        ex.line_items[0].unit_price = Decimal("NaN")
    elif invalid == "currency-mismatch":
        ex.line_items[0].currency = "EUR"
    elif invalid == "negative-deposit":
        ex.amount_paid = Decimal("-25")
    before = repr(ex)
    assert ex.issues == [] and ex.confidence == 1.0
    assert any(issue.severity == "error" for issue in validate(ex))
    with pytest.raises(ValueError):
        build_invoice(ex, INVOICER, "RECEIVING", TODAY)
    agent, mock = make_agent(SuppliedExtraction(ex))
    result = agent.tool_create_invoice("Explicitly supplied review fixture")
    assert_refused_without_requests(agent, mock, result)
    assert repr(ex) == before


def test_invalid_later_currency_part_cannot_leave_an_earlier_draft():
    ex = extraction()
    ex.line_items = [
        LineItem("Earlier EUR part", Decimal(1), Decimal("100.00"), "EUR"),
        LineItem("Later sub-cent USD part", Decimal(2), Decimal("0.015"), "USD"),
    ]
    agent, mock = make_agent(SuppliedExtraction(ex))
    result = agent.tool_create_invoice("Explicitly supplied mixed-currency fixture")
    assert_refused_without_requests(agent, mock, result)


@pytest.mark.parametrize("currency,maximum", [
    ("USD", "99999999999999999999999999.99"),
    ("JPY", "9999999999999999999999999999"),
])
def test_complete_currency_sum_is_admitted_before_any_number_or_partial_draft(currency, maximum):
    ex = extraction(currency=currency)
    ex.line_items = [
        LineItem("Earlier EUR part", Decimal(1), Decimal("100.00"), "EUR"),
        LineItem("Individually exact one", Decimal(1), Decimal(maximum), currency),
        LineItem("Individually exact two", Decimal(1), Decimal(maximum), currency),
    ]
    agent, mock = make_agent(SuppliedExtraction(ex))
    try:
        result = agent.tool_create_invoice("Whole-job sum receiving fixture")
    except Exception as error:
        pytest.fail(
            f"Expected whole-job review before requests, got {type(error).__name__}: {error}; "
            f"calls={[(r[0], r[1]) for r in mock.requests]}, "
            f"retained_drafts={len(mock.invoices)}, retained_pending={len(agent.list_pending())}"
        )
    assert_refused_without_requests(agent, mock, result)
    assert any(issue.severity == "error" for issue in validate(ex))

    single_currency = copy.deepcopy(ex)
    single_currency.line_items = single_currency.line_items[1:]
    with pytest.raises(ValueError):
        build_invoice(single_currency, INVOICER, "RECEIVING-SUM", TODAY)


@pytest.mark.parametrize("context,item,deposit_lines", [
    ("", "USD 100.00", ["Deposit already paid: EUR 25.00"]),
    ("", "EUR 100.00", ["Deposit already paid: USD 25.00"]),
    ("Prices are in CAD\n", "$100.00", ["Deposit already paid: US$25.00"]),
    ("", "USD 100.00", ["Deposit already paid: USD 10.00", "Already paid: EUR 15.00"]),
])
def test_foreign_deposit_never_becomes_a_payment_in_the_invoice_currency(context, item, deposit_lines):
    text = SOURCE_PREFIX + context + f"- 1 x Project @ {item}\n" + "\n".join(deposit_lines) + "\nNet 30\n"
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    assert_refused_without_requests(agent, mock, result)


def test_two_subunit_deposits_do_not_hide_each_others_invalid_precision():
    text = (SOURCE_PREFIX + "- 1 x Project @ USD 100.00\n"
            "Deposit already paid: USD 0.005\nAlready paid: USD 0.005\nNet 30\n")
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    assert_refused_without_requests(agent, mock, result)


@pytest.mark.parametrize("context,item,deposit_lines,currency,paid", [
    ("", "USD 100.00", ["Deposit already paid: USD 25.00", "Already paid: USD 10.00"], "USD", "35.00"),
    ("", "EUR 100.00", ["Deposit already paid: EUR 25.00"], "EUR", "25.00"),
    ("Prices are in CAD\n", "$100.00", ["Deposit already paid: $25.00"], "CAD", "25.00"),
])
def test_supported_deposit_currency_and_exact_value_survive_human_approval(context, item, deposit_lines, currency, paid):
    text = SOURCE_PREFIX + context + f"- 1 x Project @ {item}\n" + "\n".join(deposit_lines) + "\nNet 30\n"
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    row, _ = assert_draft_amounts(agent, mock, result, currency, Decimal("100.00"))
    assert agent.ledger[row["invoice_id"]].prepaid == Decimal(paid)

    agent.approve(row["approval_id"])
    payments = [r for r in mock.requests if r[1].endswith("/payments")]
    assert len(payments) == 1
    assert payments[0][2]["amount"]["currency_code"] == currency
    assert Decimal(payments[0][2]["amount"]["value"]) == Decimal(paid)
    assert agent.ledger[row["invoice_id"]].paid_amount == Decimal(paid)
    assert agent.ledger[row["invoice_id"]].balance == Decimal("100.00") - Decimal(paid)
    with pytest.raises(ApprovalRequired):
        agent.client.record_payment(row["invoice_id"], {"amount": {"currency_code": currency, "value": paid}})
    assert len([r for r in mock.requests if r[1].endswith("/payments")]) == 1


@pytest.mark.parametrize("currency,qty,price,total,serialized_qty", [
    ("USD", "0.5", "85.00", "42.50", "0.5"),
    ("USD", "0.00001", "1000.00", "0.01", "0.00001"),
    ("USD", "1E+6", "0.01", "10000.00", "1000000"),
    ("JPY", "0.5", "100", "50", "0.5"),
])
def test_accepted_fractional_and_exponent_values_keep_draft_ledger_and_review_equal(currency, qty, price, total, serialized_qty):
    ex = extraction(currency=currency, qty=qty, price=price)
    assert not [issue for issue in validate(ex) if issue.severity == "error"]
    built = build_invoice(ex, INVOICER, "RECEIVING-EXACT", TODAY)
    assert built["items"][0]["quantity"] == serialized_qty
    assert Decimal(built["items"][0]["unit_amount"]["value"]) == Decimal(price)
    assert built["items"][0]["unit_amount"]["currency_code"] == currency

    agent, mock = make_agent(SuppliedExtraction(ex))
    result = agent.tool_create_invoice("Explicit exact-value receiving fixture")
    assert_draft_amounts(agent, mock, result, currency, Decimal(total))


@pytest.mark.parametrize("spelling,exact_price", [
    ("-$10", None),
    ("$1e3", Decimal("1000")),
    ("$1,23", None),
])
def test_unsupported_money_spelling_cannot_silently_change_value_or_drop_a_priced_line(spelling, exact_price):
    text = SOURCE_PREFIX + "- 1 x Valid anchor @ USD 5.00\n" + f"- 1 x Service @ {spelling}\nNet 30\n"
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    if exact_price is None or not result["ok"]:
        assert_refused_without_requests(agent, mock, result)
    else:
        # Exact support for exponent notation is permissible; interpreting only
        # its prefix, or silently dropping that line, is not.
        row, current = assert_draft_amounts(agent, mock, result, "USD", Decimal("5.00") + exact_price)
        assert len(current["items"]) == 2
        assert Decimal(current["items"][1]["unit_amount"]["value"]) == exact_price


@pytest.mark.parametrize("quantity,expected", [(".5", Decimal("0.5")), ("-1", None)])
def test_table_quantity_is_read_completely_or_held_before_any_draft(quantity, expected):
    text = (SOURCE_PREFIX + "Invoice in USD\n| Item | Qty | Unit price |\n"
            "| Valid anchor | 1 | 5.00 |\n"
            f"| Service | {quantity} | 100.00 |\nNet 30\n")
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    if expected is None or not result["ok"]:
        assert_refused_without_requests(agent, mock, result)
    else:
        row, current = assert_draft_amounts(agent, mock, result, "USD", Decimal("5.00") + expected * 100)
        assert Decimal(current["items"][1]["quantity"]) == expected


@pytest.mark.parametrize("field", ["unit_price", "amount_paid"])
def test_nonfinite_fake_model_money_returns_review_without_exception_or_request(field):
    data = {
        "client_name": "Fixture Payer", "client_email": "payer@example.invalid", "currency": "USD",
        "line_items": [{"desc": "Project", "qty": 1, "unit_price": 100, "currency": "USD"}],
        "due_days": 30, "amount_paid": 0, "confidence": 1.0,
    }
    if field == "unit_price":
        data["line_items"][0]["unit_price"] = "NaN"
    else:
        data["amount_paid"] = "Infinity"
    extractor = LLMExtractor(lambda prompt: json.dumps(data))
    source = SOURCE_PREFIX + "- 1 x Project @ USD 100.00\nNet 30\n"
    agent, mock = make_agent(extractor)
    result = agent.tool_create_invoice(source)
    assert_refused_without_requests(agent, mock, result)
