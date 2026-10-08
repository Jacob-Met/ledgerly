"""Qualify the real built approval preview with synthetic input in native Chrome.

Serves one supplied dist directory on loopback, blocks off-origin requests, and
observes actual Worker messages without replacing the worker or Python results.
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
window.__approvalPreviewObservation = {sent: [], received: []};
const NativeWorker = window.Worker;
window.Worker = class extends NativeWorker {
  constructor(url, options) {
    super(url, options);
    this.addEventListener('message', event => {
      window.__approvalPreviewObservation.received.push(structuredClone(event.data));
    });
  }
  postMessage(message, ...rest) {
    window.__approvalPreviewObservation.sent.push(structuredClone(message));
    return super.postMessage(message, ...rest);
  }
};
"""

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

def run(source: Path, dist: Path, chrome: str, output: Path, baseline: bool):
    output.mkdir(parents=True, exist_ok=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(dist)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_port) + "/"
    origin = urlparse(url)
    report = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "source": str(source), "dist": str(dist), "host": platform.platform(),
              "baseline": baseline, "url": url, "checks": [], "page_errors": [], "off_origin": [],
              "chrome": subprocess.run([chrome, "--version"], capture_output=True, text=True).stdout.strip(),
              "source_files": {}, "dist_files": {}}
    for name in ("web-demo/src/main.ts", "web-demo/src/approval-preview.ts", "web-demo/src/approval-preview.css",
                 "web-demo/python/bridge.py", "ledgerly/agent.py", "ledgerly/extract.py", "ledgerly/paypal.py"):
        path = source / name
        if path.exists():
            report["source_files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["dist_files"] = {str(path.relative_to(dist)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in dist.rglob("*") if path.is_file()}
    def check(viewport, name, **details):
        report["checks"].append({"viewport": viewport, "name": name, "passed": True, **details})
        (output / "browser.json").write_text(json.dumps(report, indent=2) + "\n")
    try:
        with sync_playwright() as playwright:
            sizes = [("desktop", {"width": 1440, "height": 1000})]
            if not baseline:
                sizes.append(("phone", {"width": 390, "height": 844}))
            for label, size in sizes:
                profile = output / ("profile-" + label)
                context = playwright.chromium.launch_persistent_context(
                    str(profile), headless=True, executable_path=chrome, viewport=size)
                try:
                    def route(request_route):
                        target = urlparse(request_route.request.url)
                        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
                            report["off_origin"].append(request_route.request.url)
                            request_route.abort()
                        else:
                            request_route.continue_()
                    context.route("**/*", route)
                    context.add_init_script(OBSERVER)
                    page = context.pages[0]
                    page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
                    page.goto(url)
                    page.locator("#engine-start").click()
                    expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                    def idle():
                        expect(page.locator("#job-email")).to_be_enabled()
                    def state():
                        return page.evaluate("window.__approvalPreviewObservation.received.filter(x=>x.data?.state).at(-1).data.state")
                    def messages():
                        return page.evaluate("window.__approvalPreviewObservation.sent.length")
                    def load_and_analyze(name):
                        page.locator("#fixture-select").select_option(name)
                        page.locator("#load-fixture").click()
                        idle()
                        page.locator("#analyze").click()
                        idle()
                    def approve(action_id):
                        page.locator('[data-approve="' + action_id + '"]').click()
                        idle()
                    def reject(action_id):
                        page.locator('[data-reject="' + action_id + '"]').click()
                        idle()
                    load_and_analyze("05_missing_email.txt")
                    page.locator("#review-editor summary").click()
                    name = 'Queued <review> & "client"'
                    description = 'Authored <img src=x onerror="window.previewInjected=1"> résumé خدمة'
                    page.locator("#review-client-name").fill(name)
                    page.locator("#review-client-email").fill("queued-preview@example.test")
                    page.locator("#review-due-days").fill("0")
                    page.locator("#review-amount-paid").fill("20.00")
                    page.locator("#review-line-0-desc").fill(description)
                    page.locator("#review-confirm").check()
                    page.locator("#review-check").click()
                    idle()
                    expect(page.locator("#draft")).to_be_enabled()
                    page.locator("#draft").click()
                    idle()
                    expect(page.locator("#approval-list .approval-card")).to_have_count(1)
                    queued = state()["pending"][0]
                    assert queued["kind"] == "send_invoice"
                    invoice = queued["payload"]["invoice"]
                    assert invoice["items"][0]["name"] == description
                    assert invoice["detail"]["payment_term"]["term_type"] == "DUE_ON_RECEIPT"
                    assert state()["ledger"][0]["status"] == "DRAFT"
                    card = page.locator("#approval-list .approval-card")
                    if baseline:
                        witness = {"queued_action_id": queued["id"], "queued_payload_has_invoice": True,
                                   "queued_recipient": "queued-preview@example.test", "queued_item": description,
                                   "preview_count": card.locator(".approval-preview").count(),
                                   "item_text_visible": description in card.inner_text(),
                                   "mock_requests": state()["mock_requests"], "external_calls": state()["external_calls"]}
                        assert witness["preview_count"] == 0 and not witness["item_text_visible"]
                        report["baseline_missing_invoice_preview"] = witness
                        card.screenshot(path=str(output / "baseline-hidden-invoice.png"))
                        approve(queued["id"])
                        due = datetime.date.fromisoformat(state()["ledger"][0]["due_on"])
                        page.locator("#demo-date").fill((due + datetime.timedelta(days=2)).isoformat())
                        page.locator("#advance-clock").click()
                        idle()
                        page.locator("#run-chase").click()
                        idle()
                        reminder = state()["pending"][0]
                        body = reminder["payload"]["note"]
                        witness = {"queued_action_id": reminder["id"], "subject": reminder["payload"]["subject"],
                                   "note": body, "subject_visible": reminder["payload"]["subject"] in page.locator("#approval-list").inner_text(),
                                   "message_visible": body in page.locator("#approval-list").inner_text(),
                                   "external_calls": state()["external_calls"]}
                        assert not witness["subject_visible"] and not witness["message_visible"]
                        report["baseline_missing_reminder_preview"] = witness
                        page.locator("#approval-list").screenshot(path=str(output / "baseline-hidden-reminder.png"))
                        continue
                    expect(card.locator(".approval-preview")).to_have_count(1)
                    expect(card).to_contain_text(description)
                    expect(card).to_contain_text(name)
                    expect(card).to_contain_text("queued-preview@example.test")
                    expect(card).to_contain_text("Due on receipt")
                    expect(card).to_contain_text("USD " + queued["payload"]["prepaid"])
                    assert card.locator("script,img").count() == 0
                    assert page.evaluate("window.previewInjected") is None
                    assert "Due date" not in card.locator(".approval-fields").inner_text()
                    for item in invoice["items"]:
                        expect(card).to_contain_text(item["name"])
                        expect(card).to_contain_text(item["unit_amount"]["currency_code"] + " " + item["unit_amount"]["value"])
                    check(label, "actual_queued_invoice_fields_are_literal_and_exact", action_id=queued["id"], note=invoice["detail"]["note"])
                    before_messages, before_requests = messages(), state()["mock_requests"]
                    disclosure = card.locator("summary")
                    disclosure.focus()
                    page.keyboard.press("Enter")
                    expect(card.locator("details")).not_to_have_attribute("open", "")
                    page.keyboard.press("Enter")
                    expect(card.locator("details")).to_have_attribute("open", "")
                    assert messages() == before_messages and state()["mock_requests"] == before_requests
                    assert state()["pending"][0] == queued
                    check(label, "keyboard_disclosure_has_no_worker_or_approval_effect", mock_requests=before_requests)
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    card.screenshot(path=str(output / (label + "-queued-invoice.png")))
                    load_and_analyze("02_gbp_proofreading.txt")
                    expect(card).to_contain_text("queued-preview@example.test")
                    expect(card).to_contain_text(description)
                    assert state()["pending"][0] == queued
                    assert state()["mock_requests"] == before_requests
                    check(label, "new_analysis_keeps_queued_invoice_content")
                    approve(queued["id"])
                    expect(page.locator("#approval-list .approval-card")).to_have_count(0)
                    assert state()["ledger"][0]["status"] == "PARTIALLY_PAID"
                    assert state()["ledger"][0]["due_on"] == state()["today"]
                    check(label, "existing_approve_sends_only_selected_invoice_and_records_prior_payment")
                    due = datetime.date.fromisoformat(state()["ledger"][0]["due_on"])
                    page.locator("#demo-date").fill((due + datetime.timedelta(days=2)).isoformat())
                    page.locator("#advance-clock").click()
                    idle()
                    page.locator("#run-chase").click()
                    idle()
                    reminder = state()["pending"][0]
                    assert reminder["kind"] == "send_reminder"
                    note = page.locator("[data-preview-reminder-note]")
                    assert note.text_content() == reminder["payload"]["note"]
                    expect(page.locator("#approval-list .approval-fields")).to_contain_text(reminder["payload"]["subject"])
                    before_messages, before_requests = messages(), state()["mock_requests"]
                    selected = note.evaluate("(element)=>{const range=document.createRange();range.selectNodeContents(element);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);return selection.toString();}")
                    assert selected == reminder["payload"]["note"]
                    page.evaluate("getSelection().removeAllRanges()")
                    assert messages() == before_messages and state()["mock_requests"] == before_requests
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    page.locator("#approval-list").screenshot(path=str(output / (label + "-queued-reminder.png")))
                    check(label, "exact_subject_and_multiline_message_are_selectable_without_effect", action_id=reminder["id"],
                          subject=reminder["payload"]["subject"], note=reminder["payload"]["note"])
                    page.locator("#demo-date").fill((due + datetime.timedelta(days=3)).isoformat())
                    page.locator("#advance-clock").click()
                    idle()
                    expect(page.locator("[data-preview-reminder-note]")).to_have_count(0)
                    assert state()["pending"] == []
                    page.locator("#run-chase").click()
                    idle()
                    next_reminder = state()["pending"][0]
                    assert next_reminder["id"] != reminder["id"]
                    assert page.locator("[data-preview-reminder-note]").text_content() == next_reminder["payload"]["note"]
                    reject(next_reminder["id"])
                    assert state()["pending"] == [] and state()["ledger"][0]["reminders_sent"] == 0
                    page.locator("#run-chase").click()
                    idle()
                    last = state()["pending"][0]
                    approve(last["id"])
                    assert state()["pending"] == [] and state()["ledger"][0]["reminders_sent"] == 1
                    check(label, "invalidated_preview_removed_and_existing_reject_approve_bind_to_current_action")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.locator("#reset-sandbox").click()
                    idle()
                    load_and_analyze("04_multi_currency.txt")
                    page.locator("#draft").click()
                    idle()
                    split = state()["pending"]
                    assert len(split) == 2
                    for action in split:
                        preview = page.locator('[data-approval-id="' + action["id"] + '"]')
                        expect(preview).to_contain_text(action["payload"]["invoice"]["items"][0]["unit_amount"]["currency_code"])
                    reject(split[0]["id"])
                    assert [action["id"] for action in state()["pending"]] == [split[1]["id"]]
                    approve(split[1]["id"])
                    assert state()["pending"] == []
                    statuses = {entry["invoice_id"]: entry["status"] for entry in state()["ledger"]}
                    assert statuses[split[0]["invoice_id"]] == "DRAFT" and statuses[split[1]["invoice_id"]] == "SENT"
                    assert state()["external_calls"] == 0
                    check(label, "separate_currency_cards_keep_action_identity_through_reject_and_approve")
                    (output / (label + "-worker-observation.json")).write_text(json.dumps(
                        page.evaluate("window.__approvalPreviewObservation"), indent=2) + "\n")
                finally:
                    context.close()
                    if profile.exists():
                        shutil.rmtree(profile)
        if report["page_errors"] or report["off_origin"]:
            raise AssertionError("Unexpected browser error or off-origin request")
        report["ok"] = not baseline
        if baseline:
            report["expected_missing_capability_demonstrated"] = True
    except Exception as error:
        report["ok"] = False
        report["error"] = repr(error)
        report["traceback"] = traceback.format_exc()
    finally:
        server.shutdown()
        server.server_close()
        report["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report["source_unchanged"] = all(hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
                                          for name, digest in report["source_files"].items())
        report["ok"] = report.get("ok", False) and report["source_unchanged"]
        (output / "browser.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"ok": report["ok"], "checks": len(report["checks"]), "baseline": baseline,
                          "expected_missing_capability_demonstrated": report.get("expected_missing_capability_demonstrated", False),
                          "page_errors": report["page_errors"], "off_origin": report["off_origin"],
                          "source_unchanged": report["source_unchanged"], "error": report.get("error")}))
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.source.resolve(), args.dist.resolve(), args.chrome, args.output.resolve(), args.baseline))
