"""The numeric matcher must not backtrack into a valid-looking price prefix."""

import pytest

from test_invoice_values_receiving import SOURCE_PREFIX, assert_refused_without_requests, make_agent


@pytest.mark.parametrize("token", ["USD 12.345.67", "USD 1e33e2"])
def test_malformed_numeric_tail_cannot_be_silently_discarded(token):
    text = (SOURCE_PREFIX + "- 1 x Valid anchor @ USD 5.00\n"
            f"- 1 x Service @ {token}\nNet 30\n")
    agent, mock = make_agent()
    result = agent.tool_create_invoice(text)
    assert_refused_without_requests(agent, mock, result)
