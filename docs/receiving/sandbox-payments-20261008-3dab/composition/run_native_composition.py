"""Run the bounded payment/invoice-details composition against a pinned checkout."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import unittest
import urllib.request
from datetime import datetime, timezone

SOURCE = Path(sys.argv[1]).resolve()
MANIFEST = Path(sys.argv[2]).resolve()
freeze = json.loads(MANIFEST.read_text())
def verify():
    actual = {}
    for name, row in freeze["files"].items():
        raw = (SOURCE / name).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != row["sha256"]:
            raise RuntimeError("Source changed: " + name)
        actual[name] = sha
    return actual
before = verify()
os.environ["LEDGERLY_ALLOW_NETWORK"] = "0"
attempts = []
def forbidden(*args, **kwargs):
    attempts.append("network/provider entry")
    raise RuntimeError("Network and provider operations forbidden in authored receiving")
socket.create_connection = forbidden
urllib.request.urlopen = forbidden
sys.path[:0] = [str(SOURCE), str(SOURCE / "tests"), str(SOURCE / "web-demo/python")]
from ledgerly.paypal import HttpPayPalClient
HttpPayPalClient.__init__ = forbidden
suite = unittest.TestSuite()
names = ["test_sandbox_payment_admission", "test_browser_invoice_details"]
modules = []
for name in names:
    path = SOURCE / "tests" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    modules.append(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
started = datetime.now(timezone.utc).isoformat()
result = unittest.TextTestRunner(verbosity=2).run(suite)
after = verify()
origins = {}
for name, module in tuple(sys.modules.items()):
    p = getattr(module, "__file__", None)
    if p:
        path = Path(p).resolve()
        if path.is_relative_to(SOURCE):
            raw = path.read_bytes()
            origins[name] = {"path": str(path.relative_to(SOURCE)), "sha256": hashlib.sha256(raw).hexdigest()}
payload = {
    "started_utc": started, "python": sys.version, "optimize": sys.flags.optimize,
    "source": str(SOURCE), "base": freeze["base"], "tree": freeze["tree"],
    "source_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
    "runner_sha256": hashlib.sha256((globals().get("RUNNER_SOURCE") or Path(__file__).read_text()).encode()).hexdigest(),
    "test_modules": names, "methods": result.testsRun,
    "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
    "network_attempts": attempts, "source_before": before, "source_after": after,
    "loaded_source_origins": origins,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() and before == after and not attempts else 1)
