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

## Give a reason when rejecting a queued action

Each pending send or reminder has **Reason for rejecting (optional)**. You can
write up to 500 characters, including line breaks and Unicode, then choose
**Reject**. Typing alone changes no invoice or approval. The selected action's
reason is retained verbatim in the existing agent result and audit; the status
message confirms it as literal text. An empty or whitespace-only field keeps the
existing “Rejected by the browser visitor” reason.

Notes stay with their action IDs across ordinary queue updates and a failed
request. They clear when that action leaves the queue or the sandbox resets or
restarts. A busy or unavailable engine disables editing and action buttons.
Approving still uses the existing independent approval path; an unfinished
rejection note does not prevent approval and is not sent with it. Notes remain
only in the tab's sandbox and disappear on reset or close.

## Download the displayed sandbox ledger

Use **Download sandbox ledger CSV** while the local engine is ready and the ledger contains invoices. Save this local snapshot before closing or resetting the tab. Each row is explicitly marked `SANDBOX` and includes the snapshot date, invoice identity, recipient, currency, original total/paid/balance strings, status, sent/due dates and reminder count. Currencies are never combined and JavaScript does not calculate money. Downloading calls no worker or provider and approves no action.

The file uses UTF-8 with BOM, CRLF record endings, a header and quoted CSV fields. Formula-like text gets a leading apostrophe; this is an explicit text-export convention, not a guarantee about every spreadsheet application's later save/reopen behavior. Import identifier and amount columns as text when preserving their exact formatting matters. The [CSV format](https://www.rfc-editor.org/rfc/rfc4180) and [spreadsheet text handling](https://owasp.org/www-community/attacks/CSV_Injection) references explain the underlying conventions. This is a snapshot for inspection, not a session reload or accounting import format.

An empty/reset sandbox or an unavailable engine has no current download. If the browser cannot start a download, the displayed snapshot remains available for an explicit retry. Reset clears the working ledger; it does not remove CSV files already saved by the visitor.

## Review outstanding balances by client

The **See what each client owes** board groups positive open balances by the
exact billing email recorded in the sandbox ledger. Select a client and a due
state to see that selection's invoices and separate currency totals. **Clear
balance filters** restores the complete board. The original invoice ledger,
approval cards and payment controls remain available independently.

An invoice counts when its native status is `SENT`, `UNPAID`, `PARTIALLY_PAID`
or `PAYMENT_PENDING` and its balance is positive. Drafts, paid or cancelled
invoices and other statuses are counted explicitly outside the board; open
invoices with a zero balance are also excluded. A partial payment therefore
contributes only the remaining balance. Every displayed invoice retains its
original status and balance text.

Due states compare the recorded due date with the sandbox clock shown in the
snapshot label. A missing due date is **No due date**, never assumed overdue.
Advancing the local clock, approving an invoice or simulating a payment updates
the board through the same accepted snapshot as the ledger. Billing emails that
differ by case or whitespace stay separate; shared or changed display names do
not merge client identities.

Totals add decimal strings exactly, without binary floating-point money
arithmetic, currency conversion or currency-based rounding. Their fractional
scale comes from the included balance strings, so `0.1` plus `0.2` displays
`0.3`, while `100.50` plus `0.3` displays `100.80`. Each invoice still shows its
original string. This is an overview of this tab's in-memory sandbox, rather
than a refreshed provider statement or accounting balance.

While an action runs, the board hides its prior balances and disables its own
controls. Losing the Python session clears the accepted board; restarting or
resetting opens an empty one. A malformed date, duplicate invoice identity,
negative/nonfinite balance or incomplete row holds the complete board with an
explicit explanation. A balance string over 1,100 characters, with over 1,000
coefficient digits or an exponent outside ±1,000 is also refused for display.
The view cannot send, pay, refresh, export or modify an invoice.

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

## Save a standalone sandbox invoice record

Use **Save sandbox invoice record** on a ledger card to download that invoice's
currently displayed summary and retained detail record as a standalone HTML file.
The action is available only when Python is ready, no action is running, and
exactly one ledger row and one retained record share the selected invoice
reference. Existing read-only disclosures remain usable while the engine is
busy or inactive; they do not enable a download of an unavailable selection.

The saved document includes the original recipient, sender, invoice identifiers,
line items, terms, note and individual recorded payments shown in the inspector.
It preserves the agent's ledger summary separately from the sandbox provider
record, including their original decimal strings and currencies. It does not
recalculate totals, refresh an invoice, include another invoice, or add the
pasted email, current analysis or pending proposals to the file. Text from an
invoice remains literal, including Unicode, markup characters and line breaks.

The HTML states the source snapshot's sandbox clock and the file's creation time
in UTC. It is a fixed copy: later approvals, payments, resets and restarts do not
change a downloaded file. Open it directly without a server, Python engine or
network connection, and use **Print this record** (or the browser's print
command) for the included print layout. This is a sandbox demonstration record,
not a payable invoice, payment receipt, current provider statement or sandbox
backup. It cannot authorize an action or restore tab state. Keep any saved file
according to the information it contains; resetting the tab does not delete
files already downloaded.

The filename is based on the invoice reference, with unsafe filename characters
replaced. Repeated downloads of the same invoice may be renamed or prompt for a
destination according to browser settings. A serialized record over 4 MiB is
refused. A download-start failure leaves the accepted displayed snapshot intact
so the action can be retried explicitly.

### Receive the actual download and offline document

The separate **Invoice record browser receiving** workflow uses Node 22 and the
GitHub runner's installed Chrome with the existing production build. It adds no
browser library or product dependency and leaves the maintained CI unchanged.
With those runtimes already available, run from the repository root:

```bash
node web-demo/tools/check_invoice_record_browser.mjs \
  --project . --build web-demo/dist --browser /path/to/chrome \
  --output /path/to/new-invoice-record-evidence
```

The gate drives the actual Python/Pyodide fixture, approval and payment flow,
downloads real HTML files, reopens them through file URLs, and compares all
displayed invoice fields, original amounts and individual payment entries. It
also checks literal corrected text, desktop and narrow layouts, actual print PDF
generation, later-state isolation, download-allocation refusal, busy/inactive
availability and an explicit empty restart. Node tests add missing/duplicate
identity and oversized-document controls. Generated PNG/PDF artifacts are
preserved with hashes; artifact generation alone is not a claim of direct pixel
or PDF-text inspection.
