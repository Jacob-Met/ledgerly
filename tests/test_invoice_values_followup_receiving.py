"""Controls discovered while inspecting the first correction (r2).

Kept separate so the initial 26 independent cases remain byte-identical.
"""

from decimal import Decimal

import pytest

from test_invoice_values_receiving import (
    SOURCE_PREFIX, SuppliedExtraction, assert_refused_without_requests, extraction, make_agent,
)


def test_currency_mismatch_still_returns_review_when_a_deposit_is_present():
    ex = extraction(paid="25.00")
    ex.line_items[0].currency = "EUR"
    agent, mock = make_agent(SuppliedExtraction(ex))
    result = agent.tool_create_invoice("Known currency mismatch with a prior payment")
    assert_refused_without_requests(agent, mock, result)
    assert ex.amount_paid == Decimal("25.00")
    assert ex.currency == "USD" and ex.line_items[0].currency == "EUR"


@pytest.mark.parametrize("lines", [
    "- 1 x Service @ USD 100.00\nDeposit already paid: USD 1e999999999\n",
    "- 1 x Service @ USD 1e999999999\nTotal: USD 100.00\n",
])
def test_unsupported_finite_exponent_returns_review_before_aggregate_or_summary_arithmetic(lines):
    agent, mock = make_agent()
    result = agent.tool_create_invoice(SOURCE_PREFIX + lines + "Net 30\n")
    assert_refused_without_requests(agent, mock, result)
