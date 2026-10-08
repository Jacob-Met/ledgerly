# Ledgerly / Human-Gated Invoice Studio

A static browser demo that runs the repository's **actual Python modules** in a self-hosted Pyodide Web Worker. It is not a TypeScript rewrite or fixture-only output. Visitor-supplied job email flows through `RulesExtractor`, `Agent`, `RulePlanner`, `GatedClient` and the in-memory `SandboxMock`.

## Workflow

1. Load a fictional fixture or paste a non-sensitive job email; review extracted line items, confidence and validation issues.
2. If details are missing or wrong, open **Review or correct invoice fields**. Edit the recipient, name, payment terms, prior payment and line items. Confirm that you checked the original warnings, then check the fields with Python. The original extraction remains visible; reviewed values are identified as human input, without an extraction-confidence claim. Totals stay separate for each currency.
3. Create an in-memory draft from the checked values, or use the original valid extraction. Ledgerly probes and proves that an unapproved send is blocked. A checked revision is bound to its analyzed source and can be used once; changing fields or source text requires a fresh check. Checking values alone creates no invoice.
4. Review the queued invoice in its approval card: recipient, line items, exact unit prices, payment terms, note and reported prior payment. Then explicitly approve or reject its send. Only the mock changes state; no PayPal call or real message is sent.
5. Simulate a partial payment and a signed mock webhook, replay the exact event to show idempotency, advance the local clock and draft an overdue reminder.
6. Read the queued reminder's subject and complete message, then approve or reject it. The preview comes from that pending action, even if you have analyzed another email since drafting it. Opening an invoice preview or selecting message text creates no request or approval. The invoice ledger and event trace update across the whole session.
7. Open **Invoice details · sandbox record** on a ledger card to inspect the retained invoice after approval or rejection, and after later payments. It shows the original recipient, line items, unit prices, terms, note and recorded sandbox payments. The detail record comes from the existing Python mock, separately from the agent's ledger summary. Amounts keep the provider's original decimal text and currencies; the view does not recalculate totals or fetch an invoice. Missing information is labeled as not recorded.

Invoice details remain open across ordinary ledger updates. The snapshot label identifies the sandbox clock, and an in-progress action or unavailable Python session is explicitly marked. Inactive details are the last displayed copy; restarting or resetting the sandbox clears them. Keyboard users can open a disclosure with Enter or Space and focus its table region to scroll wide rows. This is a read-only sandbox inspector, not a payable invoice, provider connection, download or accounting record.

Review requires explicit quantities, positive prices, supported currencies, whole payment terms from 0 to 365 days and a nonnegative prior payment. Enter plain decimal numbers without commas or exponents. Python retains its zero-decimal currency and multi-currency deposit checks. A corrected recipient may be absent from the original email because the visitor supplied it explicitly; this is not a claim that the extractor found or verified that address. The bridge supplies the validated object through the core's existing `Extractor` protocol. It does not change `Agent`, `RulePlanner`, `GatedClient` or their approval permits.

No model, HTTP PayPal client, provider key, backend, analytics or localStorage is used. Pyodide and the staged Python modules load from this repo's Pages site. Email text and the working ledger stay in tab memory and disappear on reset/close. An explicitly downloaded CSV is a separate local file. The sandbox's HMAC is a test signature, not PayPal's production certificate verification; invoice actions are clearly labelled simulations. The confidence score is a heuristic, not a calibrated probability. Do not paste confidential client material.

## Download the displayed sandbox ledger

Use **Download sandbox ledger CSV** while the local engine is ready and the ledger contains invoices. Save this local snapshot before closing or resetting the tab. Each row is explicitly marked `SANDBOX` and includes the snapshot date, invoice identity, recipient, currency, original total/paid/balance strings, status, sent/due dates and reminder count. Currencies are never combined and JavaScript does not calculate money. Downloading calls no worker or provider and approves no action.

The file uses UTF-8 with BOM, CRLF record endings, a header and quoted CSV fields. Formula-like text gets a leading apostrophe; this is an explicit text-export convention, not a guarantee about every spreadsheet application's later save/reopen behavior. Import identifier and amount columns as text when preserving their exact formatting matters. The [CSV format](https://www.rfc-editor.org/rfc/rfc4180) and [spreadsheet text handling](https://owasp.org/www-community/attacks/CSV_Injection) references explain the underlying conventions. This is a snapshot for inspection, not a session reload or accounting import format.

An empty/reset sandbox or an unavailable engine has no current download. If the browser cannot start a download, the displayed snapshot remains available for an explicit retry. Reset clears the working ledger; it does not remove CSV files already saved by the visitor.

## Verify and run

```bash
python -m pytest -q
cd web-demo
npm ci
npm audit --audit-level=moderate
npm test
npm run build
npm run dev
```

`npm test` runs the original Python workflow under Pyodide and covers extraction, the gate, payment/webhook verification, duplicate replay and overdue reminder approval. It also checks missing-recipient correction, invalid fields, one-use revisions, source invalidation, multi-currency reviewed drafts and detached retained invoice details. `npm run build` stages the unmodified Python core, the browser-only review and invoice-detail adapters, fictional fixtures and self-hosted runtime assets into ignored `public/` directories. `tools/capture_ledgerly.py` performs a browser walkthrough and saves phone/desktop captures (requires Playwright and Chrome).

To check the correction UI against a locally served production build, install Playwright in your test environment and run:

```bash
python tools/check_review_browser.py http://127.0.0.1:8873/ \
  --chrome /path/to/chrome --output /path/to/test-evidence
```

The browser check refuses non-loopback origins, blocks off-origin requests and uses only the repository's fictional fixtures. It exercises desktop and phone layouts, keyboard confirmation, invalid edits, literal text, line addition/removal, source invalidation, one-use drafting and the separate sandbox approval. It writes its receipt and screenshots to the requested output directory.

To check actual CSV files against the Python state in the built page, use a new or empty evidence directory:

```bash
python -m pip install -r tools/requirements-browser.txt
python tools/check_ledger_export_browser.py dist /path/to/ledger-evidence \
  --chrome /path/to/chrome
```

This receiver starts its own loopback server and checks complete CSV bytes, mixed currencies, approvals/payment/reminders, retry, reset and unavailable sessions, plus Enter activation at a narrow viewport. The existing browser-engine CI job runs it with the runner's installed Chrome. CI adds --emit-bundle to retain a bounded, checksummed packet of the synthetic CSV, JSON and screenshots in its job log; an oversized packet fails explicitly. No browser binary is downloaded by this check.

Pyodide 0.29.3 is MPL-2.0. Its unmodified assets and upstream license are linked from the page footer and `THIRD_PARTY_NOTICES.md`.

To receive the invoice inspector against an actual production build, with Playwright and Chrome available:

```bash
python tools/check_invoice_details_browser.py --project .. --build dist \
  --chrome /path/to/chrome --output /path/to/new-test-evidence
```

This driver owns a temporary loopback server, refuses off-origin requests, and uses fictional fixtures and synthetic corrected text. It records real Python Worker replies and checks draft/approval/payment/reminder identity, read-only disclosures, literal text, keyboard focus, narrow-table scrolling, reset and explicit recovery from an injected worker failure. Screenshots, source hashes and a receiving receipt go into a new output directory; the script does not change source or connect to a provider.
