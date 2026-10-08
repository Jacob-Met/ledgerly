"""Independent authored fixture through the unchanged native demo bridge."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from datetime import date
from pathlib import Path

SOURCE = Path(os.environ.get("LEDGERLY_RECEIVABLES_SOURCE", Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(SOURCE), str(SOURCE / "web-demo/python")]


def hashes():
    paths = [*sorted((SOURCE / "ledgerly").glob("*.py")),
             *sorted((SOURCE / "web-demo/python").glob("*.py"))]
    return {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


before = hashes()
spec = importlib.util.spec_from_file_location("receivables_peer_native_bridge", SOURCE / "web-demo/python/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
bridge.SESSION.clock.day = date(2032, 2, 28)
calls = []


def call(action, **fields):
    request = {"action": action, **fields}
    reply = json.loads(bridge.handle_json(json.dumps(request)))
    calls.append({"request": request, "response": reply})
    assert reply["ok"], reply
    return reply


call("init")
jobs = [
    ("juniper_seven", "Juniper Studio", "billing@juniper.example.test", "USD", "0.07", 1, True, None),
    ("juniper_fourteen", "Juniper Books", "billing@juniper.example.test", "USD", "0.14", 2, True, None),
    ("juniper_euro", "Juniper Studio", "billing@juniper.example.test", "EUR", "9.90", 3, True, None),
    ("juniper_partial", "Juniper Studio", "billing@juniper.example.test", "USD", "50.05", 1, True, "0.04"),
    ("boreal_yen", "Boreal Team", "billing@boreal.example.test", "JPY", "701", 1, True, None),
    ("boreal_paid", "Boreal Team", "billing@boreal.example.test", "USD", "4.00", 1, True, "full"),
    ("boreal_draft", "Boreal Team", "billing@boreal.example.test", "GBP", "8.00", 4, False, None),
]
aliases = {}
for key, name, email, currency, amount, days, approve, payment in jobs:
    text = f"From: {name} <{email}>\n\n- 1 x Illustration work @ {currency} {amount}\nNet {days}\n"
    draft = call("draft", text=text)
    assert draft["result"]["unauthorized_send_blocked"] is True
    pending = draft["result"]["pending"]
    assert len(pending) == 1 and pending[0]["kind"] == "send_invoice", draft
    action = pending[0]
    aliases[key] = action["invoice_id"]
    if approve:
        call("approve", action_id=action["id"])
    if payment is not None:
        call("payment", invoice_id=action["invoice_id"], amount=None if payment == "full" else payment)
snapshot = call("advance", day="2032-03-01")["state"]
read_again = call("init")["state"]
after = hashes()
assert before == after
assert snapshot == read_again
assert snapshot["external_calls"] == 0
assert len(calls) == 18 and len(snapshot["ledger"]) == 7
print(json.dumps({
    "fixture_kind": "authored native bridge/Agent/SandboxMock execution",
    "fixture_clock_start": "2032-02-28", "aliases": aliases,
    "snapshot": snapshot, "commands": calls,
    "source_before": before, "source_after": after, "source_unchanged": before == after,
    "snapshot_read_unchanged": snapshot == read_again, "external_calls": snapshot["external_calls"],
}, ensure_ascii=False, indent=2))
