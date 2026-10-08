"""Exact unchanged native receiving witness for completed-review history."""
import copy, hashlib, json, pathlib, sys, urllib.request
root = pathlib.Path(sys.argv[1]).resolve()
sys.dont_write_bytecode = True
sys.path[:0] = [str(root), str(root / "web-demo/python")]
import bridge
external = []
def refuse_network(*args, **kwargs):
    external.append("urllib.request.urlopen")
    raise AssertionError("No external HTTP is part of this sandbox receiver")
urllib.request.urlopen = refuse_network
manifest = json.loads((root.parent / "receipts/source-manifest.json").read_text())
def source_hashes():
    return {r["path"]: hashlib.sha256((root / r["path"]).read_bytes()).hexdigest() for r in manifest["files"]}
before_source = source_hashes()
checks = []
def check(name, actual, expected):
    checks.append({"name": name, "actual": actual, "expected": expected, "pass": actual == expected})
def call(action, **payload):
    return json.loads(bridge.handle_json(json.dumps({"action": action, **payload})))
call("reset")
demo = bridge.SESSION
text = (root / "fixtures/01_simple_usd_hourly.txt").read_text()
queued = []
for outcome in ("approve", "reject", "unknown"):
    draft = call("draft", text=text)
    assert draft["ok"], draft
    action = draft["state"]["pending"][-1]
    queued.append(copy.deepcopy(action))
    if outcome != "unknown":
        reply = call(outcome, action_id=action["id"])
        assert reply["ok"], reply
    else:
        original_send = demo.mock.send_invoice
        def sent_then_lost(*args, **kwargs):
            original_send(*args, **kwargs)
            raise TimeoutError("Authored lost response after the actual mock send")
        demo.mock.send_invoice = sent_then_lost
        reply = call("approve", action_id=action["id"])
        demo.mock.send_invoice = original_send
        check("unknown outgoing reply is an error", reply["ok"], False)
        check("actual effect happened before response loss", demo.mock.invoices[action["invoice_id"]]["status"], "SENT")
retained = [a.to_dict() for a in demo.agent.pending.values()]
check("core retained exact action identities", [a["id"] for a in retained], [a["id"] for a in queued])
check("core retained all three outcome classes", [a["status"] for a in retained], ["APPROVED", "REJECTED", "FAILED"])
check("unknown result remains explicit in core", retained[-1]["result"]["outcome"], "UNKNOWN")
check("core retained original proposals", [a["payload"] for a in retained], [a["payload"] for a in queued])
requests_before = copy.deepcopy(demo.mock.requests)
actions_before = copy.deepcopy(retained)
snapshot = demo.snapshot()
check("closed actions leave pending queue", snapshot["pending"], [])
check("snapshot causes no extra mock request", demo.mock.requests, requests_before)
check("snapshot preserves retained action state", [a.to_dict() for a in demo.agent.pending.values()], actions_before)
check("no external call", external, [])
check("all exact source inputs unchanged", source_hashes(), before_source)
missing = [
    {"name": "browser exposes retained original proposals", "pass": snapshot.get("completed_reviews") is not None},
    {"name": "browser exposes all three completed reviews", "pass": len(snapshot.get("completed_reviews", [])) == 3},
    {"name": "browser retains explicit UNKNOWN outcome", "pass": any(a.get("result", {}).get("outcome") == "UNKNOWN" for a in snapshot.get("completed_reviews", []))},
]
receipt = {"source_commit": manifest["source_commit"], "runtime": sys.version, "entrypoint": "bridge.handle_json -> Demo -> Agent -> SandboxMock",
           "healthy_checks": checks, "healthy_pass": all(c["pass"] for c in checks), "missing_product_checks": missing,
           "expected_missing_checks": sum(not c["pass"] for c in missing), "queued": queued, "retained": retained,
           "browser_snapshot": snapshot, "external_calls": external, "source_files_before": before_source, "source_files_after": source_hashes()}
out = root.parent / "receipts/history-baseline.json"
with out.open("x") as f: json.dump(receipt, f, indent=2, ensure_ascii=False); f.write("\n")
print(json.dumps({"receipt": str(out), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "healthy_pass": receipt["healthy_pass"], "healthy_checks": len(checks), "expected_missing_checks": receipt["expected_missing_checks"], "mock_requests": len(demo.mock.requests)}))
assert receipt["healthy_pass"] and receipt["expected_missing_checks"] == 3
