import copy
import hashlib
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "current-before"
sys.path[:0] = [str(SOURCE), str(SOURCE / "web-demo/python")]
import bridge
from ledgerly.paypal import HttpPayPalClient

pins = json.loads((ROOT / "current-before-pins.json").read_text())
def verify():
    for name, expected in pins["files"].items():
        raw = (SOURCE / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise AssertionError(name)

rows = []
verify()
with patch.object(HttpPayPalClient, "__init__", side_effect=AssertionError("HTTP client forbidden")), patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")), patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
    for amount in ("50.00", "-50", "0", "0.015", "NaN", "Infinity", "1e999999"):
        demo = bridge.Demo()
        bridge.SESSION = demo
        drafted = demo.dispatch({"action": "draft", "text": (SOURCE / "fixtures/02_gbp_proofreading.txt").read_text()})
        queued = drafted["state"]["pending"][0]
        demo.dispatch({"action": "approve", "action_id": queued["id"]})
        invoice = demo.mock.invoices[queued["invoice_id"]]
        before = copy.deepcopy(invoice)
        initial_requests = len(demo.mock.requests)
        response = json.loads(bridge.handle_json(json.dumps({"action": "payment", "invoice_id": queued["invoice_id"], "amount": amount})))
        after = copy.deepcopy(invoice)
        later = None
        if amount in ("NaN", "Infinity"):
            later = json.loads(bridge.handle_json(json.dumps({"action": "payment", "invoice_id": queued["invoice_id"], "amount": "20.00"})))
        rows.append({"amount": amount, "ok": response["ok"], "error": response.get("error"), "message": response.get("message"), "initial_status": before["status"], "initial_due": before["due_amount"], "mock_changed": after != before, "after_status": after["status"], "after_paid": after["payments"], "after_due": after["due_amount"], "displayed_ledger": response["state"]["ledger"], "request_delta": len(demo.mock.requests) - initial_requests, "external_calls": response["state"]["external_calls"], "valid_retry_after_bad_payment": None if later is None else {"ok": later["ok"], "error": later.get("error"), "message": later.get("message"), "transactions": copy.deepcopy(invoice["payments"]["transactions"])}})
verify()
print(json.dumps({"base": pins["base"], "runtime": sys.version, "source_unchanged": True, "scenarios": rows}, indent=2))
