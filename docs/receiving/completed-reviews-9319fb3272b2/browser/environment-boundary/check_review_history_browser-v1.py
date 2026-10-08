"""Receive completed reviews through the actual built UI, Worker and Python.

Uses one isolated loopback server and owned Chromium profiles. The healthy path
does not replace replies. A separate, labeled fault path serves the same bridge
with a receiving-only lost-response suffix; its real SandboxMock send completes
before TimeoutError. Production files are hashed before and after both paths.
"""
from __future__ import annotations
import argparse
import datetime
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import traceback
from urllib.parse import urlparse
from playwright.sync_api import expect, sync_playwright

OBSERVER = """
window.__historyObservation = {sent: [], received: [], workerCount: 0};
window.__historyWorkers = [];
const NativeWorker = window.Worker;
window.Worker = class extends NativeWorker {
  constructor(url, options) {
    super(url, options);
    window.__historyWorkers.push(this);
    window.__historyObservation.workerCount++;
    this.addEventListener('message', event => {
      window.__historyObservation.received.push(structuredClone(event.data));
    });
  }
  postMessage(message, ...rest) {
    window.__historyObservation.sent.push(structuredClone(message));
    return super.postMessage(message, ...rest);
  }
};
"""
FAULT_SUFFIX = """
# Receiving-only injection: the real mock send succeeds before its response is lost.
_history_original_handle_json = handle_json
_history_lost_response_used = False
def handle_json(raw):
    global _history_lost_response_used
    request = json.loads(raw)
    if request.get("action") != "approve" or _history_lost_response_used:
        return _history_original_handle_json(raw)
    _history_lost_response_used = True
    original_send = SESSION.mock.send_invoice
    def send_then_lose_response(*args, **kwargs):
        original_send(*args, **kwargs)
        raise TimeoutError("Receiving-only lost response after the real mock send")
    SESSION.mock.send_invoice = send_then_lose_response
    try:
        return _history_original_handle_json(raw)
    finally:
        SESSION.mock.send_invoice = original_send
"""

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(source, dist, chrome, output, manifest):
    output.mkdir(parents=True, exist_ok=False)
    binding = json.loads(manifest.read_text())
    declared = binding["files"]
    report = {
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": str(source), "dist": str(dist), "source_pin": binding["source_pin"],
        "binding_sha256": sha(manifest), "driver_sha256": sha(Path(__file__)),
        "host": platform.platform(), "checks": [], "page_errors": [], "off_origin": [],
        "chrome": subprocess.check_output([chrome, "--version"], text=True).strip(),
        "source_files": {}, "dist_files": {}, "served_python": {},
        "fault": {"kind": "real mock send followed by authored lost response",
                  "suffix_sha256": hashlib.sha256(FAULT_SUFFIX.encode()).hexdigest(),
                  "bridge_served": 0},
        "ok": False,
    }
    for row in declared:
        data = (source / row["path"]).read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if git_blob != row["git_blob"]:
            raise AssertionError("Declared source binding differs: " + row["path"])
        report["source_files"][row["path"]] = hashlib.sha256(data).hexdigest()
    report["dist_files"] = {
        str(p.relative_to(dist)): sha(p) for p in dist.rglob("*") if p.is_file()
    }
    (output / "source-binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    (output / "lost-response-suffix.py").write_text(FAULT_SUFFIX)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(dist)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_port) + "/"
    origin = urlparse(url)
    report["url"] = url
    def save():
        (output / "browser.json").write_text(json.dumps(report, indent=2) + "\n")
    def check(name, condition=True, **details):
        report["checks"].append({"name": name, "passed": bool(condition), **details})
        save()
        if not condition:
            raise AssertionError(name)
    def fixture(page, name):
        page.locator("#fixture-select").select_option(name)
        page.locator("#load-fixture").click()
        expect(page.locator("#job-email")).to_be_enabled()
        page.locator("#analyze").click()
        expect(page.locator("#job-email")).to_be_enabled()
    def idle(page):
        expect(page.locator("#job-email")).to_be_enabled()
    def state(page):
        return page.evaluate("window.__historyObservation.received.filter(x=>x.data?.state).at(-1).data.state")
    def messages(page):
        return page.evaluate("window.__historyObservation.sent.length")
    def rows(page):
        return state(page)["completed_reviews"]
    def row(page, action_id):
        return next(x for x in rows(page) if x["id"] == action_id)
    def panel(page, action_id):
        return page.locator('details.completed-review[data-review-id="' + action_id + '"]')
    def approve(page, action_id):
        page.locator('[data-approve="' + action_id + '"]').focus()
        page.keyboard.press("Enter")
        idle(page)
    def reject(page, action_id):
        page.locator('[data-reject="' + action_id + '"]').click()
        idle(page)
    def assert_proposal(page, queued, expected_status):
        current = row(page, queued["id"])
        check("retained_original_" + expected_status.lower(),
              current["payload"] == queued["payload"] and current["status"] == expected_status
              and current["created_at"] == queued["created_at"], action_id=queued["id"])
        record = panel(page, queued["id"])
        record.locator(":scope > summary").focus()
        if not record.evaluate("element=>element.open"):
            page.keyboard.press("Enter")
        expect(record).to_contain_text(queued["created_at"])
        expect(record).to_contain_text("Queued at")
        assert json.loads(record.locator("[data-review-result]").text_content()) == current["result"]
        assert record.locator("button,a,[data-approve],[data-reject],[data-pay]").count() == 0
        return record
    def snapshot_with_focus(page, action_id, nested):
        before = state(page)
        sent = messages(page)
        witness = page.evaluate("""({id,nested})=>{
          const outer=[...document.querySelectorAll('details.completed-review')]
            .find(x=>x.dataset.reviewId===id);
          outer.open=true;
          const target=nested?outer.querySelector('details.approval-preview'):outer;
          const summary=target.querySelector(':scope > summary');
          if (nested) { target.open=true; summary.click(); }
          summary.focus();
          const prior={outerOpen:outer.open,targetOpen:target.open,focused:document.activeElement===summary};
          document.querySelector('#analyze').click();
          return prior;
        }""", {"id": action_id, "nested": nested})
        idle(page)
        after = page.evaluate("""({id,nested})=>{
          const outer=[...document.querySelectorAll('details.completed-review')]
            .find(x=>x.dataset.reviewId===id);
          const target=nested?outer.querySelector('details.approval-preview'):outer;
          return {outerOpen:outer.open,targetOpen:target.open,
            focused:document.activeElement===target.querySelector(':scope > summary')};
        }""", {"id": action_id, "nested": nested})
        check("nested_disclosure_and_focus_survive_snapshot" if nested else "outer_disclosure_and_focus_survive_snapshot",
              witness["focused"] and after["outerOpen"] and after["focused"]
              and after["targetOpen"] == witness["targetOpen"]
              and messages(page) == sent + 1 and state(page)["mock_requests"] == before["mock_requests"]
              and rows(page) == before["completed_reviews"], before=witness, after=after,
              worker_messages_before=sent, worker_messages_after=messages(page))
    save()
    try:
        with sync_playwright() as playwright:
            for label in ("healthy", "lost-response"):
                profile = output / ("profile-" + label)
                profile.mkdir(exist_ok=False)
                context = playwright.chromium.launch_persistent_context(
                    str(profile), headless=True, executable_path=chrome,
                    viewport={"width": 1440, "height": 1000},
                    args=["--disk-cache-size=1048576", "--disable-background-networking"])
                page = None
                try:
                    def route(route):
                        requested = urlparse(route.request.url)
                        if (requested.scheme, requested.netloc) != (origin.scheme, origin.netloc):
                            report["off_origin"].append({"phase": label, "url": route.request.url})
                            route.abort()
                        elif requested.path.endswith("/python/bridge.py") and label == "lost-response":
                            raw = (dist / "python/bridge.py").read_bytes()
                            fault_bytes = raw + FAULT_SUFFIX.encode()
                            report["fault"]["bridge_served"] += 1
                            report["fault"]["original_bridge_sha256"] = hashlib.sha256(raw).hexdigest()
                            report["fault"]["served_bridge_sha256"] = hashlib.sha256(fault_bytes).hexdigest()
                            route.fulfill(status=200, body=fault_bytes, content_type="text/plain; charset=utf-8")
                        else:
                            if requested.path.startswith("/python/") and requested.path.endswith(".py"):
                                name = requested.path.lstrip("/")
                                report["served_python"][label + ":" + name] = sha(dist / name)
                            route.continue_()
                    context.route("**/*", route)
                    context.add_init_script(OBSERVER)
                    page = context.pages[0]
                    page.on("pageerror", lambda error: report["page_errors"].append({"phase": label, "error": str(error)}))
                    page.goto(url)
                    page.locator("#engine-start").click()
                    expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                    check(label + "_actual_empty_python_session", rows(page) == [] and state(page)["external_calls"] == 0)
                    fixture(page, "01_simple_usd_hourly.txt")
                    page.locator("#draft").click()
                    idle(page)
                    queued = state(page)["pending"][0]
                    check(label + "_pending_stays_out_of_history", rows(page) == [] and queued["kind"] == "send_invoice")
                    approve(page, queued["id"])
                    if label == "lost-response":
                        closed = row(page, queued["id"])
                        current = state(page)
                        provider = next(x["record"] for x in current["invoice_details"] if x["invoice_id"] == queued["invoice_id"])
                        ledger = next(x for x in current["ledger"] if x["invoice_id"] == queued["invoice_id"])
                        check("actual_send_then_lost_response_reaches_failed_unknown",
                              closed["status"] == "FAILED" and closed["result"]["outcome"] == "UNKNOWN"
                              and closed["result"]["error_type"] == "TimeoutError" and provider["status"] == "SENT"
                              and ledger["status"] == "DRAFT" and current["pending"] == [],
                              action_id=queued["id"], recorded_result=closed["result"],
                              actual_mock_status=provider["status"], agent_ledger_status=ledger["status"])
                        target = panel(page, queued["id"])
                        expect(target.locator(":scope > summary")).to_contain_text("FAILED · OUTCOME UNKNOWN")
                        check("unknown_visible_before_opening", not target.evaluate("element=>element.open"))
                        before, count = state(page), messages(page)
                        target = assert_proposal(page, queued, "FAILED")
                        expect(target).to_contain_text("Check the invoice before creating another approval.")
                        expect(target).to_contain_text(queued["payload"]["invoice"]["items"][0]["name"])
                        page.set_viewport_size({"width": 390, "height": 844})
                        target.screenshot(path=str(output / "phone-outcome-unknown.png"))
                        check("failed_history_read_has_no_retry_or_provider_effect",
                              messages(page) == count and state(page) == before
                              and not page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                        continue
                    target = assert_proposal(page, queued, "APPROVED")
                    invoice = queued["payload"]["invoice"]
                    expect(target).to_contain_text(invoice["items"][0]["name"])
                    expect(target).to_contain_text(invoice["items"][0]["unit_amount"]["value"])
                    before, count = state(page), messages(page)
                    target.locator(":scope > summary").focus()
                    page.keyboard.press("Enter")
                    page.keyboard.press("Enter")
                    selected = target.locator("[data-review-result]").evaluate("""element=>{
                      const range=document.createRange();range.selectNodeContents(element);
                      const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
                      return selection.toString();
                    }""")
                    page.evaluate("getSelection().removeAllRanges()")
                    check("keyboard_and_selection_are_read_only",
                          json.loads(selected) == row(page, queued["id"])["result"]
                          and state(page) == before and messages(page) == count)
                    snapshot_with_focus(page, queued["id"], nested=False)
                    snapshot_with_focus(page, queued["id"], nested=True)
                    target.locator("details.approval-preview > summary").click()
                    sibling = page.locator('details.invoice-details[data-invoice-detail-id="' + queued["invoice_id"] + '"]')
                    sibling.locator(":scope > summary").click()
                    expect(sibling).to_contain_text(invoice["items"][0]["name"])
                    check("invoice_details_still_opens_separately", sibling.evaluate("element=>element.open"))
                    fixture(page, "05_missing_email.txt")
                    page.locator("#review-editor > summary").click()
                    name = 'Zoë <img src=x onerror=window.historyInjected=1>'
                    description = 'Révision <script>literal()</script> — خدمة'
                    for selector, value in [
                        ("#review-client-name", name), ("#review-client-email", "history-receiver@example.test"),
                        ("#review-due-days", "30"), ("#review-amount-paid", "0"),
                        ("#review-line-0-desc", description), ("#review-line-0-qty", "1.50"),
                        ("#review-line-0-price", "80.00"), ("#review-line-0-unit", "hours"),
                    ]:
                        page.locator(selector).fill(value)
                    page.locator("#review-line-0-currency").select_option("EUR")
                    page.locator("#review-confirm").check()
                    page.locator("#review-check").click()
                    idle(page)
                    expect(page.locator("#draft")).to_be_enabled()
                    page.locator("#draft").click()
                    idle(page)
                    rejected = state(page)["pending"][0]
                    reject(page, rejected["id"])
                    target = assert_proposal(page, rejected, "REJECTED")
                    expect(target).to_contain_text(name)
                    expect(target).to_contain_text(description)
                    expect(target).to_contain_text("EUR 80.00")
                    expect(target).to_contain_text("1.50")
                    check("reviewed_literal_values_and_rejection_reason_preserved",
                          target.locator("img,script,svg").count() == 0
                          and page.evaluate("window.historyInjected") is None
                          and row(page, rejected["id"])["result"] == {"reason": "Rejected by the browser visitor"})
                    due = datetime.date.fromisoformat(next(x["due_on"] for x in state(page)["ledger"] if x["invoice_id"] == queued["invoice_id"]))
                    page.locator("#demo-date").fill((due + datetime.timedelta(days=1)).isoformat())
                    page.locator("#advance-clock").click()
                    idle(page)
                    page.locator("#run-chase").click()
                    idle(page)
                    reminder = next(x for x in state(page)["pending"] if x["kind"] == "send_reminder")
                    page.locator("#demo-date").fill((due + datetime.timedelta(days=2)).isoformat())
                    before_requests = state(page)["mock_requests"]
                    page.locator("#advance-clock").click()
                    idle(page)
                    target = assert_proposal(page, reminder, "REJECTED")
                    check("automatic_invalidation_keeps_its_actual_reason_and_message",
                          row(page, reminder["id"])["result"]["reason"].startswith("auto:")
                          and target.locator("[data-preview-reminder-note]").text_content() == reminder["payload"]["note"]
                          and state(page)["mock_requests"] == before_requests,
                          recorded_result=row(page, reminder["id"])["result"])
                    expect(target).to_contain_text(reminder["payload"]["subject"])
                    page.locator("#run-chase").click()
                    idle(page)
                    final_reminder = next(x for x in state(page)["pending"] if x["kind"] == "send_reminder")
                    approve(page, final_reminder["id"])
                    target = assert_proposal(page, final_reminder, "APPROVED")
                    check("explicit_reminder_approval_has_its_own_retained_identity",
                          final_reminder["id"] != reminder["id"]
                          and row(page, final_reminder["id"])["result"] == {"reminded": True}
                          and state(page)["pending"] == [])
                    history = page.locator("#completed-reviews-list")
                    history.screenshot(path=str(output / "desktop-completed-reviews.png"))
                    before, count = state(page), messages(page)
                    page.set_viewport_size({"width": 390, "height": 844})
                    target.screenshot(path=str(output / "phone-completed-reminder.png"))
                    literal = panel(page, rejected["id"])
                    literal.screenshot(path=str(output / "phone-literal-invoice.png"))
                    check("phone_history_is_legible_without_horizontal_scroll_or_worker_effect",
                          not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                          and messages(page) == count and state(page) == before)
                    retained = rows(page)
                    source_email = page.locator("#job-email").input_value()
                    count = messages(page)
                    page.evaluate("window.__historyWorkers.at(-1).dispatchEvent(new ErrorEvent('error',{message:'Authored receiving-only worker unavailable event'}))")
                    expect(page.locator("#engine-status")).to_have_text("PYTHON UNAVAILABLE")
                    expect(page.locator("#completed-reviews-note")).to_contain_text("last received reviews")
                    target.locator(":scope > summary").click()
                    check("authored_unavailability_labels_last_history_without_restart_or_replay",
                          messages(page) == count and rows(page) == retained
                          and page.evaluate("window.__historyObservation.workerCount") == 1,
                          injection="synthetic ErrorEvent on the actual Worker, not an observed spontaneous crash")
                    page.locator("#engine-start").click()
                    expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                    check("explicit_restart_opens_empty_history_and_keeps_source",
                          rows(page) == [] and state(page)["ledger"] == [] and state(page)["pending"] == []
                          and page.locator("#job-email").input_value() == source_email
                          and messages(page) == count + 1 and page.evaluate("window.__historyObservation.workerCount") == 2)
                    fixture(page, "01_simple_usd_hourly.txt")
                    page.locator("#draft").click()
                    idle(page)
                    reject(page, state(page)["pending"][0]["id"])
                    check("new_session_can_record_its_own_review", len(rows(page)) == 1)
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.locator("#reset-sandbox").click()
                    idle(page)
                    expect(page.locator("#completed-reviews-list")).to_contain_text("No completed reviews")
                    check("explicit_reset_clears_history", rows(page) == [] and state(page)["ledger"] == [])
                except Exception:
                    if page is not None:
                        try:
                            page.screenshot(path=str(output / (label + "-failure.png")), full_page=True)
                        except Exception as capture_error:
                            report["capture_error"] = repr(capture_error)
                    raise
                finally:
                    if page is not None:
                        (output / (label + "-worker-observation.json")).write_text(json.dumps(
                            page.evaluate("window.__historyObservation"), indent=2) + "\n")
                    context.close()
                    shutil.rmtree(profile)
        check("all_browser_requests_stayed_on_loopback", not report["off_origin"])
        check("no_uncaught_page_errors", not report["page_errors"])
        check("one_labeled_lost_response_bridge_served", report["fault"]["bridge_served"] == 1)
        report["ok"] = True
    except Exception as error:
        report["error"] = repr(error)
        report["traceback"] = traceback.format_exc()
    finally:
        server.shutdown()
        server.server_close()
        report["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report["source_unchanged"] = all(sha(source / name) == digest for name, digest in report["source_files"].items())
        report["dist_unchanged"] = all(sha(dist / name) == digest for name, digest in report["dist_files"].items())
        report["ok"] = report["ok"] and report["source_unchanged"] and report["dist_unchanged"]
        report["artifacts"] = [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(output.iterdir()) if p.is_file() and p.name != "browser.json"
        ]
        save()
        print(json.dumps({"ok": report["ok"], "checks": len(report["checks"]),
                          "source_unchanged": report["source_unchanged"], "dist_unchanged": report["dist_unchanged"],
                          "error": report.get("error"), "output": str(output)}))
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.source.resolve(), args.dist.resolve(), args.chrome,
                         args.output.resolve(), args.source_manifest.resolve()))
