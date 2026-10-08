"""End-to-end offline demo: email -> draft -> approval -> send -> webhook paid -> overdue reminder.

    python -m ledgerly.demo            # scripted run, auto-approves after printing the gate
    python -m ledgerly.demo --interactive   # you type y/n at each approval
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .agent import Agent, ApprovalRequired, RulePlanner
from .paypal import SandboxMock

FIX = Path(__file__).resolve().parents[1] / "fixtures"


class Clock:
    def __init__(self, d: date):
        self.d = d

    def __call__(self) -> date:
        return self.d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    args = ap.parse_args()

    def decide(action: dict) -> bool:
        print(f"\n  APPROVAL NEEDED [{action['id']}]: {action['summary']}")
        if action["kind"] == "send_reminder":
            print("  ---\n  " + action["payload"]["note"].replace("\n", "\n  ") + "\n  ---")
        if args.interactive:
            return input("  approve? [y/N] ").strip().lower() == "y"
        print("  (scripted demo: approving)")
        return True

    clock = Clock(date(2026, 10, 1))
    mock = SandboxMock()
    agent = Agent(mock, {"name": "Jacob Scott-Metoyer", "email_address": "jacob@ledgerly.example"}, today=clock)

    for f in ("01_simple_usd_hourly.txt", "04_multi_currency.txt", "05_missing_email.txt", "12_prompt_injection.txt"):
        print(f"\n=== {f}")
        out = agent.run("invoice:" + (FIX / f).read_text(), RulePlanner())
        print("  agent:", out["final"])
        first = out["history"][1]["result"]
        for i in first.get("issues", []):
            print(f"  [{i['severity']}] {i['field']}: {i['message']}")

    print("\n=== Gate check: trying to send without approval")
    any_id = next(iter(agent.ledger))
    try:
        agent.client.send_invoice(any_id)
    except ApprovalRequired as e:
        print("  blocked:", e)

    for a in agent.list_pending():
        agent.approve(a["id"]) if decide(a) else agent.reject(a["id"], "declined in demo")

    sent = [e for e in agent.ledger.values() if e.status == "SENT"]
    if sent:
        print(f"\n=== Payer pays {sent[0].invoice_number} (mock webhook INVOICING.INVOICE.PAID)")
        ev = mock.simulate_payer_payment(sent[0].invoice_id)
        raw = json.dumps(ev).encode()
        print("  ", agent.handle_webhook(raw, mock.sign(raw)))
    else:
        print("\n=== No sent invoices; skipping the mock payment")

    clock.d = date(2026, 11, 20)
    print(f"\n=== {clock.d}: chase overdue")
    out = agent.run("chase", RulePlanner())
    print("  agent:", out["final"])
    for a in agent.list_pending():
        agent.approve(a["id"]) if decide(a) else agent.reject(a["id"], "declined in demo")

    print("\n=== Ledger")
    for e in agent.ledger.values():
        print(f"  {e.invoice_number}  {e.client_email:32} {e.currency} {e.total:>9}  {e.status:15} reminders={e.reminders_sent}")
    print(f"\nPayPal mock calls: {len(mock.requests)} (network calls: 0)")


if __name__ == "__main__":
    main()
