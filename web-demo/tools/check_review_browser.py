"""Exercise the built offline review flow with synthetic fixtures in real Chrome.

Requires Playwright and an installed Chrome/Chromium. Serve `dist/` on loopback;
this check refuses remote origins and blocks every off-origin browser request.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def run(base_url, chrome, output):
    origin = urlparse(base_url)
    if origin.scheme != "http" or origin.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use the built application served on a loopback HTTP origin.")
    output.mkdir(parents=True, exist_ok=True)
    unexpected = []
    errors = []
    receipts = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=chrome)
        try:
            for label, viewport in [("desktop", {"width": 1440, "height": 1000}), ("phone", {"width": 390, "height": 844})]:
                context = browser.new_context(viewport=viewport)

                def route(request_route):
                    url = urlparse(request_route.request.url)
                    if (url.scheme, url.netloc) != (origin.scheme, origin.netloc):
                        unexpected.append(request_route.request.url)
                        request_route.abort()
                    else:
                        request_route.continue_()

                context.route("**/*", route)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base_url)
                page.locator("#engine-start").click()
                expect(page.locator("#engine-status")).to_have_text("PYTHON READY / OFFLINE", timeout=60000)
                page.locator("#fixture-select").select_option("05_missing_email.txt")
                page.locator("#load-fixture").click()
                expect(page.locator("#analyze")).to_be_enabled()
                page.locator("#analyze").click()
                expect(page.locator("#analysis .client-row")).to_contain_text("Recipient email not found")
                expect(page.locator("#draft")).to_be_disabled()
                original = page.locator("#analysis .client-row").inner_text()
                page.locator("#review-editor summary").click()
                email = page.get_by_label("Recipient email", exact=True)
                email.fill("billing@example.test")
                quantity = page.locator("#review-line-0-qty")
                initial_quantity = quantity.input_value()
                quantity.fill("0")
                page.locator("#review-confirm").check()
                page.locator("#review-check").click()
                expect(page.locator("#review-result")).to_contain_text("These fields still need attention")
                expect(page.locator("#draft")).to_be_disabled()
                quantity.fill(initial_quantity)
                name = 'Fictional <review> & "client"'
                page.get_by_label("Client name", exact=True).fill(name)
                page.locator("#review-confirm").focus()
                page.keyboard.press("Space")
                expect(page.locator("#review-confirm")).to_be_checked()
                page.locator("#review-check").click()
                expect(page.locator("#review-result")).to_contain_text("Checked human input — ready to draft")
                expect(page.locator("#review-result")).to_contain_text(name)
                expect(page.locator("#draft")).to_be_enabled()
                assert page.locator("#analysis .client-row").inner_text() == original
                expect(page.locator("#analysis > .issue-list")).to_contain_text("No client email found")
                expect(page.locator("#approval-list .approval-card")).to_have_count(0)
                expect(page.locator("#mock-requests")).to_have_text("0")
                # Editing an already checked field must remove permission to draft it.
                page.get_by_label("Payment due in days", exact=True).fill("0")
                expect(page.locator("#draft")).to_be_disabled()
                expect(page.locator("#review-confirm")).not_to_be_checked()
                # Adding/removing a line retains every other edit and remains operable.
                page.locator("#review-add-line").click()
                expect(page.locator("[data-review-line]")).to_have_count(3)
                expect(email).to_have_value("billing@example.test")
                expect(page.get_by_label("Client name", exact=True)).to_have_value(name)
                page.get_by_role("button", name="Remove line 3", exact=True).click()
                expect(page.locator("[data-review-line]")).to_have_count(2)
                page.locator("#review-confirm").check()
                page.locator("#review-check").click()
                expect(page.locator("#review-result")).to_contain_text("Due on receipt")
                expect(page.locator("#draft")).to_be_enabled()
                overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                assert not overflow, f"Horizontal overflow at {label} width"
                page.locator("#analysis").screenshot(path=str(output / f"{label}-review.png"))
                page.locator("#draft").click()
                expect(page.locator("#approval-list .approval-card")).to_have_count(1)
                expect(page.locator("#ledger-list .status-chip")).to_have_text("DRAFT")
                expect(page.locator("#approval-list")).to_contain_text("billing@example.test")
                expect(page.locator("#draft")).to_be_disabled()
                page.locator("#draft").evaluate("button => button.click()")
                expect(page.locator("#ledger-list .invoice-card")).to_have_count(1)
                page.get_by_role("button", name="Approve in sandbox", exact=True).click()
                expect(page.locator("#ledger-list .status-chip")).to_have_text("SENT")
                today = page.locator("#demo-date").input_value()
                expect(page.locator("#ledger-list .invoice-card")).to_have_attribute("data-due", today)
                source = page.locator("#job-email").input_value()
                page.locator("#job-email").fill(source + "\nChanged for a new review.")
                expect(page.locator("#review-form")).to_have_count(0)
                expect(page.locator("#draft")).to_be_disabled()
                expect(page.locator("#ledger-list .invoice-card")).to_have_count(1)
                expect(page.locator("#external-calls")).to_have_text("0")
                # Preserve the original one-draft-per-analysis button behavior too.
                page.locator("#fixture-select").select_option("01_simple_usd_hourly.txt")
                page.locator("#load-fixture").click()
                expect(page.locator("#analyze")).to_be_enabled()
                page.locator("#analyze").click()
                expect(page.locator("#draft")).to_be_enabled()
                page.locator("#draft").click()
                expect(page.locator("#ledger-list .invoice-card")).to_have_count(2)
                expect(page.locator("#draft")).to_be_disabled()
                page.locator("#draft").evaluate("button => button.click()")
                expect(page.locator("#ledger-list .invoice-card")).to_have_count(2)
                receipts.append({"viewport": label, "recipient_corrected": True, "invalid_quantity_blocked": True,
                                 "original_preserved": True, "edits_invalidate_review": True, "separate_approval": True,
                                 "reviewed_drafts": 1, "ordinary_drafts": 1, "repeat_draft_disabled": True,
                                 "external_calls": 0, "horizontal_overflow": overflow})
                context.close()
        finally:
            browser.close()
    assert not unexpected, f"Off-origin requests were attempted: {unexpected}"
    assert not errors, f"Browser errors: {errors}"
    result = {"ok": True, "receipts": receipts, "off_origin_requests": unexpected, "page_errors": errors}
    (output / "browser-review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.url, args.chrome, args.output)
