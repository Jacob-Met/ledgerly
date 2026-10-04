import json
from decimal import Decimal

import pytest

from conftest import FIXTURES, load
from ledgerly.extract import (
    HybridExtractor, LLMExtractor, RulesExtractor, split_by_currency, validate,
)

R = RulesExtractor()


def items(ex):
    return [(li.desc, li.qty, li.unit_price, li.currency) for li in ex.line_items]


def test_all_twelve_fixtures_present():
    assert len(list(FIXTURES.glob("*.txt"))) == 12


def test_simple_usd_hourly():
    ex = R.extract(load("01_simple_usd_hourly.txt"))
    assert ex.client_name == "Maya Chen"
    assert ex.client_email == "maya.chen@brightfern.example"
    assert ex.currency == "USD"
    assert ex.due_days == 15
    assert items(ex) == [("Copywriting", 12, 85, "USD"), ("SEO keyword audit", 1, 300, "USD")]
    assert ex.total() == Decimal("1320")
    assert ex.confidence == 1.0 and ex.issues == []


@pytest.mark.parametrize("fname,ccy,total,due", [
    ("02_gbp_proofreading.txt", "GBP", Decimal("800"), 30),
    ("03_eur_fixed_project.txt", "EUR", Decimal("2550"), 14),
    ("08_jpy_zero_decimal.txt", "JPY", Decimal("180000"), 30),
    ("09_table_cad.txt", "CAD", Decimal("740"), 10),
    ("10_billing_address_net45.txt", "USD", Decimal("2680"), 45),
])
def test_currency_totals_terms(fname, ccy, total, due):
    ex = R.extract(load(fname))
    assert ex.currency == ccy
    assert ex.total() == total
    assert ex.due_days == due
    assert not ex.errors


def test_multi_currency_flagged_and_split():
    ex = R.extract(load("04_multi_currency.txt"))
    assert ex.currencies() == ["EUR", "USD"]
    assert any(i.field == "currency" and i.severity == "warning" for i in ex.issues)
    parts = split_by_currency(ex)
    assert {p.currency: p.total() for p in parts} == {"EUR": Decimal("360"), "USD": Decimal("1900")}


def test_missing_email_is_error_and_name_from_signature():
    ex = R.extract(load("05_missing_email.txt"))
    assert ex.client_email is None
    assert ex.client_name == "Darnell Brooks"
    assert any(i.field == "client_email" and i.severity == "error" for i in ex.issues)
    assert ex.confidence < 1.0


def test_ambiguous_qty_is_error_due_on_receipt():
    ex = R.extract(load("06_ambiguous_qty.txt"))
    assert ex.due_days == 0
    assert ex.line_items[1].qty is None
    assert any(i.field == "line_items[1].qty" and i.severity == "error" for i in ex.issues)


def test_range_and_approx_qty_are_warnings():
    ex = R.extract(load("11_range_qty_approx.txt"))
    assert [li.qty for li in ex.line_items] == [10, 5]
    sev = {i.field: i.severity for i in ex.issues}
    assert sev["line_items[0].qty"] == "warning" and sev["line_items[1].qty"] == "warning"
    assert not ex.errors and 0.5 < ex.confidence < 1.0


def test_partial_payment_detected_not_a_line_item():
    ex = R.extract(load("07_partial_payment_deposit.txt"))
    assert ex.amount_paid == Decimal("1000")
    assert ex.total() == Decimal("3500")
    assert all("deposit" not in li.desc.lower() for li in ex.line_items)


def test_billing_email_preferred_over_sender():
    ex = R.extract(load("10_billing_address_net45.txt"))
    assert ex.client_email == "ap@atlasfreight.example"


def test_injection_text_not_turned_into_line_item():
    ex = R.extract(load("12_prompt_injection.txt"))
    assert items(ex) == [("Bug fixing", 5, 90, "USD")]
    assert ex.client_email == "victor@quickflip.example"


def test_table_total_row_is_not_an_item():
    ex = R.extract(load("09_table_cad.txt"))
    assert [li.desc for li in ex.line_items] == ["Social posts", "Analytics report"]


def test_stated_total_mismatch_warns():
    text = "From: A B <a@b.example>\n\n- 2 x Widgets @ $10\nTotal: $50\nNet 30\n"
    ex = R.extract(text)
    assert any("differs from computed total" in i.message for i in ex.issues)


def test_no_terms_defaults_with_warning():
    ex = R.extract("From: A B <a@b.example>\n\n- 2 x Widgets @ $10\n")
    assert ex.due_days == 30
    assert any(i.field == "due_days" for i in ex.issues)


def test_empty_text_low_confidence():
    ex = R.extract("hello")
    assert ex.confidence <= 0.5 and ex.errors


# ---------------- LLM interface (fake model, no network)

def _fake(payload):
    return lambda prompt: payload if isinstance(payload, str) else json.dumps(payload)


def test_llm_extractor_happy_path_with_code_fence():
    text = load("05_missing_email.txt") + "\nmy email: darnell.b@mailbox.example\n"
    out = {"client_name": "Darnell Brooks", "client_email": "darnell.b@mailbox.example", "currency": "USD",
           "line_items": [{"desc": "Logo concepts", "qty": 3, "unit_price": 250}],
           "due_days": 7, "amount_paid": 0, "confidence": 0.9, "issues": []}
    ex = LLMExtractor(_fake("```json\n" + json.dumps(out) + "\n```")).extract(text)
    assert ex.source == "llm" and ex.client_email == "darnell.b@mailbox.example"
    assert ex.line_items[0].currency == "USD" and ex.confidence == 0.9


def test_llm_hallucinated_email_is_rejected():
    out = {"client_name": "Darnell", "client_email": "made.up@nowhere.example", "currency": "USD",
           "line_items": [{"desc": "Logo", "qty": 1, "unit_price": 250}], "due_days": 7, "confidence": 0.99}
    ex = LLMExtractor(_fake(out)).extract(load("05_missing_email.txt"))
    assert ex.client_email is None
    assert any("hallucination" in i.message for i in ex.issues)
    assert ex.confidence < 0.99


def test_llm_garbage_output_is_zero_confidence():
    ex = LLMExtractor(_fake("Sure! Here's the invoice...")).extract("x")
    assert ex.confidence == 0.0 and ex.errors


def test_hybrid_only_calls_llm_when_needed():
    calls = []

    def complete(prompt):
        calls.append(prompt)
        return "{}"

    h = HybridExtractor(R, LLMExtractor(complete), threshold=0.8)
    h.extract(load("01_simple_usd_hourly.txt"))
    assert calls == []
    h.extract(load("05_missing_email.txt"))
    assert len(calls) == 1 and "Darnell" in calls[0]


def test_validate_flags_jpy_decimals():
    ex = R.extract("From: K <k@x.example>\n\n- 1 x Thing @ ¥100.50\nNet 30")
    assert any("does not support decimals" in i.message for i in validate(ex))
