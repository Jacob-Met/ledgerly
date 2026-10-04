"""Ledgerly agent: tool loop + human approval gate + overdue reminders.

Safety model
------------
* The planner (an LLM, or the deterministic `RulePlanner`) can only call the tools in
  `Agent.TOOLS`: create_invoice, get_status, send_reminder, list_overdue.
  None of them move money or send email. Outgoing actions are *queued* as
  `PendingAction`s.
* `approve(action_id)` is NOT a tool. Only the human-facing surface (CLI / UI / test)
  calls it.
* Defence in depth: the PayPal client is wrapped in `GatedClient`, which raises
  `ApprovalRequired` for send / remind / record-payment unless `approve()` has opened a
  one-shot permit for that exact (operation, invoice_id). So even a buggy tool or a
  prompt-injected planner cannot send.
"""
from __future__ import annotations

import contextlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional, Protocol

from .extract import Extraction, Extractor, RulesExtractor, split_by_currency
from .paypal import (
    OPEN_STATUSES, PAID_STATUSES, InvoicingClient, PayPalError, Response, WebhookError,
    build_invoice, parse_webhook_event,
)

GATED_OPS = {"send_invoice", "remind_invoice", "record_payment"}


class ApprovalRequired(PermissionError):
    pass


class GatedClient:
    """Wraps an InvoicingClient; outgoing operations need a one-shot permit."""

    def __init__(self, inner: InvoicingClient):
        self._inner = inner
        self._permits: set[tuple[str, str]] = set()
        self.blocked: list[tuple[str, str]] = []

    @contextlib.contextmanager
    def permit(self, op: str, invoice_id: str):
        key = (op, invoice_id)
        self._permits.add(key)
        try:
            yield
        finally:
            self._permits.discard(key)

    def _check(self, op: str, invoice_id: str) -> None:
        if (op, invoice_id) not in self._permits:
            self.blocked.append((op, invoice_id))
            raise ApprovalRequired(f"{op}({invoice_id}) requires human approval")

    def send_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        self._check("send_invoice", invoice_id)
        return self._inner.send_invoice(invoice_id, body)

    def remind_invoice(self, invoice_id: str, body: Optional[dict] = None) -> Response:
        self._check("remind_invoice", invoice_id)
        return self._inner.remind_invoice(invoice_id, body)

    def record_payment(self, invoice_id: str, body: dict) -> Response:
        self._check("record_payment", invoice_id)
        return self._inner.record_payment(invoice_id, body)

    def __getattr__(self, name: str) -> Any:  # read-only / draft calls pass through
        return getattr(self._inner, name)


@dataclass
class PendingAction:
    id: str
    kind: str  # send_invoice | send_reminder
    invoice_id: str
    summary: str
    payload: dict
    status: str = "PENDING"  # PENDING | APPROVED | REJECTED | FAILED
    result: Any = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("id", "kind", "invoice_id", "summary", "payload", "status", "result", "created_at")}


@dataclass
class LedgerEntry:
    invoice_id: str
    invoice_number: str
    client_name: Optional[str]
    client_email: str
    currency: str
    total: Decimal
    due_days: Optional[int]
    status: str = "DRAFT"
    sent_on: Optional[date] = None
    paid_amount: Decimal = Decimal(0)
    reminders_sent: int = 0
    last_reminder_on: Optional[date] = None
    prepaid: Decimal = Decimal(0)

    @property
    def due_on(self) -> Optional[date]:
        if self.sent_on is None or self.due_days is None:
            return None
        return date.fromordinal(self.sent_on.toordinal() + self.due_days)

    @property
    def balance(self) -> Decimal:
        return max(self.total - self.paid_amount, Decimal(0))

    def days_overdue(self, today: date) -> int:
        d = self.due_on
        return 0 if d is None else max((today - d).days, 0)

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id, "invoice_number": self.invoice_number,
            "client_name": self.client_name, "client_email": self.client_email,
            "currency": self.currency, "total": str(self.total), "paid_amount": str(self.paid_amount),
            "balance": str(self.balance), "status": self.status,
            "sent_on": self.sent_on.isoformat() if self.sent_on else None,
            "due_on": self.due_on.isoformat() if self.due_on else None,
            "reminders_sent": self.reminders_sent,
        }


# ------------------------------------------------------------ reminder drafting

class ReminderDrafter(Protocol):
    def draft(self, entry: LedgerEntry, today: date, freelancer: str) -> dict: ...


class TemplateReminderDrafter:
    """Deterministic, tone escalates with lateness. Swap for an LLM drafter if you like;
    the agent still queues the result for approval either way."""

    def draft(self, entry: LedgerEntry, today: date, freelancer: str) -> dict:
        late = entry.days_overdue(today)
        first = (entry.client_name or "there").split()[0]
        amt = f"{entry.currency} {entry.balance:,}"
        partial = (f" Thank you for the {entry.currency} {entry.paid_amount:,} received so far;"
                   f" the remaining balance is {amt}.") if entry.paid_amount > 0 else ""
        if late <= 7:
            tone, subject = "friendly", f"Friendly reminder: invoice {entry.invoice_number}"
            body = (f"Hi {first},\n\nJust a quick nudge that invoice {entry.invoice_number} for {amt} "
                    f"was due on {entry.due_on:%b %d, %Y}.{partial} You can pay securely via the PayPal link "
                    f"in the original invoice email.\n\nThanks so much,\n{freelancer}")
        elif late <= 30:
            tone, subject = "firm", f"Invoice {entry.invoice_number} is {late} days overdue"
            body = (f"Hi {first},\n\nInvoice {entry.invoice_number} for {amt} is now {late} days past its "
                    f"due date ({entry.due_on:%b %d, %Y}).{partial} Could you let me know when I can expect "
                    f"payment? If something is holding it up, just reply and we can sort it out.\n\n"
                    f"Best,\n{freelancer}")
        else:
            tone, subject = "final", f"Final notice: invoice {entry.invoice_number} ({late} days overdue)"
            body = (f"Hi {first},\n\nInvoice {entry.invoice_number} for {amt} is {late} days overdue.{partial} "
                    f"Please arrange payment within 7 days or contact me to agree a payment plan.\n\n"
                    f"Regards,\n{freelancer}")
        return {"subject": subject, "note": body, "tone": tone, "days_overdue": late}


# ------------------------------------------------------------ planner protocol

class Planner(Protocol):
    def next_step(self, goal: str, history: list[dict], tools: dict[str, str]) -> dict:
        """Return {"tool": name, "args": {...}} or {"final": "text"}."""


class RulePlanner:
    """Deterministic stand-in for an LLM planner so the loop is testable offline.

    goal "invoice:<text>" -> create_invoice, then get_status for each draft
    goal "chase"          -> list_overdue, then send_reminder for each
    goal "status:<id>"    -> get_status
    """

    def next_step(self, goal: str, history: list[dict], tools: dict[str, str]) -> dict:
        done = [h for h in history if h["role"] == "tool"]
        if goal.startswith("invoice:"):
            if not done:
                return {"tool": "create_invoice", "args": {"text": goal[len("invoice:"):]}}
            created = done[0]["result"].get("invoices", [])
            if len(done) - 1 < len(created):
                return {"tool": "get_status", "args": {"invoice_id": created[len(done) - 1]["invoice_id"]}}
            return {"final": _summarise(done)}
        if goal == "chase":
            if not done:
                return {"tool": "list_overdue", "args": {}}
            overdue = done[0]["result"].get("overdue", [])
            if len(done) - 1 < len(overdue):
                return {"tool": "send_reminder", "args": {"invoice_id": overdue[len(done) - 1]["invoice_id"]}}
            return {"final": _summarise(done)}
        if goal.startswith("status:"):
            if not done:
                return {"tool": "get_status", "args": {"invoice_id": goal[len("status:"):]}}
            return {"final": _summarise(done)}
        return {"final": "I don't know how to do that."}


def _summarise(done: list[dict]) -> str:
    return "; ".join(f"{h['tool']} -> {h['result'].get('message', 'ok')}" for h in done)


# ------------------------------------------------------------ agent

class Agent:
    TOOLS = {
        "create_invoice": "Extract a job email into PayPal draft invoice(s). Queues send for human approval. args: text",
        "get_status": "Fetch invoice status from PayPal and sync the ledger. args: invoice_id",
        "send_reminder": "Draft a payment reminder for an overdue invoice and queue it for approval. args: invoice_id",
        "list_overdue": "List open invoices past their due date. args: none",
    }

    def __init__(self, client: InvoicingClient, invoicer: dict, extractor: Optional[Extractor] = None,
                 today: Callable[[], date] = date.today, drafter: Optional[ReminderDrafter] = None,
                 min_confidence: float = 0.5, reminder_cooldown_days: int = 7,
                 webhook_verifier: Optional[Callable[[dict, bytes], dict]] = None):
        self.client = GatedClient(client)
        self.invoicer = invoicer
        self.extractor = extractor or RulesExtractor()
        self.today = today
        self.drafter = drafter or TemplateReminderDrafter()
        self.min_confidence = min_confidence
        self.reminder_cooldown_days = reminder_cooldown_days
        self.webhook_verifier = webhook_verifier
        self.ledger: dict[str, LedgerEntry] = {}
        self.pending: dict[str, PendingAction] = {}
        self.audit: list[dict] = []
        self._seen_events: set[str] = set()

    # -- tool loop
    def run(self, goal: str, planner: Planner, max_steps: int = 12) -> dict:
        history: list[dict] = [{"role": "user", "content": goal}]
        for _ in range(max_steps):
            step = planner.next_step(goal, history, self.TOOLS)
            if "final" in step:
                history.append({"role": "assistant", "content": step["final"]})
                return {"final": step["final"], "history": history, "pending": self.list_pending()}
            name, args = step.get("tool"), step.get("args") or {}
            if name not in self.TOOLS:
                result = {"ok": False, "message": f"unknown or forbidden tool {name!r}"}
            else:
                try:
                    result = getattr(self, f"tool_{name}")(**args)
                except ApprovalRequired as e:  # should never happen via tools; recorded if it does
                    result = {"ok": False, "message": str(e)}
                except (PayPalError, ValueError, TypeError) as e:
                    result = {"ok": False, "message": f"{type(e).__name__}: {e}"}
            self._log("tool", tool=name, args=args, ok=result.get("ok"))
            history.append({"role": "tool", "tool": name, "args": args, "result": result})
        return {"final": "step limit reached", "history": history, "pending": self.list_pending()}

    # -- tools (safe: never send, never move money)
    def tool_create_invoice(self, text: str) -> dict:
        ex = self.extractor.extract(text)
        if ex.errors or ex.confidence < self.min_confidence:
            return {"ok": False, "needs_review": True, "confidence": ex.confidence,
                    "issues": [i.to_dict() for i in ex.issues],
                    "message": f"needs human review (confidence {ex.confidence}, {len(ex.errors)} error(s))"}
        created = []
        for part in split_by_currency(ex):
            number = self.client.generate_next_invoice_number().body["invoice_number"]
            note = "Thank you for your business."
            if ex.amount_paid > 0 and len(ex.currencies()) == 1:
                note += f" Deposit of {part.currency} {ex.amount_paid} received with thanks."
            body = build_invoice(part, self.invoicer, number, self.today(), note,
                                 allow_partial=ex.amount_paid > 0)
            resp = self.client.create_draft_invoice(body)
            inv_id = resp.body["href"].rsplit("/", 1)[-1] if "href" in resp.body else resp.body["id"]
            entry = LedgerEntry(inv_id, number, part.client_name, part.client_email, part.currency,
                                part.total(), part.due_days,
                                prepaid=ex.amount_paid if len(ex.currencies()) == 1 else Decimal(0))
            self.ledger[inv_id] = entry
            summary = f"Send invoice {number} for {part.currency} {part.total():,} to {part.client_email}"
            if entry.prepaid:
                summary += f" and record {part.currency} {entry.prepaid:,} deposit already received"
            action = self._queue("send_invoice", inv_id, summary, {"invoice": body, "prepaid": str(entry.prepaid)})
            created.append({"invoice_id": inv_id, "invoice_number": number, "currency": part.currency,
                            "total": str(part.total()), "approval_id": action.id})
        return {"ok": True, "invoices": created, "confidence": ex.confidence,
                "issues": [i.to_dict() for i in ex.issues],
                "message": f"{len(created)} draft(s) created; awaiting approval to send"}

    def tool_get_status(self, invoice_id: str) -> dict:
        inv = self.client.get_invoice(invoice_id).body
        e = self.ledger.get(invoice_id)
        if e:
            e.status = inv["status"]
            e.paid_amount = Decimal(inv["payments"]["paid_amount"]["value"])
        return {"ok": True, "invoice_id": invoice_id, "status": inv["status"],
                "due_amount": inv["due_amount"]["value"], "currency": inv["detail"]["currency_code"],
                "message": f"{invoice_id} is {inv['status']}"}

    def tool_list_overdue(self) -> dict:
        today = self.today()
        rows = [e.to_dict() | {"days_overdue": e.days_overdue(today)}
                for e in self.ledger.values()
                if e.status in OPEN_STATUSES and e.days_overdue(today) > 0]
        return {"ok": True, "overdue": rows, "message": f"{len(rows)} overdue"}

    def tool_send_reminder(self, invoice_id: str) -> dict:
        e = self.ledger.get(invoice_id)
        if e is None:
            return {"ok": False, "message": f"unknown invoice {invoice_id}"}
        today = self.today()
        if e.status not in OPEN_STATUSES:
            return {"ok": False, "message": f"{invoice_id} is {e.status}; no reminder needed"}
        if e.days_overdue(today) <= 0:
            return {"ok": False, "message": f"{invoice_id} not overdue (due {e.due_on})"}
        if e.last_reminder_on and (today - e.last_reminder_on).days < self.reminder_cooldown_days:
            return {"ok": False, "message": f"reminder already sent on {e.last_reminder_on}; cooling down"}
        if any(a.kind == "send_reminder" and a.invoice_id == invoice_id and a.status == "PENDING"
               for a in self.pending.values()):
            return {"ok": False, "message": "a reminder is already awaiting approval"}
        draft = self.drafter.draft(e, today, self.invoicer.get("name", ""))
        action = self._queue("send_reminder", invoice_id,
                             f"Send {draft['tone']} reminder for {e.invoice_number} ({draft['days_overdue']}d overdue, "
                             f"{e.currency} {e.balance:,} due) to {e.client_email}",
                             {"subject": draft["subject"], "note": draft["note"]})
        return {"ok": True, "approval_id": action.id, "draft": draft,
                "message": f"reminder drafted ({draft['tone']}); awaiting approval"}

    # -- human surface (NOT exposed to the planner)
    def list_pending(self) -> list[dict]:
        return [a.to_dict() for a in self.pending.values() if a.status == "PENDING"]

    def approve(self, action_id: str, approver: str = "human") -> dict:
        a = self._pending_or_raise(action_id)
        try:
            if a.kind == "send_invoice":
                with self.client.permit("send_invoice", a.invoice_id):
                    r = self.client.send_invoice(a.invoice_id, {"send_to_invoicer": True, "send_to_recipient": True})
                e = self.ledger[a.invoice_id]
                e.status, e.sent_on = "SENT", self.today()
                result = {"payer_view": r.body.get("href")}
                if e.prepaid > 0:
                    with self.client.permit("record_payment", a.invoice_id):
                        p = self.client.record_payment(a.invoice_id, {
                            "method": "BANK_TRANSFER", "payment_date": self.today().isoformat(),
                            "amount": {"currency_code": e.currency, "value": str(e.prepaid)},
                            "note": "Deposit received before invoicing"})
                    result["deposit_payment_id"] = p.body["payment_id"]
                    self.tool_get_status(a.invoice_id)
            elif a.kind == "send_reminder":
                with self.client.permit("remind_invoice", a.invoice_id):
                    self.client.remind_invoice(a.invoice_id, {"subject": a.payload["subject"], "note": a.payload["note"],
                                                               "send_to_invoicer": True})
                e = self.ledger[a.invoice_id]
                e.reminders_sent += 1
                e.last_reminder_on = self.today()
                result = {"reminded": True}
            else:
                raise ValueError(f"unknown action kind {a.kind}")
        except PayPalError as err:
            a.status, a.result = "FAILED", err.body
            self._log("approve_failed", action=a.id, approver=approver, error=str(err))
            raise
        a.status, a.result = "APPROVED", result
        self._log("approved", action=a.id, kind=a.kind, invoice=a.invoice_id, approver=approver)
        return result

    def reject(self, action_id: str, reason: str = "") -> None:
        a = self._pending_or_raise(action_id)
        a.status, a.result = "REJECTED", {"reason": reason}
        self._log("rejected", action=a.id, reason=reason)

    # -- webhooks
    def handle_webhook(self, raw_body: bytes, headers: Optional[dict] = None) -> dict:
        if self.webhook_verifier is not None:
            v = self.webhook_verifier(headers or {}, raw_body)
            if v.get("verification_status") != "SUCCESS":
                self._log("webhook_rejected", reason="bad signature")
                raise WebhookError("signature verification failed")
        ev = parse_webhook_event(raw_body)
        if ev.event_id in self._seen_events:
            return {"ok": True, "duplicate": True, "invoice_id": ev.invoice_id}
        self._seen_events.add(ev.event_id)
        e = self.ledger.get(ev.invoice_id)
        if e is None:
            self._log("webhook_unknown_invoice", invoice=ev.invoice_id)
            return {"ok": False, "message": "unknown invoice"}
        prev = e.status
        e.status = ev.status
        if ev.paid_amount is not None:
            e.paid_amount = ev.paid_amount
        if ev.is_fully_paid:  # cancel stale reminders
            for a in self.pending.values():
                if a.invoice_id == e.invoice_id and a.kind == "send_reminder" and a.status == "PENDING":
                    a.status, a.result = "REJECTED", {"reason": "auto: invoice paid"}
        self._log("webhook", event_type=ev.event_type, invoice=ev.invoice_id, transition=f"{prev}->{e.status}")
        return {"ok": True, "invoice_id": ev.invoice_id, "from": prev, "to": e.status}

    # -- internals
    def _queue(self, kind: str, invoice_id: str, summary: str, payload: dict) -> PendingAction:
        a = PendingAction("apv_" + uuid.uuid4().hex[:10], kind, invoice_id, summary, payload)
        self.pending[a.id] = a
        self._log("queued", action=a.id, kind=kind, invoice=invoice_id)
        return a

    def _pending_or_raise(self, action_id: str) -> PendingAction:
        a = self.pending.get(action_id)
        if a is None:
            raise KeyError(f"no such action {action_id}")
        if a.status != "PENDING":
            raise ValueError(f"action {action_id} already {a.status}")
        return a

    def _log(self, event: str, **kw: Any) -> None:
        self.audit.append({"at": datetime.now(timezone.utc).isoformat(), "event": event,
                           **{k: (str(v) if isinstance(v, Decimal) else v) for k, v in kw.items()}})

    def export_state(self) -> str:
        return json.dumps({"ledger": [e.to_dict() for e in self.ledger.values()],
                           "pending": self.list_pending(), "audit": self.audit}, indent=2, default=str)
