# Continue an unfinished invoice intake

Use **Save intake** below the invoice intake to download the source email and any current correction fields. You can save while values are incomplete: an empty quantity, an unfinished recipient or a price Python will later reject stays as typed. Saving runs no Python check and creates no invoice.

The browser prepares a file named like `ledgerly-intake-20261008T160000000Z.json`. Keep the downloaded file to continue in another visit. Ledgerly does not automatically save or recover a closed page.

## Reopen and review

1. Choose **Open intake** and select a saved file.
2. Review its filename, saved time, recipient, line count and source preview. The preview shows the first 2,000 characters; replacement loads the complete source and all saved fields.
3. Save the current intake first if you also need those edits. **Keep current intake** or Escape leaves the current intake unchanged.
4. Load the local Python engine if necessary, then choose **Replace current intake**. Python analyzes the saved source before the editor restores its saved fields.

Opening is only a preview. Explicit replacement changes the current source and corrections. Current sandbox invoices, pending approvals and the clock remain separate.

### Files with correction fields

Saved correction fields reopen unchecked. The original warnings from the new source analysis remain above the form, including warnings resolved by a supplied correction such as a missing recipient.

Read the warnings, confirm the fields, and choose **Check corrected fields with Python**. Only a new valid review creates a one-use revision for **Create reviewed sandbox draft**. The file restores no earlier review identifier or confirmation.

That draft's send still appears in the existing human approval gate. Reopening, checking or downloading an intake never approves it.

### Source-only files

If no correction form exists when you save, the file records only source text. Replacing from that file runs a new Python extraction and keeps the ordinary source-analysis behavior:

- Invalid or low-confidence extraction remains blocked.
- Valid new extraction enables the existing explicit **Create sandbox draft** action.
- The draft's send still needs separate approval.

A source-only file invents no human review and restores no earlier extraction result. Editing the correction form follows the usual human review path.

## Interrupted work

If incoming source analysis fails, the previous source and correction fields stay in the editor. Their prior review is retired; confirm and check them again before drafting.

If the Python Worker stops, **Save intake** remains available for retained input when no action is busy. The existing **Restart empty sandbox** action starts a new in-memory ledger and preserves the editor's input. A later explicit correction check reanalyzes the retained source in the new session. Intake files never replay interrupted actions.

## Format and limits

Version 1 is UTF-8 JSON with exactly these outer keys:

```json
{
  "format": "ledgerly-intake",
  "version": 1,
  "saved_at": "2026-10-08T16:00:00.000Z",
  "source_text": "Fictional job email...",
  "review_fields": null
}
```

When present, `review_fields` has exactly `client_name`, `client_email`, `due_days`, `amount_paid` and `line_items`. The first four values are raw strings. Each line contains raw string values for `desc`, `qty`, `unit_price`, `currency` and `unit`.

The saved time is an exact UTC timestamp describing file preparation; it establishes no invoice validity. Files are limited to 2 MiB and 200 editable lines. Missing/extra fields, unsupported versions, malformed JSON, invalid UTF-8 and numeric values in raw-string fields are refused. Imported strings the existing editor would silently alter are also refused, including carriage-return source text and line values that cannot survive the existing escaped renderer.

Invoice, approval, payment, clock, sandbox ledger, confidence, checked revision and confirmation state are excluded. Existing invoice-record and ledger downloads remain separate features.

## Development receiving

From `web-demo`, run the normal project commands and use an installed Chrome:

```sh
npm ci
npm test
npm run build
node tools/check_intake_file_browser.mjs --browser /path/to/chrome --output /path/to/new/receiving-directory --emit-bundle
```

The receiver uses Node's built-in Chrome DevTools transport. It builds the frozen original application privately using the same locked dependencies, then exercises both original and current applications through the real Python Worker. The output directory must be new.

See the [source and receiving record](../../docs/receipts/intake-files-e3a41d2b3368-20261008/README.md) for exact boundaries, source pins, reports and historical failures.
