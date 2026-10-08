"""Independent four-stage receiver for literal per-action rejection reasons.

All mutations enter the actual bridge.handle_json JSON boundary. Agent state is
read only to qualify exact attribution and absence of effects on other actions.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import traceback

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
variant = sys.argv[3]
expected = {
    "baseline": "c265d04c5251ae437c4ffc2eb4533a4d0a6da056d1a8d9c37835fb71b9a3acd0",
    "candidate": "29fc87a066111b6d3dd214797cb51b7727d0585a104a71ad20593a0de3425e81",
}
default_reason = "Rejected by the browser visitor"
literal_reason = '\u2003  Hold "alpha α"\n<not approved> & café 🙂\t '
sha = lambda b: hashlib.sha256(b).hexdigest()
git = lambda b: hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
clean = lambda value: json.loads(json.dumps(value, default=str, ensure_ascii=False, sort_keys=True))
report = {
    "variant": variant, "source": str(source), "python": sys.version,
    "entrypoint": "bridge.handle_json(JSON) -> actual Demo/Agent/SandboxMock",
    "source_base": "fba278f552e868ad2b94b7f1dc309eed6f1e8514",
    "checks": [], "steps": [], "source_unchanged": False,
}
def check(group, name, observed, required):
    observed, required = clean(observed), clean(required)
    report["checks"].append({
        "group": group, "name": name, "pass": observed == required,
        "observed": observed, "required": required,
    })

try:
    st = os.statvfs(output.parent)
    mem = {
        k: int(v.split()[0]) * 1024 for k, v in (
            line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
        )
    }
    report["guard"] = {"free_disk": st.f_bavail * st.f_frsize, "available_memory": mem["MemAvailable"]}
    if report["guard"]["free_disk"] < 1024**3 or mem["MemAvailable"] < 1536*1024**2:
        raise RuntimeError("Resource guard refused")
    entry = source / "web-demo/python/bridge.py"
    entry_bytes = entry.read_bytes()
    if sha(entry_bytes) != expected[variant]:
        raise RuntimeError("Frozen bridge mismatch")
    sys.path[:0] = [str(source / "web-demo/python"), str(source)]
    bridge = importlib.import_module("bridge")
    if Path(bridge.__file__).resolve() != entry:
        raise RuntimeError("Unexpected bridge import")
    def source_pins():
        pins = {}
        for module in list(sys.modules.values()):
            filename = getattr(module, "__file__", None)
            if not filename:
                continue
            p = Path(filename).resolve()
            if p.suffix == ".py" and p.is_relative_to(source):
                b = p.read_bytes()
                pins[p.relative_to(source).as_posix()] = {"bytes": len(b), "sha256": sha(b), "git_blob": git(b)}
        return pins
    before_pins = source_pins()
    if before_pins["ledgerly/agent.py"]["git_blob"] != "e4e26ebd7259bd61d14819593a17d3d0738bbf30":
        raise RuntimeError("Primary Agent pin mismatch")
    def request(payload):
        raw = json.dumps(payload, ensure_ascii=False)
        return json.loads(bridge.handle_json(raw))
    def effects():
        session = bridge.SESSION
        return clean({
            "actions": {key: action.to_dict() for key, action in session.agent.pending.items()},
            "audit": session.agent.audit,
            "ledger": {key: entry.to_dict() for key, entry in session.agent.ledger.items()},
            "mock_request_count": len(session.mock.requests),
            "mock_invoices_sha256": sha(json.dumps(session.mock.invoices, default=str, ensure_ascii=False, sort_keys=True).encode()),
        })
    first = request({"action": "init"})
    if not first["ok"] or first["result"].get("engine") != "RulesExtractor + RulePlanner + SandboxMock":
        raise RuntimeError("Actual Demo initialization failed")
    fixtures = [
        "From: Alice One <alice.one@example.test>\nSubject: completed workshop\n\nPlease invoice in USD.\n- Discovery workshop: 2 hours @ $40/hr\nNet 14.\nThanks,\nAlice One",
        "From: Bob Two <bob.two@example.test>\nSubject: completed workshop\n\nPlease invoice in USD.\n- Follow-up workshop: 3 hours @ $30/hr\nNet 14.\nThanks,\nBob Two",
    ]
    for text in fixtures:
        result = request({"action": "draft", "text": text})
        if not result["ok"]:
            raise RuntimeError("Public draft failed: " + json.dumps(result))
    pending = result["state"]["pending"]
    if len(pending) != 2 or any(item["kind"] != "send_invoice" for item in pending):
        raise RuntimeError("Two-action setup did not produce actual send approvals: " + json.dumps(result))
    a, b = [item["id"] for item in pending]
    if a == b or pending[0]["invoice_id"] == pending[1]["invoice_id"]:
        raise RuntimeError("Setup identities are not distinct")
    report["setup"] = {"texts": fixtures, "actions": pending, "mock_request_count": result["state"]["mock_requests"]}
    before = effects()

    stale = request({"action": "reject", "action_id": "missing-" + a, "reason": "must not attach to another action"})
    check("stale identity", "unknown identity refuses", [stale["ok"], stale.get("error")], [False, "KeyError"])
    check("stale identity", "both real identities remain pending", [item["id"] for item in stale["state"]["pending"]], [a, b])
    check("stale identity", "unknown identity has no action/audit/invoice/request effects", effects(), before)
    report["steps"].append({"name": "stale", "response": stale})

    rejected = request({"action": "reject", "action_id": a, "reason": literal_reason})
    after_a = effects()
    check("selected identity", "public rejection succeeds", [rejected["ok"], rejected.get("result", {}).get("rejected")], [True, True])
    check("selected identity", "public result preserves literal reason", rejected.get("result", {}).get("reason"), literal_reason)
    check("selected identity", "selected action stores exact literal reason", after_a["actions"][a]["result"], {"reason": literal_reason})
    check("selected identity", "only selected action is rejected", after_a["actions"][a]["status"], "REJECTED")
    check("selected identity", "other pending action is byte-equivalent", after_a["actions"][b], before["actions"][b])
    check("selected identity", "public pending list retains only the other identity", [item["id"] for item in rejected["state"]["pending"]], [b])
    check("selected identity", "existing Agent audit retains exact attribution and reason",
          {k: after_a["audit"][-1].get(k) for k in ("event", "action", "reason")},
          {"event": "rejected", "action": a, "reason": literal_reason})
    check("selected identity", "exactly one audit event appended", len(after_a["audit"]), len(before["audit"]) + 1)
    check("selected identity", "rejection leaves provider mock and invoice ledger unchanged",
          {k: after_a[k] for k in ("mock_request_count", "mock_invoices_sha256", "ledger")},
          {k: before[k] for k in ("mock_request_count", "mock_invoices_sha256", "ledger")})
    report["steps"].append({"name": "selected", "response": rejected, "audit_event": after_a["audit"][-1], "action_result": after_a["actions"][a]["result"]})

    duplicate = request({"action": "reject", "action_id": a, "reason": "different text must never overwrite history"})
    check("duplicate identity", "consumed identity refuses", [duplicate["ok"], duplicate.get("error")], [False, "ValueError"])
    check("duplicate identity", "refusal identifies the consumed action", a in duplicate.get("message", "") and "already REJECTED" in duplicate.get("message", ""), True)
    check("duplicate identity", "duplicate has no action/audit/invoice/request effects", effects(), after_a)
    check("duplicate identity", "other identity remains pending", [item["id"] for item in duplicate["state"]["pending"]], [b])
    report["steps"].append({"name": "duplicate", "response": duplicate})

    legacy = request({"action": "reject", "action_id": b})
    after_b = effects()
    check("legacy default", "omitted reason succeeds with documented default",
          legacy.get("result"), {"rejected": True, "reason": default_reason})
    check("legacy default", "second action stores its own default", after_b["actions"][b]["result"], {"reason": default_reason})
    check("legacy default", "first action history is preserved exactly", after_b["actions"][a], after_a["actions"][a])
    check("legacy default", "no pending identity remains", legacy["state"]["pending"], [])
    check("legacy default", "default attribution belongs to the second action",
          {k: after_b["audit"][-1].get(k) for k in ("event", "action", "reason")},
          {"event": "rejected", "action": b, "reason": default_reason})
    check("legacy default", "second rejection has no provider or ledger effects",
          {k: after_b[k] for k in ("mock_request_count", "mock_invoices_sha256", "ledger")},
          {k: before[k] for k in ("mock_request_count", "mock_invoices_sha256", "ledger")})
    report["steps"].append({"name": "legacy", "response": legacy, "audit_event": after_b["audit"][-1]})
    after_pins = source_pins()
    if after_pins != before_pins:
        raise RuntimeError("Source closure changed during receiving")
    report["source_pins"] = after_pins
    report["source_unchanged"] = True
    report["external_calls"] = legacy["state"]["external_calls"]
    report["four_stage_contract_completed"] = True
except Exception as exc:
    report["fatal"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
report["passed"] = sum(check["pass"] for check in report["checks"])
report["failed"] = sum(not check["pass"] for check in report["checks"])
report["groups"] = sorted({check["group"] for check in report["checks"]})
data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
output.write_bytes(data)
print(json.dumps({"variant":variant,"passed":report["passed"],"failed":report["failed"],"fatal":report.get("fatal"),"source_unchanged":report["source_unchanged"],"report":str(output),"sha256":sha(data)},ensure_ascii=False))
raise SystemExit(1 if report.get("fatal") or report["failed"] else 0)
