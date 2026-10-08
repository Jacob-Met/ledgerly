"""Detached details of the browser's existing in-memory sandbox invoices.

This is a snapshot projection, not a provider operation. Only invoices already
in the displayed agent ledger are included, and private mock bookkeeping is not
exposed. Monetary values retain the representation supplied by the Python mock.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any


_RECORD_FIELDS = (
    "id", "status", "detail", "invoicer", "primary_recipients", "items",
    "amount", "due_amount", "payments",
)


def snapshot_invoice_details(
    invoices: Mapping[str, Any], invoice_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Copy matching retained records without fetching, recalculating or editing."""
    rows = []
    for invoice_id in invoice_ids:
        invoice = invoices.get(invoice_id)
        available = isinstance(invoice, dict) and invoice.get("id") == invoice_id
        record = (
            deepcopy({key: invoice[key] for key in _RECORD_FIELDS if key in invoice})
            if available else None
        )
        rows.append({"invoice_id": invoice_id, "record": record})
    return rows
