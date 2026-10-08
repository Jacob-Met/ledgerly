"""Focused current-main receiving across confirmation, exact values and deadlines."""
import json
from datetime import date
from decimal import Decimal

from ledgerly.agent import Agent
from ledgerly.extract import RulesExtractor
from ledgerly.paypal import SandboxMock


INVOICER = {"name": "Independent Receipt", "email_address": "receiver@example.invalid"}
PREFIX = "From: Current Client <client@example.invalid>\n\n- 1 x Service @ USD 100.00\n"
CASES = [
    ("confirmed-malformed-group", ["Deposit paid: USD 1,23."], False),
    ("confirmed-malformed-tail", ["Deposit paid: USD 12.345.67."], False),
    ("confirmed-foreign", ["Deposit paid: EUR 25.00."], False),
    ("confirmed-subunit", ["Deposit paid: USD 0.005."], False),
    ("confirmed-subunits-cannot-cancel", ["Deposit paid: USD 0.005.", "Already paid USD 0.005."], False),
    ("confirmed-negative", ["Deposit paid: -USD 25.00."], False),
    ("future-foreign", ["We will pay an EUR 25.00 deposit tomorrow."], True),
    ("negated", ["We have not paid a USD 25.00 deposit."], True),
    ("conditional", ["If we already paid USD 25.00, begin work."], True),
    ("refunded", ["We already paid USD 25.00, but it was refunded."], True),
]


def refused_case(label, lines, must_remain_zero):
    text = PREFIX + "\n".join(lines) + "\nNet 12\n"
    ex = RulesExtractor().extract(text)
    mock = SandboxMock()
    agent = Agent(mock, INVOICER, today=lambda: date(2026, 10, 1))
    result = agent.tool_create_invoice(text)
    record = {
        "case": label, "lines": lines, "amount_paid": str(ex.amount_paid),
        "error_fields": [issue.field for issue in ex.errors],
        "ok": result.get("ok"), "needs_review": result.get("needs_review"),
        "requests": len(mock.requests), "drafts": len(mock.invoices),
        "ledger_rows": len(agent.ledger), "pending": len(agent.list_pending()),
    }
    problems = []
    if not ex.errors:
        problems.append("invalid or uncertain statement had no extraction error")
    if must_remain_zero and ex.amount_paid != 0:
        problems.append("uncertain statement became a recorded receipt")
    if result.get("ok") is not False or result.get("needs_review") is not True:
        problems.append("whole job was not held for review")
    if mock.requests or mock.invoices or agent.ledger or agent.list_pending():
        problems.append("refused job produced a request or partial state")
    record["problems"] = problems
    return record


def accepted_delayed_deposit():
    clock = [date(2026, 10, 1)]
    text = PREFIX + "Deposit already paid: USD 25.00.\nNet 12\n"
    mock = SandboxMock()
    agent = Agent(mock, INVOICER, today=lambda: clock[0])
    result = agent.tool_create_invoice(text)
    assert result["ok"], result
    row = result["invoices"][0]
    entry = agent.ledger[row["invoice_id"]]
    assert entry.invoice_due_on == date(2026, 10, 13)
    assert entry.due_on is None
    assert not any(path.endswith(("/send", "/payments")) for _, path, _ in mock.requests)
    clock[0] = date(2026, 10, 8)
    agent.approve(row["approval_id"])
    assert entry.sent_on == clock[0]
    assert entry.due_on == date(2026, 10, 13)
    assert entry.paid_amount == Decimal("25.00")
    assert entry.balance == Decimal("75.00")
    sends = [body for _, path, body in mock.requests if path.endswith("/send")]
    payments = [body for _, path, body in mock.requests if path.endswith("/payments")]
    assert len(sends) == 1 and len(payments) == 1
    assert payments[0]["amount"]["currency_code"] == "USD"
    assert Decimal(payments[0]["amount"]["value"]) == Decimal("25.00")
    return {"case": "accepted-confirmed-deposit-with-delayed-approval", "due_on": entry.due_on.isoformat(),
            "sent_on": entry.sent_on.isoformat(), "paid_amount": str(entry.paid_amount),
            "balance": str(entry.balance), "sends": len(sends), "payments": len(payments), "problems": []}


records = [refused_case(*case) for case in CASES]
try:
    records.append(accepted_delayed_deposit())
except Exception as error:
    records.append({"case": "accepted-confirmed-deposit-with-delayed-approval",
                    "problems": [type(error).__name__ + ": " + str(error)]})
print(json.dumps({"cases": records, "passed": sum(not row["problems"] for row in records),
                  "failed": sum(bool(row["problems"]) for row in records)}, indent=2))
raise SystemExit(1 if any(row["problems"] for row in records) else 0)
