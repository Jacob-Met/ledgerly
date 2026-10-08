"""Qualify newly integrated mock receipt terms with the frozen approval correction."""
from pathlib import Path
from datetime import datetime, timezone
import ast, hashlib, json, os, shutil, subprocess, sys
ROOT = Path(__file__).resolve().parent
ENV = {**os.environ, "LEDGERLY_ALLOW_NETWORK": "0", "PYTHONDONTWRITEBYTECODE": "1"}
MIN_FREE = 512 * 1024 * 1024
MAX_OWN = 16 * 1024 * 1024
def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
def guard():
    free = shutil.disk_usage(ROOT).free
    own = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())
    assert free >= MIN_FREE and own <= MAX_OWN, (free, own)
    return {"free_bytes": free, "own_bytes": own}
def method(text):
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == "Agent")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "approve")
    lines = text.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1:node.end_lineno])
data = json.loads((ROOT / "receipt-input.json").read_text())
before = guard()
candidate = (ROOT / "source/ledgerly/agent.py").read_bytes()
assert sha(candidate) == data["frozen_candidate_agent_sha256"]
current = data["agent"]["content"]
assert blob(current.encode()) == data["agent"]["sha"]
composed = current.replace(method(current), method(candidate.decode()), 1)
assert method(current) == method((ROOT / "baseline/ledgerly/agent.py").read_text())
destination = ROOT / "receipt-composed"
shutil.copytree(ROOT / "latest-composed", destination)
for row in data["files"]:
    raw = row["content"].encode()
    assert blob(raw) == row["sha"]
    (destination / row["path"]).write_bytes(raw)
(destination / "ledgerly/agent.py").write_text(composed)
def selected():
    result = {}
    for path in destination.rglob("*"):
        if not path.is_file(): continue
        rel = path.relative_to(destination).as_posix()
        raw = path.read_bytes()
        result[rel] = {"sha256": sha(raw), "git_blob": blob(raw), "bytes": len(raw)}
        if rel not in {"ledgerly/agent.py", "tests/test_approval_outcomes.py"}:
            assert blob(raw) == data["current_blobs"][rel], rel
    return result
source_before = selected()
harness = ROOT / "independent/independent_review.py"
assert sha(harness.read_bytes()) == "125bb8ae3f739ec9f655df9e68ee6e747c7b9d09666b0e9d64496210defb96bf"
commands = [
    ["/usr/bin/python3", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
     "tests/test_receipt_term_receiving.py",
     "tests/test_approval_outcomes.py"],
    ["/usr/bin/python3", "-B", str(harness), str(destination), str(ROOT / "receipt-bridge-receiving.json")],
]
results = []
try:
    for argv in commands:
        p = subprocess.run(argv, cwd=destination, env=ENV, capture_output=True, text=True, timeout=45)
        record = {"command": argv, "cwd": str(destination), "returncode": p.returncode,
                  "stdout": p.stdout, "stderr": p.stderr, "after": guard()}
        results.append(record)
        print(json.dumps({"returncode": p.returncode, "summary": p.stdout.splitlines()[-1:] or p.stderr.splitlines()[-2:]}), flush=True)
        assert p.returncode == 0, record
    assert source_before == selected()
    assert sha((ROOT / "source/ledgerly/agent.py").read_bytes()) == data["frozen_candidate_agent_sha256"]
finally:
    out = {"at": datetime.now(timezone.utc).isoformat(), "current_base": data["base"], "current_tree": data["tree"],
           "source": str(destination), "current_agent_blob": data["agent"]["sha"],
           "composed_agent_sha256": sha(composed.encode()), "composed_agent_blob": blob(composed.encode()),
           "approve_substitution_only": True, "retained_other_current_agent_bytes": True,
           "source_files": source_before, "commands": results, "before": before, "after": guard(),
           "guards": {"minimum_free_bytes": MIN_FREE, "maximum_own_bytes": MAX_OWN, "command_timeout_seconds": 45},
           "runner_sha256": sha(Path(__file__).read_bytes()),
           "execution_by": "production_scope; unchanged independently authored four-method bridge harness replayed for the new mock receipt-term composition",
           "prior_receipts": ["current-composition.json", "latest-composition.json", "independent/independent-results.json"],
           "boundary": "Prior independent acceptance remains at original187 source. This additional author current-composition run proves interaction with newly integrated mock send receipt-term bytes; no new peer acceptance, browser, external call or installed deployment is implied."}
    (ROOT / "receipt-composition.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({"current": data["base"], "composed_agent_sha256": sha(composed.encode()),
                  "files_checked": len(source_before), "receipt_sha256": sha((ROOT / "receipt-composition.json").read_bytes())}), flush=True)
