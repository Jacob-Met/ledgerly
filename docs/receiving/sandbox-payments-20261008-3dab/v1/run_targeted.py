import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path("/dev/shm/memory-delivery-ledgerly-3dab")
PYTHON = "/workspace/scratch/3dab0b9d2ce9/canvaspilot-product/test-env/bin/python"
EVIDENCE = ROOT / "receiving"
TEST = ROOT / "candidate/tests/test_sandbox_payment_admission.py"
BODY = r"""import hashlib,json,sys,unittest
from pathlib import Path
suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern="test_sandbox_payment_admission.py")
modules={}
for name in ["ledgerly","ledgerly.agent","ledgerly.paypal","ledgerly.extract","review","test_sandbox_payment_admission"]:
    m=sys.modules.get(name)
    if m is not None and getattr(m,"__file__",None):
        p=Path(m.__file__).resolve();modules[name]={"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
m=sys.modules["test_sandbox_payment_admission"].bridge
p=Path(m.__file__).resolve();modules["bridge"]={"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
print(json.dumps({"runtime":sys.version,"loaded":modules}),flush=True)
r=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not r.wasSuccessful())
"""
def pins(source):
    files = {}
    for pattern in ("ledgerly/*.py", "tests/*.py", "fixtures/*.txt", "web-demo/python/*.py"):
        for path in source.glob(pattern):
            files[str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files

runs = []
for label, directory in (("before", "current-before"), ("candidate", "candidate")):
    source = ROOT / directory
    before = pins(source)
    for mode in ("normal", "optimized"):
        argv = [PYTHON, "-B"] + (["-O"] if mode == "optimized" else []) + ["-c", BODY, str(TEST.parent)]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(source)}
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(argv, cwd=source, env=env, capture_output=True, text=True)
        prefix = EVIDENCE / f"targeted-{label}-{mode}"
        stdout = prefix.with_suffix(".stdout")
        stderr = prefix.with_suffix(".stderr")
        stdout.write_text(result.stdout)
        stderr.write_text(result.stderr)
        after = pins(source)
        if before != after:
            raise RuntimeError("Source changed during receiving")
        row = {"subject": label, "mode": mode, "started_utc": started, "argv": argv,
               "cwd": str(source), "environment": {"PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"},
               "exit_code": result.returncode, "stdout": stdout.name, "stderr": stderr.name,
               "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
               "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest(),
               "source_unchanged": True, "source_files": len(before),
               "test_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
               "methods": int(re.search(r"Ran (\d+) tests", result.stderr).group(1)),
               "result_summary": result.stderr.strip().splitlines()[-1]}
        runs.append(row)
        print(json.dumps({k: row[k] for k in ("subject", "mode", "exit_code", "methods", "result_summary", "source_unchanged")}), flush=True)
(EVIDENCE / "targeted-receipt.json").write_text(json.dumps(runs, indent=2) + "\n")
