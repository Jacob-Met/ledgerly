"""Bounded native validation for the exact source candidate; uses installed pytest."""
import difflib
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
MIN_FREE = 512 * 1024 * 1024
MAX_OWN = 16 * 1024 * 1024
ENV = {**os.environ, "LEDGERLY_ALLOW_NETWORK": "0", "PYTHONDONTWRITEBYTECODE": "1"}
records = []

def sha(data):
    return hashlib.sha256(data).hexdigest()

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def guard():
    free = shutil.disk_usage(ROOT).free
    own = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())
    assert free >= MIN_FREE, {"free_bytes": free}
    assert own <= MAX_OWN, {"own_bytes": own}
    return {"free_bytes": free, "own_bytes": own}

def run(name, args, cwd, expected):
    before = guard()
    result = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=45)
    record = {"name": name, "command": args, "cwd": str(cwd), "returncode": result.returncode,
              "expected_returncode": expected, "stdout": result.stdout, "stderr": result.stderr,
              "before": before, "after": guard()}
    records.append(record)
    assert result.returncode == expected, record
    print(json.dumps({"name": name, "returncode": result.returncode,
                      "summary": result.stdout.splitlines()[-1:]}), flush=True)

pins = json.loads((ROOT/"source-pins.json").read_text())
for row in pins["files"]:
    data = (ROOT/"baseline"/row["path"]).read_bytes()
    assert blob(data) == row["git_blob"]
    if row["path"] != "ledgerly/agent.py":
        assert (ROOT/"source"/row["path"]).read_bytes() == data

control = ROOT/"baseline-control"
shutil.copytree(ROOT/"baseline", control)
test_data = (ROOT/"source/tests/test_approval_outcomes.py").read_bytes()
(control/"tests/test_approval_outcomes.py").write_bytes(test_data)
python = "/usr/bin/python3"
try:
    run("original_core_suite", [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        ROOT/"baseline", 0)
    run("new_controls_on_original_source",
        [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_approval_outcomes.py"],
        control, 1)
    run("candidate_core_suite", [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        ROOT/"source", 0)
    run("candidate_actual_api_receiving",
        [python, "-B", str(ROOT/"reproduce.py"), str(ROOT/"source")], ROOT, 0)
finally:
    import pytest
    receipt = {"at": datetime.now(timezone.utc).isoformat(), "base": pins["base"], "tree": pins["tree"],
               "python": sys.version, "pytest": pytest.__version__,
               "python_executable": str(pathlib.Path(python).resolve()),
               "python_sha256": sha(pathlib.Path(python).read_bytes()),
               "source_collection": "29 selected exact text files; baseline control overlays only the new test",
               "guards": {"minimum_free_bytes": MIN_FREE, "maximum_own_bytes": MAX_OWN,
                          "command_timeout_seconds": 45,
                          "limits": "Checks before/after commands and subprocess deadline; not kernel memory/disk quotas"},
               "native_check_sha256": sha(pathlib.Path(__file__).read_bytes()), "commands": records}
    (ROOT/"native-results.json").write_text(json.dumps(receipt, indent=2)+"\n")

for row in pins["files"]:
    assert blob((ROOT/"baseline"/row["path"]).read_bytes()) == row["git_blob"]
    assert blob((control/row["path"]).read_bytes()) == row["git_blob"]
    if row["path"] != "ledgerly/agent.py":
        assert blob((ROOT/"source"/row["path"]).read_bytes()) == row["git_blob"]
diff = list(difflib.unified_diff(
    (ROOT/"baseline/ledgerly/agent.py").read_text().splitlines(True),
    (ROOT/"source/ledgerly/agent.py").read_text().splitlines(True),
    fromfile="a/ledgerly/agent.py", tofile="b/ledgerly/agent.py"))
diff += list(difflib.unified_diff([], test_data.decode().splitlines(True),
                                 fromfile="/dev/null", tofile="b/tests/test_approval_outcomes.py"))
(ROOT/"product.diff").write_text("".join(diff))
product = [{"path": path, "git_blob": blob((ROOT/"source"/path).read_bytes()),
            "sha256": sha((ROOT/"source"/path).read_bytes()),
            "bytes": (ROOT/"source"/path).stat().st_size}
           for path in ("ledgerly/agent.py", "tests/test_approval_outcomes.py")]
(ROOT/"product-pins.json").write_text(json.dumps({
    "base": pins["base"], "tree": pins["tree"], "product_files": product,
    "diff_sha256": sha((ROOT/"product.diff").read_bytes()), "unchanged_selected_files": 28,
    "baseline_and_control_source_pins_unchanged": True,
    "final_resource_state": guard()}, indent=2)+"\n")
print(json.dumps({"product": product, "source_pins_unchanged": True, "resource": guard()}), flush=True)
