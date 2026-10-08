import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

root = Path("/dev/shm/memory-delivery-ledgerly-3dab")
evidence = root / "receiving-v2"
source = root / "candidate-v2"
py = "/workspace/scratch/3dab0b9d2ce9/canvaspilot-product/test-env/bin/python"
freeze = json.loads((evidence / "source-freeze-v2.json").read_text())
def verify():
    for name, row in freeze["subjects"]["candidate"]["files"].items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != row["sha256"]:
            raise RuntimeError("Source drift: " + name)

runs = []
for mode in ("normal", "optimized"):
    verify()
    argv = [py, "-B"] + (["-O"] if mode == "optimized" else []) + [
        "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "--basetemp=" + str(root / ("pytest-v2-tmp-" + mode))]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LEDGERLY_ALLOW_NETWORK": "0",
           "TMPDIR": str(root)}
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=source, env=env, capture_output=True, text=True)
    stdout = evidence / ("full-native-" + mode + ".stdout")
    stderr = evidence / ("full-native-" + mode + ".stderr")
    stdout.write_text(result.stdout)
    stderr.write_text(result.stderr)
    verify()
    row = {"mode": mode, "argv": argv, "cwd": str(source), "started_utc": started,
           "exit_code": result.returncode, "source_unchanged": True,
           "source_manifest_sha256": hashlib.sha256((evidence/"source-freeze-v2.json").read_bytes()).hexdigest(),
           "stdout": stdout.name, "stderr": stderr.name,
           "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
           "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest()}
    runs.append(row)
    print(json.dumps(row), flush=True)
    print(result.stdout[-3500:], flush=True)
    print(result.stderr[-500:], flush=True)
(evidence / "full-native-receipt.json").write_text(json.dumps(runs, indent=2) + "\n")
