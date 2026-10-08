"""Challenge the accepted history tests with two valid but wrong projections."""
import hashlib, json, os, pathlib, shutil, subprocess, time
root = pathlib.Path("/home/jacob/hamon-ultra-9319fb3272b2-integration-qa/ledgerly-history-5493205")
source = root / "candidate"
original_helper = (source / "web-demo/python/review_history.py").read_text()
original_test = (source / "tests/test_review_history.py").read_bytes()
controls = [
    ("drop-failed", original_helper.replace('("APPROVED", "REJECTED", "FAILED")', '("APPROVED", "REJECTED")'),
     "test_actual_send_then_lost_response_retains_unknown_without_replay"),
    ("shallow-alias", original_helper.replace("action.to_dict()", '{name: getattr(action, name) for name in ("id", "kind", "invoice_id", "summary", "payload", "status", "result", "created_at")}'),
     "test_original_proposal_and_result_are_detached_from_later_records"),
]
results = []
for label, helper, test in controls:
    assert helper != original_helper
    target = root / ("control-" + label)
    shutil.copytree(source, target)
    (target / "web-demo/python/review_history.py").write_text(helper)
    before = hashlib.sha256((target / "tests/test_review_history.py").read_bytes()).hexdigest()
    prefix = root / "receipts" / ("control-" + label)
    command = ["python3", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "tests/test_review_history.py::CompletedReviewTests::" + test]
    with pathlib.Path(str(prefix) + ".stdout.log").open("xb") as out, pathlib.Path(str(prefix) + ".stderr.log").open("xb") as err:
        run = subprocess.run(command, cwd=target, stdout=out, stderr=err,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=30)
    text = pathlib.Path(str(prefix) + ".stdout.log").read_text()
    stderr = pathlib.Path(str(prefix) + ".stderr.log").read_text()
    row = {"name": label, "command": command, "exit_code": run.returncode, "stdout": text, "stderr": stderr,
           "helper_sha256": hashlib.sha256(helper.encode()).hexdigest(),
           "unchanged_test_sha256": before, "oracle_unchanged": before == hashlib.sha256(original_test).hexdigest(),
           "semantic_failure": run.returncode == 1 and "AssertionError:" in text and "1 failed" in text and not stderr}
    results.append(row)
receipt = {"accepted_helper_sha256": hashlib.sha256(original_helper.encode()).hexdigest(),
           "accepted_test_sha256": hashlib.sha256(original_test).hexdigest(), "controls": results,
           "accepted_source_unchanged": (source / "web-demo/python/review_history.py").read_text() == original_helper and (source / "tests/test_review_history.py").read_bytes() == original_test}
with (root / "receipts/history-negative-controls.json").open("x") as f:
    json.dump(receipt, f, indent=2); f.write("\n")
print(json.dumps({"controls": [{"name": r["name"], "exit_code": r["exit_code"], "semantic_failure": r["semantic_failure"], "oracle_unchanged": r["oracle_unchanged"]} for r in results], "accepted_source_unchanged": receipt["accepted_source_unchanged"]}))
assert all(r["semantic_failure"] and r["oracle_unchanged"] for r in results) and receipt["accepted_source_unchanged"]
