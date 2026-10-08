"""Explicit visitor corrections for the offline browser demo.

This adapter supplies a checked extraction through the core's existing Extractor
protocol. It grants no send or payment permit and never changes the rules extractor.
"""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal, DecimalException
import re

from ledgerly.extract import (
    Extraction, Issue, LineItem, PAYPAL_CURRENCIES, RulesExtractor,
    compute_confidence, validate,
)


def _text(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    return value.strip()


def _decimal(value, field):
    raw = _text(value, field)
    if not re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", raw):
        raise ValueError(f"{field} needs a plain decimal number, such as 2 or 12.50.")
    number = Decimal(raw)
    if not number.is_finite():
        raise ValueError(f"{field} must be finite.")
    return number


def prepare_review(fields):
    """Rebuild editable fields and validate them, without trusting derived metadata."""
    allowed = {"client_name", "client_email", "due_days", "amount_paid", "line_items"}
    if not isinstance(fields, dict) or set(fields) != allowed:
        raise ValueError("Provide exactly the editable invoice fields.")
    raw_items = fields["line_items"]
    if not isinstance(raw_items, list):
        raise ValueError("Line items must be a list.")
    items = []
    extra = []
    for index, row in enumerate(raw_items):
        prefix = f"line_items[{index}]"
        if not isinstance(row, dict) or set(row) != {"desc", "qty", "unit_price", "currency", "unit"}:
            raise ValueError(f"Line item {index + 1} has incomplete or unexpected fields.")
        desc = _text(row["desc"], f"Line item {index + 1} description")
        currency = _text(row["currency"], f"Line item {index + 1} currency").upper()
        if not desc:
            extra.append(Issue(prefix + ".desc", "error", "Describe the work on this line."))
        if currency not in PAYPAL_CURRENCIES:
            extra.append(Issue(prefix + ".currency", "error", "Choose a supported currency for this line."))
        items.append(LineItem(
            desc,
            _decimal(row["qty"], f"Line item {index + 1} quantity"),
            _decimal(row["unit_price"], f"Line item {index + 1} unit price"),
            currency or None,
            _text(row["unit"], f"Line item {index + 1} unit") or None,
        ))
    days = _text(fields["due_days"], "Payment terms")
    if not re.fullmatch(r"[0-9]{1,3}", days):
        raise ValueError("Payment terms need a whole number of days from 0 to 365.")
    paid = _decimal(fields["amount_paid"], "Prior payment")
    if paid < 0:
        extra.append(Issue("amount_paid", "error", "Prior payment cannot be negative."))
    ex = Extraction(
        _text(fields["client_name"], "Client name") or None,
        _text(fields["client_email"], "Recipient email") or None,
        items[0].currency if items else None,
        items, int(days), paid, source="human_review",
    )
    try:
        # A visitor may supply a recipient absent from the source; this is an
        # explicit human correction, never an extractor grounding claim.
        ex.issues = extra + validate(ex)
        ex.total()  # Refuse unsupported decimal arithmetic before any draft effect.
    except DecimalException as exc:
        raise ValueError("These invoice values exceed the supported decimal precision.") from exc
    ex.confidence = compute_confidence(ex.issues)
    return ex


class ReviewableExtractor:
    """Use one reviewed value only inside a source-bound draft operation."""
    def __init__(self):
        self.rules = RulesExtractor()
        self._active = None

    def extract(self, text):
        if self._active is None:
            return self.rules.extract(text)
        source, extraction = self._active
        if text != source:
            raise ValueError("The source changed after review; analyze and check it again.")
        return deepcopy(extraction)

    @contextmanager
    def using(self, text, extraction):
        if self._active is not None:
            raise RuntimeError("A reviewed draft is already running.")
        self._active = (text, deepcopy(extraction))
        try:
            yield
        finally:
            self._active = None
