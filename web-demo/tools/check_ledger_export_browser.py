"""Receive the built ledger CSV workflow against real browser/Python snapshots.

Run against a loopback-only temporary server; no provider requests are allowed.
Requires Playwright and an installed Chrome/Chromium. All inputs are fictional.
"""
import argparse
import base64
import platform
import subprocess
from importlib.metadata import version
import csv
import functools
import hashlib
import io
import json
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

HEADERS = [
    "Record type", "Snapshot date", "Invoice ID", "Invoice number", "Client name",
    "Client email", "Currency", "Total", "Paid", "Balance", "Status", "Sent date",
    "Due date", "Reminders sent",
]
CORRECTED_NAME = '=SUM(1,2) — 佐藤 "Studio"'
OBSERVER = """
(() => {
  const NativeWorker = window.Worker;
  const r = window.__ledgerReceiving = {workers: [], requests: [], states: [], replies: [], holdNext: false, held: null, objectUrls: 0};
  const nativeObjectURL = URL.createObjectURL;
  URL.createObjectURL = function(...args) { r.objectUrls++; return nativeObjectURL.apply(this, args); };
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      r.workers.push(this);
      this.addEventListener('message', event => {
        const value = event.data;
        if (value.id) r.replies.push(value.id);
        if (value.data?.state) r.states.push(JSON.parse(JSON.stringify(value.data.state)));
      });
    }
    postMessage(message, ...rest) {
      r.requests.push({id: message.id, action: message.action});
      if (r.holdNext) {
        r.holdNext = false;
        r.held = () => { r.held = null; super.postMessage(message, ...rest); };
        return;
      }
      super.postMessage(message, ...rest);
    }
  };
})();
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def view(page):
    return page.evaluate("""() => ({
      state: window.__ledgerReceiving.states.at(-1),
      requests: window.__ledgerReceiving.requests,
      mock: document.querySelector('#mock-requests').textContent,
      external: document.querySelector('#external-calls').textContent
    })""")


def settle(page):
    page.wait_for_function("""() => {
      const r = window.__ledgerReceiving, request = r.requests.at(-1);
      return request && r.replies.includes(request.id);
    }""", timeout=60000)
    expect(page.locator("#analyze")).to_be_enabled()


def action(page, selector):
    before = page.evaluate("window.__ledgerReceiving.requests.length")
    page.locator(selector).first.click()
    page.wait_for_function("(n) => window.__ledgerReceiving.requests.length > n", arg=before)
    settle(page)


def fixture(page, filename):
    page.locator("#fixture-select").select_option(filename)
    page.locator("#load-fixture").click()
    expect(page.locator("#analyze")).to_be_enabled()
    action(page, "#analyze")


def expected_rows(state):
    rows = [HEADERS]
    for e in state["ledger"]:
        name = e.get("client_name") or ""
        # This fixture's formula-like name has an explicitly documented literal prefix.
        if name == CORRECTED_NAME:
            name = "'" + name
        rows.append([
            "SANDBOX", state["today"], e["invoice_id"], e["invoice_number"],
            name, e["client_email"], e["currency"], e["total"], e["paid_amount"],
            e["balance"], e["status"], e.get("sent_on") or "", e.get("due_on") or "",
            str(e["reminders_sent"]),
        ])
    return rows


def print_bundle(output):
    records = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            records.append({"path": str(path.relative_to(output)), "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "base64": base64.b64encode(data).decode("ascii")})
    total = sum(record["bytes"] for record in records)
    if total > 2 * 1024 * 1024:
        raise ValueError("Receiving packet exceeds 2 MiB; refusing to truncate its evidence.")
    payload = json.dumps({"version": 1, "files": records}, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = [encoded[i:i + 4096] for i in range(0, len(encoded), 4096)]
    print("LEDGERLY_CSV_BUNDLE_BEGIN " + json.dumps({
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "chunks": len(chunks)}))
    for index, chunk in enumerate(chunks):
        print("LEDGERLY_CSV_BUNDLE_CHUNK " + str(index) + " " + chunk)
    print("LEDGERLY_CSV_BUNDLE_END", flush=True)


def run(dist, output, chrome, baseline=False, emit_bundle=False):
    dist, output = dist.resolve(), output.resolve()
    if not (dist / "index.html").is_file():
        raise ValueError("Supply an existing production build directory.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new or empty evidence directory.")
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(dist)))
    Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    errors, off_origin, downloads, checks = [], [], [], []
    source_root = Path(__file__).resolve().parents[1]
    try:
        checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        checkout = None
    source_paths = ["src/main.ts", "src/engine.worker.ts", "src/worker-client.ts",
                    "src/ledger-export.ts", "python/bridge.py", "index.html",
                    "tools/check_ledger_export_browser.py", "package-lock.json", "vite.config.ts"]
    result = {"ok": False, "baseline": baseline, "checks": checks, "downloads": downloads,
              "page_errors": errors, "off_origin_requests": off_origin, "checkout": checkout,
              "python": platform.python_version(), "platform": platform.platform(),
              "playwright": version("playwright"),
              "source_sha256": {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                                for name in source_paths if (source_root / name).is_file()},
              "dist_sha256": {str(path.relative_to(dist)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(dist.rglob("*")) if path.is_file()}}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=chrome, headless=True,
                args=["--no-first-run", "--no-default-browser-check", "--disable-background-networking"],
            )
            try:
                result["browser"] = browser.version
                context = browser.new_context(viewport={"width": 1360, "height": 1000}, accept_downloads=True)
                context.add_init_script(OBSERVER)

                def route(request_route):
                    url = request_route.request.url
                    parsed = urlparse(url)
                    if parsed.scheme in {"data", "blob"} or (parsed.scheme + "://" + parsed.netloc) == origin:
                        request_route.continue_()
                    else:
                        off_origin.append(url)
                        request_route.abort()

                context.route("**/*", route)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                seen_downloads = []
                page.on("download", lambda item: seen_downloads.append(item.suggested_filename))
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto(origin)
                button = page.locator("#ledger-export")
                if not baseline:
                    expect(button).to_be_disabled()
                page.locator("#engine-start").click()
                expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                if not baseline:
                    expect(button).to_be_disabled()
                    checks.append("disabled before ready and for empty ledger")
                fixture(page, "04_multi_currency.txt")
                action(page, "#draft")
                expect(page.locator("#ledger-list .invoice-card")).to_have_count(2)
                state = view(page)["state"]
                assert len({e["currency"] for e in state["ledger"]}) == 2
                assert all(e["status"] == "DRAFT" for e in state["ledger"])
                if baseline:
                    expect(button).to_have_count(0)
                    checks.append("real Python creates two currency-specific drafts; export control absent")
                    (output / "baseline-snapshot.json").write_text(json.dumps(state, indent=2) + "\n")
                    page.locator(".ledger-panel").screenshot(path=str(output / "baseline-ledger.png"))
                    assert not errors and not off_origin
                    result["ok"] = True
                    return result

                def download(label, keyboard=False):
                    before = view(page)
                    expect(button).to_be_enabled()
                    with page.expect_download() as pending:
                        if keyboard:
                            button.focus()
                            page.keyboard.press("Enter")
                        else:
                            button.click()
                    item = pending.value
                    assert item.suggested_filename == "ledgerly-sandbox-" + before["state"]["today"] + ".csv"
                    target = output / (label + ".csv")
                    item.save_as(str(target))
                    data = target.read_bytes()
                    assert data.startswith(b"\xef\xbb\xbf") and data.endswith(b"\r\n")
                    parsed = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))
                    expected = expected_rows(before["state"])
                    assert parsed == expected, (label, parsed, expected)
                    canonical = io.StringIO(newline="")
                    csv.writer(canonical, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(expected)
                    assert data == b"\xef\xbb\xbf" + canonical.getvalue().encode("utf-8"), "Noncanonical CSV bytes"
                    after = view(page)
                    assert before == after, "Download changed the snapshot or made a Worker request"
                    (output / (label + "-snapshot.json")).write_text(json.dumps(before, indent=2) + "\n")
                    downloads.append({"case": label, "filename": item.suggested_filename,
                                      "rows": len(parsed) - 1, "sha256": hashlib.sha256(data).hexdigest(),
                                      "exact_snapshot_fields": True, "canonical_file_bytes": True,
                                      "state_and_requests_unchanged": True})
                    return data

                download("01-drafts")
                while page.locator("[data-approve]").count():
                    action(page, "[data-approve]:first-of-type")
                assert all(e["status"] == "SENT" for e in view(page)["state"]["ledger"])
                download("02-sent")
                page.locator("#payment-amount").fill("1")
                action(page, "[data-pay]:first-of-type")
                assert view(page)["state"]["ledger"][0]["status"] == "PARTIALLY_PAID"
                download("03-partial-payment")
                page.locator(".ledger-panel").screenshot(path=str(output / "desktop-ledger.png"))

                later = max(date.fromisoformat(e["due_on"]) for e in view(page)["state"]["ledger"]) + timedelta(days=1)
                page.locator("#demo-date").fill(later.isoformat())
                page.evaluate("window.__ledgerReceiving.holdNext = true")
                page.locator("#advance-clock").click()
                page.wait_for_function("window.__ledgerReceiving.held !== null")
                expect(button).to_be_disabled()
                count = len(seen_downloads)
                object_urls = page.evaluate("window.__ledgerReceiving.objectUrls")
                button.evaluate("button => { button.click(); button.dispatchEvent(new MouseEvent(\'click\', {bubbles: true})); }")
                assert page.evaluate("window.__ledgerReceiving.objectUrls") == object_urls
                assert len(seen_downloads) == count
                page.evaluate("window.__ledgerReceiving.held()")
                settle(page)
                checks.append("disabled UI and controller guard during an actual pending Worker action")
                action(page, "#run-chase")
                while page.locator("[data-approve]").count():
                    action(page, "[data-approve]:first-of-type")
                assert any(e["reminders_sent"] > 0 for e in view(page)["state"]["ledger"])
                download("04-reminders")

                fixture(page, "01_simple_usd_hourly.txt")
                page.locator("#review-editor summary").click()
                page.get_by_label("Client name", exact=True).fill(CORRECTED_NAME)
                page.locator("#review-confirm").check()
                action(page, "#review-check")
                expect(page.locator("#review-result")).to_contain_text("Checked human input")
                action(page, "#draft")
                assert view(page)["state"]["ledger"][-1]["client_name"] == CORRECTED_NAME
                corrected = download("05-corrected-name")
                assert download("06-repeat") == corrected
                checks.append("actual human correction retains Unicode/commas/quotes with documented formula prefix")
                before = view(page)
                count = len(seen_downloads)
                page.evaluate("""() => {
                  const native = URL.createObjectURL;
                  let once = true;
                  URL.createObjectURL = function(...args) {
                    if (once) { once = false; throw new Error('Injected local download failure'); }
                    return native.apply(this, args);
                  };
                }""")
                button.click()
                expect(page.locator("#ledger-export-note")).to_contain_text("could not start")
                assert view(page) == before and len(seen_downloads) == count
                assert download("07-retry") == corrected
                checks.append("failed browser download has no effects and explicit retry retains exact bytes")

                page.set_viewport_size({"width": 390, "height": 844})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                assert download("08-phone-keyboard", keyboard=True) == corrected
                page.locator(".ledger-panel").screenshot(path=str(output / "phone-ledger.png"))
                checks.append("390px layout without overflow and focused Enter activation")

                action(page, "#reset-sandbox")
                expect(button).to_be_disabled()
                assert not view(page)["state"]["ledger"]
                assert (output / "05-corrected-name.csv").read_bytes() == corrected
                checks.append("reset disables empty export without deleting an explicitly downloaded file")
                fixture(page, "01_simple_usd_hourly.txt")
                action(page, "#draft")
                expect(button).to_be_enabled()
                preserved = view(page)
                page.evaluate("""() => window.__ledgerReceiving.workers.at(-1).dispatchEvent(
                  new ErrorEvent('error', {message: 'Injected receiving Worker loss'}))""")
                expect(page.locator("#engine-status")).to_have_text("PYTHON UNAVAILABLE")
                expect(button).to_be_disabled()
                assert view(page) == preserved
                count = len(seen_downloads)
                object_urls = page.evaluate("window.__ledgerReceiving.objectUrls")
                button.evaluate("button => { button.click(); button.dispatchEvent(new MouseEvent(\'click\', {bubbles: true})); }")
                assert page.evaluate("window.__ledgerReceiving.objectUrls") == object_urls
                assert len(seen_downloads) == count
                page.locator("#engine-start").click()
                expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                expect(button).to_be_disabled()
                assert not view(page)["state"]["ledger"]
                checks.append("synthetic terminal Worker error blocks stale ledger through UI and controller guard; explicit restart starts empty")
                assert not errors and not off_origin
                result["ok"] = True
                return result
            except Exception:
                if "page" in locals() and not page.is_closed():
                    try:
                        page.screenshot(path=str(output / "failure.png"))
                    except Exception as screenshot_error:
                        result["screenshot_error"] = str(screenshot_error)
                raise
            finally:
                browser.close()
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        server.shutdown()
        server.server_close()
        (output / "browser-receiving.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        if emit_bundle:
            print_bundle(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--emit-bundle", action="store_true")
    args = parser.parse_args()
    run(args.dist, args.output, args.chrome, args.baseline, args.emit_bundle)
