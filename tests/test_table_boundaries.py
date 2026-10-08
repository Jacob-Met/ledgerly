import itertools
from decimal import Decimal

import pytest

from ledgerly.extract import RulesExtractor

PREFIX = "From: Alex Example <alex@studio.example>\n\nPrices are in USD.\nNet 30\n\n"
FIRST = "| Item | Qty | Unit price |\n| --- | --- | --- |\n| Editing | 2 | $100 |"


def table(columns, row):
    return "\n".join([
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        "| " + " | ".join(row[column] for column in columns) + " |",
    ])


def extract(body):
    return RulesExtractor().extract(PREFIX + body)


def values(result):
    return [(item.desc, item.qty, item.unit_price, item.currency)
            for item in result.line_items]


@pytest.mark.parametrize("columns", list(itertools.permutations(
    ["Description", "Qty", "Unit price"])))
def test_each_later_table_uses_its_own_header(columns):
    second = table(columns, {"Description": "Photos", "Qty": "3", "Unit price": "$75"})
    result = extract(FIRST + "\n\nAdditional work:\n\n" + second)
    assert values(result) == [("Editing", Decimal(2), Decimal(100), "USD"),
                              ("Photos", Decimal(3), Decimal(75), "USD")]
    assert result.total() == Decimal(425)
    assert result.issues == []


@pytest.mark.parametrize("separator", ["\n", "\n\n", "\nMilestone two:\n"])
def test_repeated_header_is_not_a_billable_row(separator):
    result = extract(FIRST + separator + FIRST.replace("Editing", "Review"))
    assert [item.desc for item in result.line_items] == ["Editing", "Review"]
    assert result.total() == Decimal(400)
    assert result.issues == []


def test_unrelated_tables_before_and_after_do_not_inherit_invoice_columns():
    context = "| Milestone | Contact | Status |\n| --- | --- | --- |\n| Launch | Alex | Ready |"
    result = extract(context + "\n\n" + FIRST + "\n\n" + context)
    assert values(result) == [("Editing", Decimal(2), Decimal(100), "USD")]
    assert result.issues == []


def test_reordered_header_can_follow_without_a_blank_line():
    second = table(["Unit price", "Description", "Qty"],
                   {"Description": "Photos", "Qty": "3", "Unit price": "$75"})
    result = extract(FIRST + "\n" + second)
    assert [item.desc for item in result.line_items] == ["Editing", "Photos"]
    assert result.total() == Decimal(425)
    assert result.issues == []


def test_plain_priced_line_between_tables_is_still_extracted():
    second = table(["Unit price", "Description", "Qty"],
                   {"Description": "Photos", "Qty": "3", "Unit price": "$75"})
    result = extract(FIRST + "\n\n- Proofreading: 1 hr @ $50/hr\n\n" + second)
    assert {item.desc: item.amount() for item in result.line_items} == {
        "Editing": Decimal(200), "Photos": Decimal(225), "Proofreading": Decimal(50)}
    assert result.total() == Decimal(475)
    assert result.issues == []


def test_description_named_hours_is_data_not_a_new_header():
    result = extract(FIRST + "\n| Hours | 1 | $25 |")
    assert [item.desc for item in result.line_items] == ["Editing", "Hours"]
    assert result.total() == Decimal(225)
    assert result.issues == []


def test_invalid_quantity_in_second_table_still_blocks_drafting():
    second = table(["Unit price", "Description", "Qty"],
                   {"Description": "Photos", "Qty": "several", "Unit price": "$75"})
    result = extract(FIRST + "\n\n" + second)
    assert [item.desc for item in result.line_items] == ["Editing", "Photos"]
    assert result.line_items[1].qty is None
    assert any(issue.field == "line_items[1].qty" for issue in result.errors)


def test_missing_price_column_retains_existing_refusal():
    result = extract("| Item | Qty |\n| --- | --- |\n| Editing | 2 |")
    assert result.line_items == []
    assert result.errors


def test_truncated_row_in_later_table_is_not_silently_repriced():
    second = "| Unit price | Qty | Description |\n| --- | --- | --- |\n| $75 | 3 |"
    result = extract(FIRST + "\n\n" + second)
    assert [item.desc for item in result.line_items] == ["Editing"]
    assert any("Malformed table row" in issue.message for issue in result.errors)


def test_existing_total_row_recognition_is_preserved():
    result = extract(FIRST + "\n| Total | | $200 |")
    assert [item.desc for item in result.line_items] == ["Editing"]
    assert result.issues == []


@pytest.mark.parametrize("description,quantity", [
    ("Price audit", "hours"),
    ("Unit price review", "hrs"),
    ("Price", "qty"),
    ("Item price", "quantity"),
])
def test_data_with_header_words_keeps_its_invalid_quantity(description, quantity):
    result = extract(FIRST + f"\n| {description} | {quantity} | $75 |")
    assert [item.desc for item in result.line_items] == ["Editing", description]
    assert result.line_items[1].qty is None
    assert any(issue.field == "line_items[1].qty" for issue in result.errors)


def test_header_words_in_data_block_a_partial_sandbox_draft(agent, mock):
    result = agent.tool_create_invoice(PREFIX + FIRST + "\n| Price audit | hours | $75 |")
    assert result["ok"] is False and result["needs_review"]
    assert mock.invoices == {}
    assert agent.list_pending() == []
    assert mock.requests == []


@pytest.mark.parametrize("separator", ["\n\n", "\n\nAdditional work:\n\n"])
@pytest.mark.parametrize("description,quantity", [
    ("Photos", "3"), ("Photos", "several"), ("Price audit", "hours"),
])
def test_unheaded_continuation_retains_rows_across_prose_and_blank_lines(separator, description, quantity):
    result = extract(FIRST + separator + f"| {description} | {quantity} | $75 |")
    assert [item.desc for item in result.line_items] == ["Editing", description]
    if quantity == "3":
        assert result.total() == Decimal(425)
        assert result.errors == []
    else:
        assert result.line_items[1].qty is None
        assert any(issue.field == "line_items[1].qty" for issue in result.errors)


@pytest.mark.parametrize("header", [
    "| Milestone | Owner | Budget |", "| Description | Owner | Budget |",
])
def test_new_unrelated_table_cannot_borrow_previous_invoice_columns(header):
    result = extract(FIRST + "\n\nPlanning only:\n\n" + header +
                     "\n| --- | --- | --- |\n| Launch | 3 | $75 |")
    assert values(result) == [("Editing", Decimal(2), Decimal(100), "USD")]
    assert result.errors == []


@pytest.mark.parametrize("suffix", [
    "\n| Photos | 3 |",
    "\n\n| Unit price | Qty | Description |\n| --- | --- | --- |\n| $75 | 3 |",
])
def test_truncated_invoice_rows_refuse_partial_drafts(agent, mock, suffix):
    result = agent.tool_create_invoice(PREFIX + FIRST + suffix)
    assert result["ok"] is False and result["needs_review"]
    assert mock.invoices == {}
    assert agent.list_pending() == []
    assert mock.requests == []


@pytest.mark.parametrize("body", [
    FIRST + "\n| Photos | 3 | $75 |\n| --- | --- | --- |",
    FIRST + "\n| --- | --- | --- |\n| Photos | 3 | $75 |",
    FIRST + "\n| Photos | 3 | $75 |\n| --- | --- | --- |\n| Proofreading | 1 | $50 |",
])
def test_separator_rows_do_not_erase_invoice_data_or_column_state(body):
    result = extract(body)
    assert [item.desc for item in result.line_items] == (
        ["Editing", "Photos", "Proofreading"] if "Proofreading" in body
        else ["Editing", "Photos"])
    assert result.total() == (Decimal(475) if "Proofreading" in body else Decimal(425))
    assert result.issues == []


def test_invalid_quantity_before_separator_still_blocks_partial_draft(agent, mock):
    result = agent.tool_create_invoice(PREFIX + FIRST +
        "\n| Price audit | hours | $75 |\n| --- | --- | --- |")
    assert result["ok"] is False and result["needs_review"]
    assert mock.invoices == {}
    assert agent.list_pending() == []
    assert mock.requests == []
