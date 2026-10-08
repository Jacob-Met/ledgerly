"""Totals describe the invoice; a summary word alone does not identify a total."""

from decimal import Decimal

import pytest

from ledgerly.extract import RulesExtractor


HEADER = "From: Alex Example <alex@example.com>\n\nPrices are in USD. Net 30.\n"


def job(description, shape="fixed", summary="Total", stated="1000.00"):
    if shape == "table":
        return HEADER + (
            "| Item | Qty | Unit price |\n"
            "| --- | --- | --- |\n"
            f"| {description} | 1 | $800.00 |\n"
            "| Website build | 1 | $200.00 |\n"
            f"| {summary} | | $" + stated + " |\n"
        )
    work = (
        f"- 2 hours of {description} at $400.00/hr\n"
        if shape == "quantity"
        else f"- {description} — $800.00\n"
    )
    return HEADER + work + "- Website build — $200.00\n" + summary + ": $" + stated + "\n"


@pytest.mark.parametrize("description", [
    "Budget planning",
    "Total brand redesign",
    "Account balance report",
    "Subtotal reconciliation",
    "Annual budget review workshop",
    "Calculate the total cost report",
    "Reconcile account balance",
    "BUDGET planning",
    "Reconcile the account balance",
    "Prepare subtotal reconciliation",
    "Brand redesign total cost report",
    "Review annual budget",
    "Total station survey",
])
@pytest.mark.parametrize("shape", ["fixed", "quantity", "table"])
def test_summary_words_inside_work_descriptions_remain_billable(description, shape):
    ex = RulesExtractor().extract(job(description, shape))
    assert [item.desc for item in ex.line_items] == [description, "Website build"]
    assert ex.line_items[0].amount() == Decimal("800.00")
    assert ex.total() == Decimal("1000.00")
    assert ex.issues == []


@pytest.mark.parametrize("summary", [
    "Total",
    "Subtotal",
    "Budget",
    "Balance",
    "Altogether",
    "Grand total",
    "Estimated total",
    "Total budget",
    "Balance due",
    "Net total",
    "Final balance remaining",
    "Invoice total",
    "Project subtotal",
    "Outstanding balance",
    "Budget cap",
    "Total cost",
    "Total for this project",
    "Subtotal before tax",
    "gRaNd   ToTaL",
    "  TOTAL  ",
    "**Total**",
    "Total (USD)",
    "Invoice total (USD)",
    "Total USD",
    "Amount total",
    "Labor subtotal",
    "Services total",
    "Monthly budget",
    "Total charges",
    "Balance to pay",
    "Total incl. tax",
    "Total (before tax)",
    "Pre-tax total",
    "Sub total",
    "TOTAL.",
    "Balance due on receipt",
    "**Grand total:**",
    "Total invoice amount",
    "Total project cost",
    "Total labor charges",
    "Outstanding total balance",
    "**Total** (USD)",
    "Total ($)",
    "Total (US$)",
    "Total due today",
    "Total payable immediately",
    "Grand total including tax",
    "Total due (USD)",
    "Total amount payable (USD)",
    "Total (excluding tax)",
    "Total USD net",
    "Total due upon receipt",
    "USD Total",
    "VAT total",
    "Total (tax included)",
    "Total (tax excluded)",
    "Total inc. tax",
    "Total to be invoiced",
])
@pytest.mark.parametrize("shape", ["fixed", "table"])
def test_complete_summary_labels_are_not_billable(summary, shape):
    ex = RulesExtractor().extract(job("Website design", shape, summary))
    assert [item.desc for item in ex.line_items] == ["Website design", "Website build"]
    assert ex.total() == Decimal("1000.00")
    assert ex.issues == []


@pytest.mark.parametrize("shape", ["fixed", "table"])
def test_real_total_conflict_is_reported_after_preserving_work(shape):
    ex = RulesExtractor().extract(job("Budget planning", shape, stated="1200.00"))
    assert ex.total() == Decimal("1000.00")
    assert len(ex.issues) == 1
    issue = ex.issues[0]
    assert (issue.field, issue.severity) == ("line_items", "warning")
    assert "1200.00 differs from computed total 1000.00" in issue.message


def test_unparsed_summary_sentence_keeps_existing_conflict_reporting():
    ex = RulesExtractor().extract(
        HEADER + "Website design — $800.00\nThe total for this project is $900.00.\n"
    )
    assert [item.desc for item in ex.line_items] == ["Website design"]
    assert ex.total() == Decimal("800.00")
    assert len(ex.issues) == 1
    assert "900.00 differs from computed total 800.00" in ex.issues[0].message


@pytest.mark.parametrize("shape", ["fixed", "table"])
def test_draft_keeps_budget_work_and_still_requires_approval(agent, mock, shape):
    result = agent.tool_create_invoice(job("Budget planning", shape))
    assert result["ok"], result
    assert len(result["invoices"]) == 1
    draft = mock.get_invoice(result["invoices"][0]["invoice_id"]).body
    assert [item["name"] for item in draft["items"]] == ["Budget planning", "Website build"]
    assert draft["amount"]["value"] == "1000.00"
    assert draft["status"] == "DRAFT"
    assert len(agent.list_pending()) == 1
    assert not [
        request for request in mock.requests
        if request[1].endswith(("/send", "/remind", "/payments"))
    ]
