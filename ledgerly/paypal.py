"""PayPal Invoicing v2 client interface + an offline `SandboxMock`.

Nothing in this module talks to the network unless you construct `HttpPayPalClient`
yourself AND set LEDGERLY_ALLOW_NETWORK=1. Tests and the demo only use `SandboxMock`.

Shapes below were written from the PayPal developer docs (field names, enums, status
codes). Where I was not certain of an exact detail it is marked "ASSUMPTION" - verify
against the sandbox before relying on it.

Docs used:
  Invoicing v2 API reference ........ https://developer.paypal.com/docs/api/invoicing/v2/
    - Create draft invoice  POST /v2/invoicing/invoices
    - Send invoice          POST /v2/invoicing/invoices/{invoice_id}/send
    - Send reminder         POST /v2/invoicing/invoices/{invoice_id}/remind
    - Show invoice details  GET  /v2/invoicing/invoices/{invoice_id}
    - Record payment        POST /v2/invoicing/invoices/{invoice_id}/payments
    - Generate inv. number  POST /v2/invoicing/generate-next-invoice-number
  Invoicing integration guide ....... https://developer.paypal.com/docs/invoicing/
  Webhooks overview ................. https://developer.paypal.com/api/rest/webhooks/
  Webhook event names (INVOICING.*) . https://developer.paypal.com/api/rest/webhooks/event-names/
  Verify webhook signature .......... https://developer.paypal.com/docs/api/webhooks/v1/#verify-webhook-signature_post
  OAuth 2.0 access token ............ https://developer.paypal.com/api/rest/authentication/
  Sandbox base URL / environments ... https://developer.paypal.com/api/rest/sandbox/
  Currency codes .................... https://developer.paypal.com/api/rest/reference/currency-codes/
  Error response format ............. https://developer.paypal.com/api/rest/responses/
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from typing import Any, Callable, Optional, Protocol

from .extract import Extraction, quantize

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE = "https://api-m.paypal.com"

# Invoice status enum (Invoicing v2 `detail.status` / top-level `status`).
STATUSES = {
    "DRAFT", "SENT", "SCHEDULED", "PAID", "MARKED_AS_PAID", "CANCELLED", "REFUNDED",
    "PARTIALLY_PAID", "PARTIALLY_REFUNDED", "MARKED_AS_REFUNDED", "UNPAID", "PAYMENT_PENDING",
}
PAID_STATUSES = {"PAID", "MARKED_AS_PAID"}
OPEN_STATUSES = {"SENT", "UNPAID", "PARTIALLY_PAID", "PAYMENT_PENDING"}

# payment_term.term_type enum.
TERM_TYPES = {0: "DUE_ON_RECEIPT", 10: "NET_10", 15: "NET_15", 30: "NET_30", 45: "NET_45", 60: "NET_60", 90: "NET_90"}

# Webhook event types for invoicing (event-names page above).
EVT_PAID = "INVOICING.INVOICE.PAID"
INVOICING_EVENTS = {
    "INVOICING.INVOICE.CREATED", "INVOICING.INVOICE.UPDATED", "INVOICING.INVOICE.PAID",
    "INVOICING.INVOICE.CANCELLED", "INVOICING.INVOICE.REFUNDED", "INVOICING.INVOICE.SCHEDULED",
}


class PayPalError(Exception):
    """Mirrors the REST error body: {name, message, debug_id, details[{issue, description}]}."""

    def __init__(self, http_status: int, name: str, message: str, issue: str | None = None, description: str = ""):
        self.http_status = http_status
        self.body = {
            "name": name,
            "message": message,
            "debug_id": uuid.uuid4().hex[:13],
            "details": [{"issue": issue, "description": description}] if issue else [],
        }
        super().__init__(f"{http_status} {name}: {message}" + (f" [{issue}]" if issue else ""))


@dataclass
class Response:
    status: int
    body: Any


class InvoicingClient(Protocol):
    """Subset of Invoicing v2 used by Ledgerly. Bodies are plain dicts in PayPal's JSON shape."""

    def generate_next_invoice_number(self) -> Response: ...
    def create_draft_invoice(self, invoice: dict, prefer_representation: bool = False) -> Response: ...
    def send_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response: ...
    def remind_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response: ...
    def get_invoice(self, invoice_id: str) -> Response: ...
    def record_payment(self, invoice_id: str, body: dict) -> Response: ...


# --------------------------------------------------------------- builders

def _money(value: Decimal, ccy: str) -> dict:
    return {"currency_code": ccy, "value": str(quantize(Decimal(value), ccy))}


def _split_name(full: Optional[str]) -> dict:
    if not full:
        return {}
    parts = full.split()
    if len(parts) == 1:
        return {"given_name": parts[0]}
    return {"given_name": " ".join(parts[:-1]), "surname": parts[-1]}


def payment_term(due_days: Optional[int], invoice_date: date) -> dict:
    if due_days is None:
        return {"term_type": "NO_DUE_DATE"}
    if due_days == 0:
        # Receipt is a future event while the invoice is still a draft.
        return {"term_type": "DUE_ON_RECEIPT"}
    if due_days in TERM_TYPES:
        term = {"term_type": TERM_TYPES[due_days]}
    else:
        term = {"term_type": "DUE_ON_DATE_SPECIFIED"}
    # due_date is accepted alongside NET_* terms; ASSUMPTION: PayPal recomputes it for NET_*.
    term["due_date"] = (invoice_date + timedelta(days=due_days)).isoformat()
    return term


def build_invoice(ex: Extraction, invoicer: dict, invoice_number: str, invoice_date: date,
                  note: str = "", allow_partial: bool = False) -> dict:
    """Extraction -> Invoicing v2 create-draft request body. Single-currency only."""
    ccy = ex.currency
    if not ccy or len(ex.currencies()) > 1:
        raise ValueError("build_invoice needs exactly one currency; use extract.split_by_currency first")
    items = []
    for li in ex.line_items:
        uom = "HOURS" if (li.unit or "").lower().startswith(("h", "hr")) else "QUANTITY"
        items.append({
            "name": li.desc[:200],
            "quantity": str(li.qty),
            "unit_amount": _money(li.unit_price, ccy),
            "unit_of_measure": uom,
        })
    inv = {
        "detail": {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date.isoformat(),
            "currency_code": ccy,
            "note": note or "Thank you for your business.",
            "payment_term": payment_term(ex.due_days, invoice_date),
        },
        "invoicer": {
            "name": _split_name(invoicer.get("name")),
            "email_address": invoicer["email_address"],
        },
        "primary_recipients": [{
            "billing_info": {"name": _split_name(ex.client_name), "email_address": ex.client_email},
        }],
        "items": items,
        "configuration": {
            "partial_payment": {"allow_partial_payment": allow_partial},
            "allow_tip": False,
            "tax_calculated_after_discount": True,
            "tax_inclusive": False,
        },
    }
    if not inv["primary_recipients"][0]["billing_info"]["name"]:
        del inv["primary_recipients"][0]["billing_info"]["name"]
    return inv


# --------------------------------------------------------------- mock

class SandboxMock:
    """In-memory stand-in for api-m.sandbox.paypal.com Invoicing v2.

    * Same request/response JSON shapes and HTTP status codes as the docs.
    * Enforces the state machine: only DRAFT can be sent; reminders only for open invoices.
    * `simulate_payer_payment()` plays the payer side and returns a webhook event dict.
    * `requests` is an audit log of every call (used by tests to prove nothing was sent).
    """

    def __init__(self, now: Callable[[], datetime] | None = None, webhook_secret: str = "mock-webhook-secret"):
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.invoices: dict[str, dict] = {}
        self.requests: list[tuple[str, str, Any]] = []
        self._seq = 0
        self.webhook_secret = webhook_secret
        self.webhook_id = "WH-MOCK-" + "0" * 8

    # -- helpers
    def _log(self, method: str, path: str, body: Any = None) -> None:
        self.requests.append((method, path, copy.deepcopy(body)))

    def _get(self, invoice_id: str) -> dict:
        inv = self.invoices.get(invoice_id)
        if inv is None:
            raise PayPalError(404, "RESOURCE_NOT_FOUND", "The specified resource does not exist.",
                              "INVALID_RESOURCE_ID", "Requested invoice does not exist.")
        return inv

    def _href(self, invoice_id: str) -> dict:
        return {"rel": "self", "href": f"{SANDBOX_BASE}/v2/invoicing/invoices/{invoice_id}", "method": "GET"}

    def _ts(self) -> str:
        return self._now().strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _total(inv: dict) -> Decimal:
        return sum((Decimal(i["quantity"]) * Decimal(i["unit_amount"]["value"]) for i in inv["items"]), Decimal(0))

    def _recalc(self, inv: dict) -> None:
        ccy = inv["detail"]["currency_code"]
        total = self._total(inv)
        paid = sum((Decimal(t["amount"]["value"]) for t in inv["payments"].get("transactions", [])), Decimal(0))
        inv["amount"] = {"currency_code": ccy, "value": str(quantize(total, ccy)),
                         "breakdown": {"item_total": _money(total, ccy)}}
        inv["payments"]["paid_amount"] = _money(paid, ccy)
        inv["due_amount"] = _money(max(total - paid, Decimal(0)), ccy)

    # -- API
    def generate_next_invoice_number(self) -> Response:
        self._log("POST", "/v2/invoicing/generate-next-invoice-number")
        return Response(200, {"invoice_number": f"LDG-{len(self.invoices) + 1:04d}"})

    def create_draft_invoice(self, invoice: dict, prefer_representation: bool = False) -> Response:
        self._log("POST", "/v2/invoicing/invoices", invoice)
        recips = invoice.get("primary_recipients") or []
        email = recips[0].get("billing_info", {}).get("email_address") if recips else None
        if not invoice.get("detail", {}).get("currency_code"):
            raise PayPalError(400, "INVALID_REQUEST", "Request is not well-formed, syntactically incorrect, or violates schema.",
                              "MISSING_REQUIRED_PARAMETER", "detail.currency_code is required.")
        for i in invoice.get("items", []):
            if i["unit_amount"]["currency_code"] != invoice["detail"]["currency_code"]:
                raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                                  "CURRENCY_MISMATCH", "Item currency must match invoice currency.")
        self._seq += 1
        inv_id = f"INV2-MOCK-{self._seq:04d}-{uuid.uuid4().hex[:4].upper()}"
        inv = copy.deepcopy(invoice)
        inv["id"] = inv_id
        inv["status"] = "DRAFT"
        inv["detail"]["metadata"] = {"create_time": self._ts(), "recipient_view_url": None, "invoicer_view_url": None}
        inv["payments"] = {"transactions": []}
        inv["_has_recipient_email"] = bool(email)  # mock-internal, stripped from responses
        self._recalc(inv)
        self.invoices[inv_id] = inv
        if prefer_representation:  # header `Prefer: return=representation`
            return Response(201, self._public(inv))
        return Response(201, self._href(inv_id))  # default: HATEOAS link to the new invoice

    def send_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        body = body or {"send_to_invoicer": True, "send_to_recipient": True}
        self._log("POST", f"/v2/invoicing/invoices/{invoice_id}/send", body)
        inv = self._get(invoice_id)
        if inv["status"] != "DRAFT":
            # ASSUMPTION: exact issue code for re-sending a non-draft invoice.
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                              "INVALID_INVOICE_STATUS", f"Invoice in status {inv['status']} cannot be sent.")
        if body.get("send_to_recipient", True) and not inv["_has_recipient_email"]:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                              "MISSING_RECIPIENT_EMAIL", "Recipient email is required to send.")
        sent_time = self._ts()
        inv["status"] = "SENT"
        meta = inv["detail"]["metadata"]
        meta["last_sent_time"] = sent_time
        term = inv["detail"].get("payment_term")
        if isinstance(term, dict) and term.get("term_type") == "DUE_ON_RECEIPT":
            # Mock convention: a successful send is receipt. Preserve explicit dates.
            term.setdefault("due_date", sent_time[:10])
        meta["recipient_view_url"] = f"https://www.sandbox.paypal.com/invoice/p/#{invoice_id}"
        meta["invoicer_view_url"] = f"https://www.sandbox.paypal.com/invoice/details/{invoice_id}"
        return Response(200, {"href": meta["recipient_view_url"], "rel": "payer-view", "method": "GET"})

    def remind_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        self._log("POST", f"/v2/invoicing/invoices/{invoice_id}/remind", body)
        inv = self._get(invoice_id)
        if inv["status"] not in OPEN_STATUSES:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                              "INVALID_INVOICE_STATUS", f"Cannot remind invoice in status {inv['status']}.")
        inv["detail"]["metadata"]["last_reminder_time"] = self._ts()
        return Response(204, None)

    def get_invoice(self, invoice_id: str) -> Response:
        self._log("GET", f"/v2/invoicing/invoices/{invoice_id}")
        return Response(200, self._public(self._get(invoice_id)))

    def record_payment(self, invoice_id: str, body: dict) -> Response:
        """Record an external (non-PayPal) payment, e.g. a bank-transfer deposit."""
        self._log("POST", f"/v2/invoicing/invoices/{invoice_id}/payments", body)
        inv = self._get(invoice_id)
        if inv["status"] in PAID_STATUSES | {"CANCELLED", "DRAFT"}:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                              "INVALID_INVOICE_STATUS", f"Cannot record payment on {inv['status']} invoice.")
        pid = "EXTR-" + uuid.uuid4().hex[:12].upper()
        self._apply_payment(inv, pid, Decimal(body["amount"]["value"]), body.get("method", "BANK_TRANSFER"),
                            body.get("payment_date", self._now().date().isoformat()), external=True)
        return Response(200, {"payment_id": pid})

    def _apply_payment(self, inv: dict, pid: str, amount: Decimal, method: str, pdate: str, external: bool) -> None:
        ccy = inv["detail"]["currency_code"]
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Sandbox payment amount must be a finite number greater than zero.")
        try:
            money = _money(amount, ccy)
        except DecimalException as exc:
            raise ValueError(f"Sandbox payment amount cannot be represented in {ccy}.") from exc
        if Decimal(money["value"]) != amount:
            raise ValueError(f"Sandbox payment amount must be exact in {ccy}; it cannot be rounded.")

        # Recalculation can still fail after admission. Prepare every changed
        # invoice field before committing the payment to this retained record.
        staged = copy.deepcopy(inv)
        staged["payments"]["transactions"].append({
            "payment_id": pid, "type": "EXTERNAL" if external else "PAYPAL", "method": method,
            "payment_date": pdate, "amount": money,
        })
        try:
            self._recalc(staged)
            due = Decimal(staged["due_amount"]["value"])
            if due <= 0:
                staged["status"] = "MARKED_AS_PAID" if external else "PAID"
            else:
                staged["status"] = "PARTIALLY_PAID"
        except DecimalException as exc:
            raise ValueError("Sandbox payment could not be calculated; the invoice was not changed.") from exc
        inv.update({key: staged[key] for key in ("payments", "amount", "due_amount", "status")})

    def _public(self, inv: dict) -> dict:
        out = copy.deepcopy(inv)
        out.pop("_has_recipient_email", None)
        out["links"] = [self._href(inv["id"])]
        return out

    # -- payer simulation + webhooks
    def simulate_payer_payment(self, invoice_id: str, amount: Optional[Decimal] = None) -> dict:
        """Payer pays through the PayPal-hosted invoice page. Returns the webhook event.

        ASSUMPTION: PayPal emits INVOICING.INVOICE.PAID for partial payments too, with
        resource.invoice.status == PARTIALLY_PAID. Ledgerly keys off the status field, not
        the event name, so it is robust either way.
        """
        inv = self._get(invoice_id)
        if inv["status"] not in OPEN_STATUSES:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "The requested action could not be performed.",
                              "INVALID_INVOICE_STATUS", f"Invoice {inv['status']} is not payable.")
        amt = Decimal(inv["due_amount"]["value"]) if amount is None else Decimal(amount)
        self._apply_payment(inv, uuid.uuid4().hex[:17].upper(), amt, "PAYPAL", self._now().date().isoformat(), external=False)
        return self.make_webhook_event(EVT_PAID, invoice_id)

    def make_webhook_event(self, event_type: str, invoice_id: str) -> dict:
        inv = self._public(self._get(invoice_id))
        inv.pop("links", None)
        return {
            "id": "WH-" + uuid.uuid4().hex[:17].upper() + "-" + uuid.uuid4().hex[:17].upper(),
            "event_version": "1.0",
            "create_time": self._ts(),
            "resource_type": "invoices",
            "event_type": event_type,
            "summary": "An invoice was paid" if event_type == EVT_PAID else event_type,
            "resource": {"invoice": inv},
            "links": [
                {"href": f"{SANDBOX_BASE}/v1/notifications/webhooks-events/WH-MOCK", "rel": "self", "method": "GET"},
                {"href": f"{SANDBOX_BASE}/v1/notifications/webhooks-events/WH-MOCK/resend", "rel": "resend", "method": "POST"},
            ],
        }

    def sign(self, raw_body: bytes, transmission_id: str = "mock-tx", ts: str | None = None) -> dict:
        """Mock transmission headers. Real PayPal signs with a cert (PAYPAL-CERT-URL);
        we use HMAC so verification is testable offline. Same header names."""
        ts = ts or self._ts()
        crc = format(_crc32(raw_body), "d")
        msg = f"{transmission_id}|{ts}|{self.webhook_id}|{crc}".encode()
        sig = base64.b64encode(hmac.new(self.webhook_secret.encode(), msg, hashlib.sha256).digest()).decode()
        return {
            "PAYPAL-TRANSMISSION-ID": transmission_id,
            "PAYPAL-TRANSMISSION-TIME": ts,
            "PAYPAL-TRANSMISSION-SIG": sig,
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-CERT-URL": f"{SANDBOX_BASE}/v1/notifications/certs/CERT-MOCK",
        }

    def verify_webhook_signature(self, headers: dict, raw_body: bytes) -> dict:
        """Mock of POST /v1/notifications/verify-webhook-signature -> {verification_status}."""
        h = {k.upper(): v for k, v in headers.items()}
        try:
            msg = f"{h['PAYPAL-TRANSMISSION-ID']}|{h['PAYPAL-TRANSMISSION-TIME']}|{self.webhook_id}|{_crc32(raw_body)}".encode()
        except KeyError:
            return {"verification_status": "FAILURE"}
        want = base64.b64encode(hmac.new(self.webhook_secret.encode(), msg, hashlib.sha256).digest()).decode()
        ok = hmac.compare_digest(want, h.get("PAYPAL-TRANSMISSION-SIG", ""))
        return {"verification_status": "SUCCESS" if ok else "FAILURE"}


def _crc32(b: bytes) -> int:
    import zlib
    return zlib.crc32(b) & 0xFFFFFFFF


# --------------------------------------------------------------- webhook parsing

@dataclass
class InvoiceEvent:
    event_id: str
    event_type: str
    invoice_id: str
    status: str
    currency: Optional[str]
    paid_amount: Optional[Decimal]
    due_amount: Optional[Decimal]
    create_time: Optional[str]

    @property
    def is_fully_paid(self) -> bool:
        return self.status in PAID_STATUSES


class WebhookError(ValueError):
    pass


def parse_webhook_event(event: dict | str | bytes) -> InvoiceEvent:
    """Parse an INVOICING.INVOICE.* webhook body. Signature verification is separate."""
    if isinstance(event, (str, bytes)):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as e:
            raise WebhookError(f"invalid JSON: {e}") from e
    if not isinstance(event, dict):
        raise WebhookError("event must be an object")
    et = event.get("event_type")
    if et not in INVOICING_EVENTS:
        raise WebhookError(f"unsupported event_type {et!r}")
    res = event.get("resource") or {}
    inv = res.get("invoice", res)  # docs show resource.invoice; tolerate a bare invoice too
    inv_id = inv.get("id")
    if not inv_id:
        raise WebhookError("resource.invoice.id missing")
    status = inv.get("status") or (inv.get("detail") or {}).get("status")
    if status not in STATUSES:
        raise WebhookError(f"unknown invoice status {status!r}")
    if et == EVT_PAID and status not in PAID_STATUSES | {"PARTIALLY_PAID"}:
        raise WebhookError(f"{EVT_PAID} with non-paid status {status}")
    pa = (inv.get("payments") or {}).get("paid_amount")
    da = inv.get("due_amount")
    return InvoiceEvent(
        event_id=event.get("id", ""),
        event_type=et,
        invoice_id=inv_id,
        status=status,
        currency=(inv.get("detail") or {}).get("currency_code"),
        paid_amount=Decimal(pa["value"]) if pa else None,
        due_amount=Decimal(da["value"]) if da else None,
        create_time=event.get("create_time"),
    )


# --------------------------------------------------------------- live client (unused offline)

class HttpPayPalClient:
    """Thin urllib client for the real sandbox. NOT exercised by tests.

    Refuses to run unless LEDGERLY_ALLOW_NETWORK=1, so a stray import can never hit PayPal.
    Credentials come from the caller (env PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET) - never
    hard-code them.
    """

    def __init__(self, client_id: str, client_secret: str, base_url: str = SANDBOX_BASE):
        if os.environ.get("LEDGERLY_ALLOW_NETWORK") != "1":
            raise RuntimeError("Network disabled. Set LEDGERLY_ALLOW_NETWORK=1 to use the real sandbox.")
        self.base, self._cid, self._sec = base_url, client_id, client_secret
        self._token: Optional[str] = None

    def _auth(self) -> str:
        import urllib.request
        if self._token:
            return self._token
        req = urllib.request.Request(
            self.base + "/v1/oauth2/token", data=b"grant_type=client_credentials", method="POST",
            headers={"Authorization": "Basic " + base64.b64encode(f"{self._cid}:{self._sec}".encode()).decode(),
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=20) as r:
            self._token = json.load(r)["access_token"]
        return self._token

    def _call(self, method: str, path: str, body: Any = None, extra: dict | None = None) -> Response:
        import urllib.error
        import urllib.request
        headers = {"Authorization": f"Bearer {self._auth()}", "Content-Type": "application/json",
                   "PayPal-Request-Id": uuid.uuid4().hex, **(extra or {})}
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return Response(r.status, json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            b = json.loads(e.read() or b"{}")
            d = (b.get("details") or [{}])[0]
            raise PayPalError(e.code, b.get("name", "HTTP_ERROR"), b.get("message", str(e)), d.get("issue"), d.get("description", ""))

    def generate_next_invoice_number(self) -> Response:
        return self._call("POST", "/v2/invoicing/generate-next-invoice-number")

    def create_draft_invoice(self, invoice: dict, prefer_representation: bool = False) -> Response:
        return self._call("POST", "/v2/invoicing/invoices", invoice,
                          {"Prefer": "return=representation"} if prefer_representation else None)

    def send_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        return self._call("POST", f"/v2/invoicing/invoices/{invoice_id}/send", body or {"send_to_invoicer": True})

    def remind_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        return self._call("POST", f"/v2/invoicing/invoices/{invoice_id}/remind", body or {})

    def get_invoice(self, invoice_id: str) -> Response:
        return self._call("GET", f"/v2/invoicing/invoices/{invoice_id}")

    def record_payment(self, invoice_id: str, body: dict) -> Response:
        return self._call("POST", f"/v2/invoicing/invoices/{invoice_id}/payments", body)

    def verify_webhook_signature(self, headers: dict, raw_body: bytes, webhook_id: str) -> dict:
        h = {k.upper(): v for k, v in headers.items()}
        body = {
            "auth_algo": h["PAYPAL-AUTH-ALGO"], "cert_url": h["PAYPAL-CERT-URL"],
            "transmission_id": h["PAYPAL-TRANSMISSION-ID"], "transmission_sig": h["PAYPAL-TRANSMISSION-SIG"],
            "transmission_time": h["PAYPAL-TRANSMISSION-TIME"], "webhook_id": webhook_id,
            "webhook_event": json.loads(raw_body),
        }
        return self._call("POST", "/v1/notifications/verify-webhook-signature", body).body
