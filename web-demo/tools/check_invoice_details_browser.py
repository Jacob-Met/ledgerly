#!/usr/bin/env python3
"""Exercise the production browser/Python invoice inspector with fictional data.

Owns a temporary loopback server and browser context. Requests leaving that
origin are refused. The observer records real Worker replies without replacing
the Python engine, its messages, or the application's event handlers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import traceback
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


SOURCE_PATHS = [
    "ledgerly/agent.py", "ledgerly/paypal.py", "ledgerly/extract.py",
    "web-demo/python/bridge.py", "web-demo/python/invoice_details.py",
    "web-demo/src/invoice-details.ts", "web-demo/src/invoice-details.css",
    "web-demo/src/main.ts", "web-demo/src/engine.worker.ts",
    "web-demo/src/approval-preview.ts", "web-demo/src/worker-client.ts",
]

OBSERVER = """(() => {
  const NativeWorker = window.Worker;
  window.__invoiceDetailProbe = {calls: [], states: [], workers: []};
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      window.__invoiceDetailProbe.workers.push(this);
      this.addEventListener('message', event => {
        if (event.data?.data?.state)
          window.__invoiceDetailProbe.states.push(JSON.parse(JSON.stringify(event.data.data.state)));
      });
    }
    postMessage(...args) {
      window.__invoiceDetailProbe.calls.push(JSON.parse(JSON.stringify(args[0])));
      return super.postMessage(...args);
    }
  };
})();"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build", type=Path)
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    build = (args.build or project / "web-demo/dist").resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    assert (build / "index.html").is_file(), "Build the actual production app first"
    report = {"schema": "ledgerly.invoice-details.browser-receiving.v1", "started_at": datetime.now(timezone.utc).isoformat(),
              "status": "running", "synthetic_only": True, "checks": [], "requests": [], "blocked_requests": [],
              "errors": [], "files": {}, "source": {p: sha(project / p) for p in SOURCE_PATHS}}

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(build)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    report["origin"] = origin
    browser = None

    def passed(label):
        report["checks"].append(label)
        print("PASS " + label, flush=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.chrome, headless=True,
                args=["--no-sandbox", "--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-first-run"])
            report["browser"] = browser.version
            context = browser.new_context(viewport={"width": 1280, "height": 1000}, service_workers="block")

            def route(request_route):
                url = request_route.request.url
                if urlsplit(url).scheme in ("data", "blob") or url.startswith(origin + "/"):
                    request_route.continue_()
                else:
                    report["blocked_requests"].append(url)
                    request_route.abort("blockedbyclient")

            context.route("**/*", route)
            context.on("request", lambda request: report["requests"].append(request.url))
            context.add_init_script(OBSERVER)
            page = context.new_page()
            page.set_default_timeout(30000)
            page.on("pageerror", lambda error: report["errors"].append(str(error)))
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(origin + "/", wait_until="networkidle")

            def state():
                return page.evaluate("window.__invoiceDetailProbe.states.at(-1)")

            def calls():
                return page.evaluate("window.__invoiceDetailProbe.calls")

            def action(selector, *, programmatic=False):
                count = page.evaluate("window.__invoiceDetailProbe.states.length")
                if programmatic:
                    page.locator(selector).evaluate("element => element.click()")
                else:
                    page.locator(selector).click()
                page.wait_for_function("count => window.__invoiceDetailProbe.states.length > count", arg=count, timeout=45000)
                page.wait_for_function("!document.querySelector('#analyze').disabled")
                return state()

            def load_fixture(name):
                text = (project / "fixtures" / name).read_text()
                options = page.locator("#fixture-select option").evaluate_all("elements => elements.map(element => element.value)")
                if name in options:
                    page.locator("#fixture-select").select_option(name)
                    page.locator("#load-fixture").click()
                else:
                    # The menu intentionally lists only some shipped examples;
                    # exercise the existing paste field for the remaining ones.
                    page.locator("#job-email").fill(text)
                page.wait_for_function("text => document.querySelector('#job-email').value === text", arg=text)
                return text

            def detail(invoice_id):
                return page.locator(".invoice-details[data-invoice-detail-id=" + json.dumps(invoice_id) + "]")

            def open_detail(invoice_id):
                element = detail(invoice_id)
                if not element.evaluate("element => element.open"):
                    element.locator("summary").focus()
                    page.keyboard.press("Enter")
                    page.wait_for_function("id => [...document.querySelectorAll('.invoice-details')].find(e => e.dataset.invoiceDetailId === id)?.open", arg=invoice_id)
                return element

            def screenshot(name):
                path = output / name
                page.screenshot(path=str(path), full_page=False)
                report["files"][name] = {"bytes": path.stat().st_size, "sha256": sha(path)}

            # Real self-hosted Pyodide startup, not a mocked browser result.
            count = page.evaluate("window.__invoiceDetailProbe.states.length")
            page.locator("#engine-start").click()
            page.wait_for_function("count => window.__invoiceDetailProbe.states.length > count && !document.querySelector('#analyze').disabled", arg=count, timeout=45000)
            assert state()["invoice_details"] == []
            assert state()["external_calls"] == 0
            assert page.locator(".invoice-details").count() == 0
            passed("actual local Python engine starts with an empty inspector and no external calls")

            load_fixture("01_simple_usd_hourly.txt")
            action("#analyze")
            drafted = action("#draft")
            invoice_id = drafted["ledger"][0]["invoice_id"]
            original = drafted["invoice_details"][0]["record"]
            assert drafted["mock_requests"] == 3 and original["status"] == "DRAFT"
            assert not detail(invoice_id).evaluate("element => element.open")
            assert page.locator("#approval-list .approval-preview").count() == 1
            before_calls, before_state = calls(), state()
            element = open_detail(invoice_id)
            text = element.inner_text()
            for item in original["items"]:
                assert item["name"] in text and item["unit_amount"]["value"] in text
            assert original["primary_recipients"][0]["billing_info"]["email_address"] in text
            assert calls() == before_calls and state() == before_state
            assert element.locator("button,a,input,form,img,iframe,script").count() == 0
            passed("keyboard opens original draft details without changing the queued approval, snapshot or request count")
            element.locator("summary").scroll_into_view_if_needed()
            screenshot("desktop-original-details.png")

            sent = action("#approval-list button[data-approve]")
            assert sent["pending"] == [] and sent["mock_requests"] == 4
            assert detail(invoice_id).evaluate("element => element.open")
            assert sent["invoice_details"][0]["record"]["items"] == original["items"]
            assert "SENT" in detail(invoice_id).inner_text()
            passed("details stay open and retain the original invoice when explicit approval removes its queued payload")

            load_fixture("02_gbp_proofreading.txt")
            analyzed = action("#analyze")
            assert analyzed["invoice_details"] == sent["invoice_details"]
            assert detail(invoice_id).evaluate("element => element.open")
            passed("analyzing another email does not replace the retained invoice record")

            page.locator("#payment-amount").fill("100.25")
            paid = action("#ledger-list button[data-pay]")
            record = paid["invoice_details"][0]["record"]
            assert record["payments"]["transactions"][0]["amount"]["value"] == "100.25"
            assert record["due_amount"]["value"] == "1219.75"
            assert "100.25" in detail(invoice_id).inner_text() and "PARTIALLY_PAID" in detail(invoice_id).inner_text()
            replayed = action("#replay-webhook")
            assert replayed["invoice_details"] == paid["invoice_details"]
            passed("real signed mock payment and duplicate replay update the correct retained payment facts")

            # Trigger the real button handler while the disclosure has focus, as
            # can happen when a reply arrives while its read-only content is used.
            page.locator("#demo-date").fill("2050-01-01")
            detail(invoice_id).locator("summary").focus()
            advanced = action("#advance-clock", programmatic=True)
            assert detail(invoice_id).evaluate("element => element.open")
            assert page.evaluate("document.activeElement?.closest('.invoice-details')?.dataset.invoiceDetailId") == invoice_id
            assert "2050-01-01" in detail(invoice_id).inner_text()
            assert advanced["invoice_details"] == paid["invoice_details"]
            passed("whole-ledger updates preserve disclosure state and keyboard focus while labeling the new sandbox clock")

            chased = action("#run-chase")
            assert any(pending["kind"] == "send_reminder" for pending in chased["pending"])
            assert page.locator("#approval-list .approval-reminder").count() == 1
            reminded = action("#approval-list button[data-approve]")
            assert reminded["ledger"][0]["reminders_sent"] == 1
            assert reminded["invoice_details"][0]["record"]["payments"] == paid["invoice_details"][0]["record"]["payments"]
            passed("the existing reminder preview and approval remain separate from read-only invoice inspection")
            detail(invoice_id).locator(".invoice-detail-amounts").scroll_into_view_if_needed()
            screenshot("desktop-recorded-payment.png")

            action("#reset-sandbox")
            assert page.locator(".invoice-details").count() == 0
            load_fixture("04_multi_currency.txt")
            action("#analyze")
            mixed = action("#draft")
            assert len(mixed["ledger"]) > 1
            assert invoice_id not in [entry["invoice_id"] for entry in mixed["ledger"]]
            for entry in mixed["ledger"]:
                element = open_detail(entry["invoice_id"])
                record = next(row["record"] for row in mixed["invoice_details"] if row["invoice_id"] == entry["invoice_id"])
                assert record["detail"]["currency_code"] == entry["currency"]
                for item in record["items"]:
                    assert item["name"] in element.inner_text()
                    assert item["unit_amount"]["currency_code"] + " " + item["unit_amount"]["value"] in element.inner_text()
            before_calls = calls()
            for entry in mixed["ledger"]:
                detail(entry["invoice_id"]).locator("summary").click()
            assert calls() == before_calls
            passed("reset clears old details and mixed-currency invoices retain separate exact identities and amount strings")

            action("#reset-sandbox")
            original_email = load_fixture("05_missing_email.txt")
            action("#analyze")
            page.locator("#review-editor > summary").click()
            hostile = 'Retained <img src=x onerror="window.detailExecuted=1"> & 日本語 😀'
            page.locator("#review-client-name").fill("日本語 <b>Client</b> 😀")
            page.locator("#review-client-email").fill("receiver@example.test")
            page.locator("#review-line-0-desc").fill(hostile)
            page.locator("#review-confirm").check()
            action("#review-check")
            literal = action("#draft")
            literal_id = literal["ledger"][0]["invoice_id"]
            element = open_detail(literal_id)
            assert hostile in element.inner_text()
            assert "日本語 <b>Client</b> 😀" in element.inner_text()
            assert element.locator("img,b,script,iframe,a,input,button,form").count() == 0
            assert page.evaluate("typeof window.detailExecuted") == "undefined"
            passed("actual corrected Python invoice renders Unicode and hostile-looking text literally without active markup")

            page.set_viewport_size({"width": 390, "height": 844})
            element.locator("summary").scroll_into_view_if_needed()
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
            if overflow:
                report["narrow_overflow"] = page.evaluate("""() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                  elements: [...document.querySelectorAll('body *')].map(element => ({tag: element.tagName, id: element.id,
                    class: element.className, width: element.getBoundingClientRect().width, right: element.getBoundingClientRect().right,
                    minWidth: getComputedStyle(element).minWidth})).filter(element => element.right > innerWidth + 1).slice(-40)})""")
                screenshot("phone-overflow-before.png")
                report["layout_probes"] = []
                for css in [".invoice-card:has(.invoice-details){min-width:0}", ".invoice-details{display:none}"]:
                    probe = page.add_style_tag(content=css)
                    report["layout_probes"].append({"css": css, "scrollWidth": page.evaluate("document.documentElement.scrollWidth")})
                    probe.evaluate("element => element.remove()")
            assert not overflow
            box = element.bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= 390
            screenshot("phone-literal-details.png")
            element.locator("summary").focus()
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement?.classList.contains('invoice-detail-table')")
            table = element.locator(".invoice-detail-table").first
            assert table.evaluate("element => element.scrollWidth > element.clientWidth")
            page.keyboard.press("ArrowRight")
            page.wait_for_function("document.activeElement.scrollLeft > 0")
            screenshot("phone-table-keyboard-scroll.png")
            passed("390px viewport contains long invoice text and keyboard users can focus and scroll the item table")

            page.set_viewport_size({"width": 1280, "height": 1000})
            snapshot_before_loss = state()
            before_calls = calls()
            page.evaluate("window.__invoiceDetailProbe.workers.at(-1).dispatchEvent(new ErrorEvent('error', {message: 'Receiver injected terminal worker loss'}))")
            page.wait_for_function("document.querySelector('#engine-status').textContent.includes('UNAVAILABLE')")
            assert "last displayed sandbox snapshot" in detail(literal_id).inner_text().lower()
            assert "inactive" in detail(literal_id).inner_text()
            accessibility = context.new_cdp_session(page).send("Accessibility.getFullAXTree")["nodes"]
            report["inactive_disclosures_ax"] = [node for node in accessibility if str(node.get("name", {}).get("value", "")).startswith("Invoice details")]
            readonly_controls = [node for node in accessibility if
                (node.get("role", {}).get("value") == "DisclosureTriangle" and
                 str(node.get("name", {}).get("value", "")).startswith("Invoice details")) or
                (node.get("role", {}).get("value") == "region" and
                 str(node.get("name", {}).get("value", "")).startswith(("Invoice items;", "Recorded sandbox payments;")))]
            report["inactive_readonly_controls_ax"] = readonly_controls
            assert readonly_controls and all(not any(prop.get("name") == "disabled" and
                prop.get("value", {}).get("value") is True for prop in node.get("properties", []))
                for node in readonly_controls), "Read-only invoice controls must stay enabled in the accessibility tree"
            assert calls() == before_calls and state() == snapshot_before_loss
            detail(literal_id).locator("summary").focus()
            page.keyboard.press("Enter")
            page.keyboard.press("Enter")
            assert calls() == before_calls
            assert page.locator("#draft").is_disabled() and page.locator("#reset-sandbox").is_disabled()
            passed("terminal worker loss labels retained details inactive while inspection remains read-only")

            prior_worker_count = page.evaluate("window.__invoiceDetailProbe.workers.length")
            page.locator("#engine-start").click()
            page.wait_for_function("count => window.__invoiceDetailProbe.workers.length > count && !document.querySelector('#analyze').disabled", arg=prior_worker_count, timeout=45000)
            assert state()["ledger"] == [] and state()["invoice_details"] == []
            assert page.locator(".invoice-details").count() == 0
            assert page.locator("#job-email").input_value() == original_email
            assert calls()[-1]["action"] == "init"
            assert len(calls()) == len(before_calls) + 1
            passed("explicit empty restart clears old invoice details, retains source text and replays no prior action")

            assert not report["blocked_requests"], report["blocked_requests"]
            assert all(url.startswith(origin + "/") for url in report["requests"])
            assert not report["errors"], report["errors"]
            assert all(sha(project / path) == value for path, value in report["source"].items())
            report["worker_calls"] = calls()
            report["last_state"] = state()
            report["state_count"] = page.evaluate("window.__invoiceDetailProbe.states.length")
            passed("all browser and worker requests stay on the loopback build, with no page error or source change")
            context.close()
            browser.close()
            browser = None
            report["status"] = "passed"
    except Exception:
        report["status"] = "failed"
        report["failure"] = traceback.format_exc()
        print(report["failure"], flush=True)
        raise
    finally:
        server.shutdown()
        server.server_close()
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "browser-receipt.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
