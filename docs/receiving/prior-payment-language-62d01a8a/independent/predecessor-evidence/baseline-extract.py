"""Job email / plain text -> structured invoice draft.

Two extractors share one output type (`Extraction`) and one validator:

* `RulesExtractor`  - deterministic regex/heuristic parser. No network, no model.
* `LLMExtractor`    - pluggable: you inject `complete(prompt) -> str`. No live LLM
                      call is made anywhere in this repo; tests use a fake.
* `HybridExtractor` - rules first, falls back to the LLM when confidence is low.

Every result has a 0..1 `confidence` and field-level `issues`
(severity: error | warning | info). Errors block invoice creation in the agent
until a human fixes them.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Optional, Protocol

# Subset of PayPal-supported currency codes.
# https://developer.paypal.com/api/rest/reference/currency-codes/
PAYPAL_CURRENCIES = {
    "AUD", "BRL", "CAD", "CNY", "CZK", "DKK", "EUR", "HKD", "HUF", "ILS", "JPY",
    "MYR", "MXN", "TWD", "NZD", "NOK", "PHP", "PLN", "GBP", "SGD", "SEK", "CHF",
    "THB", "USD",
}
# Currencies PayPal treats as having no decimal places (same reference page).
ZERO_DECIMAL_CURRENCIES = {"JPY", "HUF", "TWD"}
DOLLAR_CURRENCIES = {"USD", "CAD", "AUD", "NZD", "SGD", "HKD", "MXN", "TWD"}

SYMBOLS = {
    "US$": "USD", "CA$": "CAD", "C$": "CAD", "AU$": "AUD", "A$": "AUD",
    "NZ$": "NZD", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY",
}

SEVERITY_PENALTY = {"error": 0.25, "warning": 0.10, "info": 0.0}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SYM = "|".join(re.escape(s) for s in sorted(SYMBOLS, key=len, reverse=True))
_CODE = "|".join(sorted(PAYPAL_CURRENCIES))
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"
_NO_SUFFIX = r"(?![\d.,]*[kKmM]\b)"  # don't read "$5k" as $5
MONEY_RE = re.compile(
    rf"(?:(?P<pre>{_SYM}|\b(?:{_CODE})\b)\s?(?P<num>{_NUM}){_NO_SUFFIX}"
    rf"|(?P<num2>{_NUM}){_NO_SUFFIX}\s?(?P<post>\b(?:{_CODE})\b|€|£))"
)

_WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_Q = (
    r"(?:(?:~\s*|approx\.?\s*|about\s+|around\s+|roughly\s+)?"
    r"\d+(?:\.\d+)?(?:\s*(?:-|–|to)\s*\d+(?:\.\d+)?)?"
    r"|(?:a\s+few|a\s+couple(?:\s+of)?|several|some|"
    + "|".join(_WORD_NUMS) + r")\b)"
)
_UNITS = (
    r"(?:hours?|hrs?|h|days?|pages?|words?|units?|revisions?|sessions?|items?|"
    r"pcs?|photos?|articles?|posts?|videos?|weeks?|months?|screens?|episodes?)"
)
_ITEM_PATTERNS = [
    # "3 x Logo concepts @ $250 each"
    re.compile(rf"^(?P<qty>{_Q})\s*(?:x|×|\*)\s*(?P<desc>.+?)\s*(?:@|\bat\b|\bfor\b)\s*<M>", re.I),
    # "12 hours of copy editing at £45/hr"
    re.compile(rf"^(?P<qty>{_Q})\s*(?P<unit>{_UNITS})\b\s+(?:of\s+)?(?P<desc>.+?)\s*(?:@|\bat\b|\bfor\b|x|×)\s*<M>", re.I),
    # "Proofreading: 3 hrs @ £40/hr"
    re.compile(rf"^(?P<desc>.+?)\s*[:–—-]\s*(?P<qty>{_Q})\s*(?P<unit>[A-Za-z]+\.?)?\s*(?:@|\bat\b|x|×)\s*<M>", re.I),
    # "4 product photos at $75 each" / "a few revisions at $40 each"
    re.compile(rf"^(?P<qty>{_Q})\s+(?P<desc>.+?)\s*(?:@|\bat\b)\s*<M>", re.I),
    # "Website build — €2,400.00"  (qty 1; separator must touch the price)
    re.compile(r"^(?P<desc>.+?)\s*(?:[:–—-]|@|\bat\b|\bfor\b)\s*<M>", re.I),
]
_BULLET_RE = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s+")
_PAID_RE = re.compile(
    r"\b(deposit|already paid|paid upfront|advance payment|prepaid|have paid|we paid|retainer paid)\b", re.I
)
_TOTAL_RE = re.compile(r"\b(total|subtotal|budget|balance|altogether)\b", re.I)
_BILLING_RE = re.compile(
    r"\b(?:send|email|address|forward)\s+(?:the\s+|your\s+|all\s+)?invoices?\s+to\s+(" + EMAIL_RE.pattern + ")",
    re.I,
)
_DOC_CCY_RE = re.compile(
    rf"\b(?:prices?|amounts?|rates?|figures?|billed|bill|invoice)\s+(?:are\s+|is\s+|us\s+)?in\s+({_CODE})\b",
    re.I,
)
_DUE_PATTERNS = [
    re.compile(r"\bnet\s*[- ]?\s*(\d{1,3})\b", re.I),
    re.compile(r"\bdue\s+(?:with)?in\s+(\d{1,3})\s+days\b", re.I),
    re.compile(r"\b(?:pay|paid|payment)\b[^.\n]{0,30}?\bwithin\s+(\d{1,3})\s+days\b", re.I),
    re.compile(r"\bwithin\s+(\d{1,3})\s+days\b", re.I),
    re.compile(r"\b(\d{1,3})[- ]day\s+(?:payment\s+)?terms?\b", re.I),
]
_DUE_ON_RECEIPT_RE = re.compile(r"\b(?:due\s+(?:up)?on\s+receipt|payable\s+immediately)\b", re.I)
_SIGNOFF_RE = re.compile(
    r"^(thanks|thank you|thx|best|regards|cheers|best regards|kind regards|warm regards|sincerely)[,!.]?\s*$", re.I
)
_HEADER_KEYS = {"from", "to", "cc", "subject", "date", "reply-to"}


@dataclass
class Issue:
    field: str
    severity: str  # error | warning | info
    message: str

    def to_dict(self) -> dict:
        return {"field": self.field, "severity": self.severity, "message": self.message}


@dataclass
class LineItem:
    desc: str
    qty: Optional[Decimal]
    unit_price: Decimal
    currency: Optional[str] = None
    unit: Optional[str] = None

    def amount(self) -> Decimal:
        return (self.qty or Decimal(0)) * self.unit_price

    def to_dict(self) -> dict:
        return {
            "desc": self.desc,
            "qty": None if self.qty is None else str(self.qty),
            "unit_price": str(self.unit_price),
            "currency": self.currency,
            "unit": self.unit,
        }


@dataclass
class Extraction:
    client_name: Optional[str]
    client_email: Optional[str]
    currency: Optional[str]
    line_items: list[LineItem]
    due_days: Optional[int]
    amount_paid: Decimal = Decimal(0)
    issues: list[Issue] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "rules"

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    def currencies(self) -> list[str]:
        return sorted({li.currency for li in self.line_items if li.currency})

    def total(self) -> Decimal:
        return sum((li.amount() for li in self.line_items), Decimal(0))

    def to_dict(self) -> dict:
        return {
            "client_name": self.client_name,
            "client_email": self.client_email,
            "currency": self.currency,
            "line_items": [li.to_dict() for li in self.line_items],
            "due_days": self.due_days,
            "amount_paid": str(self.amount_paid),
            "total": str(self.total()),
            "confidence": self.confidence,
            "issues": [i.to_dict() for i in self.issues],
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Extraction":
        items = []
        for li in d.get("line_items") or []:
            qty = li.get("qty")
            items.append(
                LineItem(
                    desc=str(li.get("desc") or "").strip(),
                    qty=None if qty in (None, "") else _dec(qty),
                    unit_price=_dec(li.get("unit_price", 0)),
                    currency=(li.get("currency") or d.get("currency") or None),
                    unit=li.get("unit"),
                )
            )
        ex = cls(
            client_name=d.get("client_name"),
            client_email=d.get("client_email"),
            currency=d.get("currency"),
            line_items=items,
            due_days=None if d.get("due_days") is None else int(d["due_days"]),
            amount_paid=_dec(d.get("amount_paid") or 0),
            issues=[Issue(**i) for i in d.get("issues") or []],
            confidence=float(d.get("confidence") or 0.0),
            source=d.get("source", "dict"),
        )
        return ex


class Extractor(Protocol):
    def extract(self, text: str) -> Extraction: ...


# ----------------------------------------------------------------- helpers

def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"not a number: {v!r}")


def quantize(value: Decimal, currency: Optional[str]) -> Decimal:
    exp = Decimal("1") if currency in ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
    return value.quantize(exp, rounding=ROUND_HALF_UP)


def compute_confidence(issues: list[Issue]) -> float:
    score = 1.0 - sum(SEVERITY_PENALTY.get(i.severity, 0.0) for i in issues)
    return round(max(0.0, min(1.0, score)), 2)


def parse_money(m: re.Match) -> tuple[Optional[str], Decimal, str]:
    """Return (currency_code, amount, raw_currency_token)."""
    tok = m.group("pre") or m.group("post") or ""
    num = m.group("num") or m.group("num2")
    code = SYMBOLS.get(tok, tok.upper() if tok.upper() in PAYPAL_CURRENCIES else None)
    return code, _dec(num), tok


def parse_qty(raw: str) -> tuple[Optional[Decimal], Optional[str]]:
    """Return (qty, ambiguity_reason). qty None means unknowable."""
    s = raw.strip().lower()
    if re.fullmatch(r"a\s+few|several|some", s):
        return None, f"vague quantity '{raw.strip()}'"
    if re.fullmatch(r"a\s+couple(?:\s+of)?", s):
        return Decimal(2), f"'{raw.strip()}' interpreted as 2"
    if s in _WORD_NUMS:
        return Decimal(_WORD_NUMS[s]), None
    approx = re.match(r"^(?:~\s*|approx\.?\s*|about\s+|around\s+|roughly\s+)", s)
    rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)", s)
    if rng:
        lo = Decimal(rng.group(1))
        return lo, f"range '{raw.strip()}' - used lower bound {lo}; confirm with client"
    n = re.search(r"\d+(?:\.\d+)?", s)
    if not n:
        return None, f"unreadable quantity '{raw.strip()}'"
    q = Decimal(n.group(0))
    if approx:
        return q, f"approximate quantity '{raw.strip()}' - used {q}"
    return q, None


def _split_headers(text: str) -> tuple[dict[str, str], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    headers: dict[str, str] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z-]+):\s*(.*)$", lines[i])
        if not m or m.group(1).lower() not in _HEADER_KEYS:
            break
        headers[m.group(1).lower()] = m.group(2).strip()
        i += 1
    return headers, "\n".join(lines[i:])


def _parse_address(value: str) -> tuple[Optional[str], Optional[str]]:
    if not value:
        return None, None
    em = EMAIL_RE.search(value)
    email = em.group(0).lower() if em else None
    name = value
    if em:
        name = value[: em.start()] + value[em.end():]
    name = re.sub(r"[<>\"]", " ", name)
    paren = re.search(r"\(([^)]+)\)", name)  # "佐藤 健 (Ken Sato)" -> prefer latin alias
    if paren:
        name = paren.group(1)
    name = re.sub(r"\s+", " ", name).strip(" ,")
    return (name or None), email


def _signature_name(body: str) -> Optional[str]:
    lines = [l.strip() for l in body.split("\n")]
    for i, line in enumerate(lines):
        if _SIGNOFF_RE.match(line):
            for nxt in lines[i + 1:]:
                if not nxt:
                    continue
                if len(nxt.split()) <= 4 and not re.search(r"[\d@]", nxt):
                    return nxt
                break
    return None


# --------------------------------------------------------------- validation

def validate(ex: Extraction, source_text: Optional[str] = None) -> list[Issue]:
    """Checks shared by every extractor. Returns NEW issues (does not mutate)."""
    out: list[Issue] = []
    if not ex.client_email:
        out.append(Issue("client_email", "error", "No client email found; PayPal needs a recipient email to send an invoice."))
    elif not EMAIL_RE.fullmatch(ex.client_email):
        out.append(Issue("client_email", "error", f"Malformed email {ex.client_email!r}."))
    elif source_text is not None and ex.client_email.lower() not in source_text.lower():
        out.append(Issue("client_email", "error", f"{ex.client_email} does not appear in the source text (possible hallucination)."))
    if not ex.client_name:
        out.append(Issue("client_name", "warning", "No client name found."))
    if not ex.line_items:
        out.append(Issue("line_items", "error", "No priced line items found."))
    for n, li in enumerate(ex.line_items):
        if li.qty is not None and li.qty <= 0:
            out.append(Issue(f"line_items[{n}].qty", "error", "Quantity must be positive."))
        if li.unit_price <= 0:
            out.append(Issue(f"line_items[{n}].unit_price", "error", "Unit price must be positive."))
        if li.currency in ZERO_DECIMAL_CURRENCIES and li.unit_price != li.unit_price.to_integral_value():
            out.append(Issue(f"line_items[{n}].unit_price", "error", f"{li.currency} does not support decimals on PayPal."))
        if not li.currency:
            out.append(Issue(f"line_items[{n}].currency", "error", "Currency unknown for this item."))
    ccys = ex.currencies()
    if len(ccys) > 1:
        out.append(Issue("currency", "warning",
                         f"Multiple currencies {ccys}; a PayPal invoice has one currency_code, so this will be split into {len(ccys)} invoices."))
    if ex.currency and ex.currency not in PAYPAL_CURRENCIES:
        out.append(Issue("currency", "error", f"{ex.currency} is not a PayPal-supported currency."))
    if ex.due_days is not None and not (0 <= ex.due_days <= 365):
        out.append(Issue("due_days", "error", f"Implausible payment term: {ex.due_days} days."))
    if ex.amount_paid > 0:
        if len(ccys) > 1:
            out.append(Issue("amount_paid", "error", "Prior payment reported on a multi-currency job; assign it manually."))
        elif ex.line_items and ex.amount_paid >= ex.total():
            out.append(Issue("amount_paid", "error", f"Reported payment {ex.amount_paid} >= invoice total {ex.total()}."))
    return out


# ------------------------------------------------------------ rules extractor

class RulesExtractor:
    name = "rules"

    def __init__(self, default_due_days: int = 30):
        self.default_due_days = default_due_days

    def extract(self, text: str) -> Extraction:
        headers, body = _split_headers(text)
        live = "\n".join(l for l in body.split("\n") if not l.lstrip().startswith(">"))  # ignore quoted thread
        issues: list[Issue] = []

        name, email = _parse_address(headers.get("from", ""))
        _, to_email = _parse_address(headers.get("to", ""))
        billing = _BILLING_RE.search(live)
        if billing:
            b = billing.group(1).rstrip(".").lower()
            if email and b != email:
                issues.append(Issue("client_email", "info", f"Billing address {b} differs from sender {email}; using billing address."))
            email = b
        if not email:
            found = [e.lower() for e in EMAIL_RE.findall(live) if e.lower() != (to_email or "")]
            if found:
                email = found[0]
                issues.append(Issue("client_email", "info", f"Client email {email} taken from message body."))
        if not name:
            name = _signature_name(live)
            if name:
                issues.append(Issue("client_name", "info", "Client name taken from signature."))

        doc_ccy_m = _DOC_CCY_RE.search(live)
        doc_ccy = doc_ccy_m.group(1).upper() if doc_ccy_m else None

        items, paid, stated_totals, item_issues = self._line_items(live, doc_ccy)
        issues += item_issues

        ccy_counts = Counter(li.currency for li in items if li.currency)
        currency = ccy_counts.most_common(1)[0][0] if ccy_counts else doc_ccy

        due_days = self._due_days(live)
        if due_days is None:
            due_days = self.default_due_days
            issues.append(Issue("due_days", "warning", f"No payment terms found; defaulted to Net {self.default_due_days}."))

        ex = Extraction(name, email, currency, items, due_days, paid, source=self.name)
        if paid > 0:
            issues.append(Issue("amount_paid", "info", f"Client reports {paid} already paid; will be recorded against the invoice after approval."))
        for ccy, amt in stated_totals:
            if items and (ccy in (None, currency)) and len(ex.currencies()) <= 1:
                if amt not in (ex.total(), ex.total() - paid):
                    issues.append(Issue("line_items", "warning", f"Stated total/budget {amt} differs from computed total {ex.total()}."))
            elif not items:
                issues.append(Issue("line_items", "info", f"Message mentions a total/budget of {ccy or ''} {amt} but no itemised work."))
        ex.issues = issues + validate(ex, text)
        ex.confidence = compute_confidence(ex.issues)
        return ex

    def _due_days(self, text: str) -> Optional[int]:
        if _DUE_ON_RECEIPT_RE.search(text):
            return 0
        for pat in _DUE_PATTERNS:
            m = pat.search(text)
            if m:
                return int(m.group(1))
        return None

    def _line_items(self, body: str, doc_ccy: Optional[str]):
        lines = body.split("\n")
        items: list[LineItem] = []
        issues: list[Issue] = []
        stated: list[tuple[Optional[str], Decimal]] = []
        paid = Decimal(0)

        t_items, consumed, t_issues, t_totals = self._table(lines, doc_ccy)
        items += t_items
        issues += t_issues
        stated += t_totals

        for idx, raw in enumerate(lines):
            if idx in consumed:
                continue
            line = _BULLET_RE.sub("", raw).strip()
            if not line:
                continue
            monies = list(MONEY_RE.finditer(line))
            if not monies:
                continue
            ccy, amt, tok = parse_money(monies[0])
            if _PAID_RE.search(line):
                paid += amt
                continue
            if _TOTAL_RE.search(line):
                stated.append((ccy, amt))
                continue
            item, reason = self._item_from_line(line, monies[0])
            if item is None:
                issues.append(Issue("line_items", "warning", f"Could not parse priced line: {line!r}"))
                continue
            item.currency = ccy or doc_ccy
            if tok == "$" and doc_ccy and doc_ccy in DOLLAR_CURRENCIES and doc_ccy != "USD":
                item.currency = doc_ccy
                issues.append(Issue(f"line_items[{len(items)}].currency", "warning", f"'$' interpreted as {doc_ccy} per the email."))
            if reason:
                sev = "error" if item.qty is None else "warning"
                issues.append(Issue(f"line_items[{len(items)}].qty", sev, reason))
            items.append(item)
        return items, paid, stated, issues

    @staticmethod
    def _item_from_line(line: str, m: re.Match) -> tuple[Optional[LineItem], Optional[str]]:
        s = line[: m.start()] + "<M>" + line[m.end():]
        _, price, _ = parse_money(m)
        for pat in _ITEM_PATTERNS:
            pm = pat.search(s)
            if not pm:
                continue
            desc = pm.group("desc").strip().rstrip(" :–—-,")
            if not desc or len(desc.split()) > 12:
                continue
            gd = pm.groupdict()
            qty, reason = (Decimal(1), None) if gd.get("qty") is None else parse_qty(gd["qty"])
            unit = gd.get("unit")
            desc = desc[0].upper() + desc[1:]
            return LineItem(desc=desc, qty=qty, unit_price=price, unit=unit), reason
        return None, None

    @staticmethod
    def _table(lines: list[str], doc_ccy: Optional[str]):
        items: list[LineItem] = []
        consumed: set[int] = set()
        issues: list[Issue] = []
        totals: list[tuple[Optional[str], Decimal]] = []
        rows = [(i, [c.strip() for c in l.strip().strip("|").split("|")]) for i, l in enumerate(lines) if l.count("|") >= 2]
        header = None
        for i, cells in rows:
            low = [c.lower() for c in cells]
            if header is None:
                if any(c in ("qty", "quantity", "hours", "hrs") for c in low):
                    def col(*names):
                        return next((k for k, c in enumerate(low) if any(n in c for n in names)), None)
                    header = {
                        "desc": col("item", "description", "service", "task") or 0,
                        "qty": col("qty", "quantity", "hours", "hrs"),
                        "price": col("unit price", "price", "rate", "unit"),
                    }
                    consumed.add(i)
                continue
            consumed.add(i)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            try:
                desc = cells[header["desc"]]
                raw_price = cells[header["price"]] if header["price"] is not None else ""
                raw_qty = cells[header["qty"]] if header["qty"] is not None else "1"
            except IndexError:
                issues.append(Issue("line_items", "warning", f"Malformed table row: {lines[i].strip()!r}"))
                continue
            mm = MONEY_RE.search(raw_price)
            if mm:
                ccy, price, tok = parse_money(mm)
                if tok == "$" and doc_ccy and doc_ccy in DOLLAR_CURRENCIES and doc_ccy != "USD":
                    ccy = doc_ccy
            else:
                bare = re.search(_NUM, raw_price)
                if not bare:
                    issues.append(Issue("line_items", "warning", f"No price in table row: {lines[i].strip()!r}"))
                    continue
                ccy, price = None, _dec(bare.group(0))
            if _TOTAL_RE.search(desc):
                totals.append((ccy or doc_ccy, price))
                continue
            qty, reason = parse_qty(raw_qty)
            if reason:
                issues.append(Issue(f"line_items[{len(items)}].qty", "error" if qty is None else "warning", reason))
            items.append(LineItem(desc=desc, qty=qty, unit_price=price, currency=ccy or doc_ccy))
        return items, consumed, issues, totals


# ------------------------------------------------------------- LLM extractor

LLM_PROMPT = """You extract invoice data from a freelancer's job email.
Return ONLY a JSON object, no prose, matching:
{"client_name": string|null, "client_email": string|null, "currency": ISO-4217 string|null,
 "line_items": [{"desc": string, "qty": number|null, "unit_price": number, "currency": string|null}],
 "due_days": integer|null, "amount_paid": number, "confidence": number 0..1,
 "issues": [{"field": string, "severity": "error"|"warning"|"info", "message": string}]}
Rules: never invent an email address or price that is not in the text; use null and add an
issue instead. Quoted earlier messages (lines starting with '>') are history, not scope.
If a deposit/partial payment was already made, put it in amount_paid.

EMAIL:
<<<
{text}
>>>"""


def _strip_fence(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s


class LLMExtractor:
    """Model-agnostic: inject any `complete(prompt) -> str` (OpenAI, Anthropic, local...).

    Output is never trusted blindly: it goes through the same `validate()` as the rules
    extractor plus a grounding check (email must literally appear in the source text).
    """

    name = "llm"

    def __init__(self, complete: Callable[[str], str]):
        self.complete = complete

    def extract(self, text: str) -> Extraction:
        raw = self.complete(LLM_PROMPT.replace("{text}", text))
        try:
            data = json.loads(_strip_fence(raw))
            if not isinstance(data, dict):
                raise ValueError("not an object")
            model_issues = data.pop("issues", []) or []
            model_conf = float(data.pop("confidence", 0.5))
            ex = Extraction.from_dict(data)
            ex.issues = [Issue(**i) for i in model_issues if isinstance(i, dict) and {"field", "severity", "message"} <= set(i)]
        except (ValueError, TypeError, KeyError) as e:
            bad = Extraction(None, None, None, [], None, source=self.name,
                             issues=[Issue("*", "error", f"LLM output unusable: {e}")])
            bad.confidence = 0.0
            return bad
        ex.source = self.name
        if ex.client_email:
            ex.client_email = ex.client_email.lower()
        for li in ex.line_items:
            li.currency = li.currency or ex.currency
        if ex.currency is None and ex.currencies():
            ex.currency = Counter(li.currency for li in ex.line_items).most_common(1)[0][0]
        v = validate(ex, text)
        if any(i.field == "client_email" and "hallucination" in i.message for i in v):
            ex.client_email = None
        ex.issues += v
        ex.confidence = min(round(model_conf, 2), compute_confidence(ex.issues))
        return ex


class HybridExtractor:
    """Rules first (free, deterministic); LLM only when rules confidence < threshold."""

    name = "hybrid"

    def __init__(self, primary: Extractor, fallback: Optional[Extractor] = None, threshold: float = 0.75):
        self.primary, self.fallback, self.threshold = primary, fallback, threshold

    def extract(self, text: str) -> Extraction:
        first = self.primary.extract(text)
        if first.confidence >= self.threshold or self.fallback is None:
            return first
        second = self.fallback.extract(text)
        best, other = (second, first) if second.confidence > first.confidence else (first, second)
        best.issues.append(Issue("*", "info",
                                 f"Hybrid: chose {best.source} ({best.confidence}) over {other.source} ({other.confidence})."))
        if first.client_email and second.client_email and first.client_email != second.client_email:
            best.issues.append(Issue("client_email", "warning",
                                     f"Extractors disagree on email: {first.client_email} vs {second.client_email}."))
            best.confidence = compute_confidence(best.issues) if best.source == "rules" else min(best.confidence, compute_confidence(best.issues))
        return best


def split_by_currency(ex: Extraction) -> list[Extraction]:
    """One Extraction per currency (PayPal invoices carry a single currency_code)."""
    ccys = ex.currencies()
    if len(ccys) <= 1:
        return [ex]
    parts = []
    for c in ccys:
        parts.append(Extraction(
            ex.client_name, ex.client_email, c,
            [li for li in ex.line_items if li.currency == c], ex.due_days,
            Decimal(0), [i for i in ex.issues if i.field != "currency"], ex.confidence, ex.source,
        ))
    return parts
