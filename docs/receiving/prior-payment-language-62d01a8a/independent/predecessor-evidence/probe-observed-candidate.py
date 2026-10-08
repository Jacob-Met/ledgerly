"""Independent negative witnesses; only the native in-memory SandboxMock is used."""
from datetime import date, datetime, timezone
from pathlib import Path
from decimal import Decimal
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "observed-candidate-v1"))
from ledgerly.extract import RulesExtractor
from ledgerly.agent import Agent
from ledgerly.paypal import SandboxMock

CASES = (
    "We'll have paid a $500 deposit by Friday.",
    "We’ll have paid a $500 deposit by Friday.",
    "Earlier you wrote 'we paid a $500 deposit' for another project.",
    "Earlier you wrote ‘we paid a $500 deposit’ for another project.",
    "Had we paid a $500 deposit, we'd have a receipt.",
)
for statement in CASES:
    text = "From: Review Client <client@example.test>\n\nWebsite build — $1,000\nNet 30.\n" + statement
    extraction = RulesExtractor().extract(text)
    mock = SandboxMock(now=lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
    agent = Agent(mock, {"name": "Review Fixture", "email_address": "fixture@example.test"}, today=lambda: date(2026, 10, 8))
    result = agent.tool_create_invoice(text)
    before = {"drafts": len(mock.invoices), "pending": len(agent.pending), "provider_records": len(mock.requests)}
    if result.get("ok"):
        for row in result["invoices"]:
            agent.approve(row["approval_id"], approver="independent local fixture")
    payments = [body["amount"]["value"] for method, path, body in mock.requests if method == "POST" and path.endswith("/payments")]
    print(json.dumps({"statement": statement, "amount_paid": str(extraction.amount_paid),
        "amount_paid_errors": [i.to_dict() for i in extraction.errors if i.field == "amount_paid"],
        "needs_review": result.get("needs_review", False), "before_mock_approval": before,
        "mock_external_payment_amounts_after_approval": payments}, ensure_ascii=False))
