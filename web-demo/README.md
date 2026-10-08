# Ledgerly / Human-Gated Invoice Studio

A static browser demo that runs the repository's **actual Python modules** in a self-hosted Pyodide Web Worker. It is not a TypeScript rewrite or fixture-only output. Visitor-supplied job email flows through `RulesExtractor`, `Agent`, `RulePlanner`, `GatedClient` and the in-memory `SandboxMock`.

## Workflow

1. Load a fictional fixture or paste a non-sensitive job email; review extracted line items, confidence and validation issues.
2. If details are missing or wrong, open **Review or correct invoice fields**. Edit the recipient, name, payment terms, prior payment and line items. Confirm that you checked the original warnings, then check the fields with Python. The original extraction remains visible; reviewed values are identified as human input, without an extraction-confidence claim. Totals stay separate for each currency.
3. Create an in-memory draft from the checked values, or use the original valid extraction. Ledgerly probes and proves that an unapproved send is blocked. A checked revision is bound to its analyzed source and can be used once; changing fields or source text requires a fresh check. Checking values alone creates no invoice.
4. Explicitly approve or reject the queued send. Only the mock changes state; no PayPal call or real message is sent.
5. Simulate a partial payment and a signed mock webhook, replay the exact event to show idempotency, advance the local clock and draft an overdue reminder.
6. Approve or reject the reminder. The invoice ledger and event trace update across the whole session.

Review requires explicit quantities, positive prices, supported currencies, whole payment terms from 0 to 365 days and a nonnegative prior payment. Enter plain decimal numbers without commas or exponents. Python retains its zero-decimal currency and multi-currency deposit checks. A corrected recipient may be absent from the original email because the visitor supplied it explicitly; this is not a claim that the extractor found or verified that address. The bridge supplies the validated object through the core's existing `Extractor` protocol. It does not change `Agent`, `RulePlanner`, `GatedClient` or their approval permits.

No model, HTTP PayPal client, provider key, backend, analytics or localStorage is used. Pyodide and the staged Python modules load from this repo's Pages site. Email text and ledger state stay in tab memory and disappear on reset/close. The sandbox's HMAC is a test signature, not PayPal's production certificate verification; invoice actions are clearly labelled simulations. The confidence score is a heuristic, not a calibrated probability. Do not paste confidential client material.

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

`npm test` runs the original Python workflow under Pyodide and covers extraction, the gate, payment/webhook verification, duplicate replay and overdue reminder approval. It also checks missing-recipient correction, invalid fields, one-use revisions, source invalidation and multi-currency reviewed drafts. `npm run build` stages the unmodified Python core, the browser-only review adapter, fictional fixtures and self-hosted runtime assets into ignored `public/` directories. `tools/capture_ledgerly.py` performs a browser walkthrough and saves phone/desktop captures (requires Playwright and Chrome).

To check the correction UI against a locally served production build, install Playwright in your test environment and run:

```bash
python tools/check_review_browser.py http://127.0.0.1:8873/ \
  --chrome /path/to/chrome --output /path/to/test-evidence
```

The browser check refuses non-loopback origins, blocks off-origin requests and uses only the repository's fictional fixtures. It exercises desktop and phone layouts, keyboard confirmation, invalid edits, literal text, line addition/removal, source invalidation, one-use drafting and the separate sandbox approval. It writes its receipt and screenshots to the requested output directory.

Pyodide 0.29.3 is MPL-2.0. Its unmodified assets and upstream license are linked from the page footer and `THIRD_PARTY_NOTICES.md`.
