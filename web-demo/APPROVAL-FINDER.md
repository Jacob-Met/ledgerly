# Find a pending approval

The local browser demo's human gate can show just the pending invoice or reminder you want to inspect. Load the Python engine and create the sandbox drafts first.

1. In **Find in queued proposals**, type part of a recipient, invoice ID, line item, subject or message. Exact queued action IDs also work.
2. Choose **All pending**, **Invoice sends** or **Reminders**. Text and action type must both match.
3. Read the matching card's original recipient, amounts, terms and message. Use its existing **Approve in sandbox** or **Reject** button only when you choose that action.
4. **Clear filters** restores the entire pending list in its original order.

The count is matching cards out of all pending cards. A no-match result does not mean the queue is empty. Hidden actions remain queued; filtering does not approve, reject, delete or reorder them. Rejection notes stay attached to the same original action.

Search is a case-insensitive literal substring over the existing proposal text plus its queued action and invoice IDs. Leading and trailing query whitespace is ignored; internal whitespace, accents, punctuation, decimal strings and currency text are not rewritten. This is not a regular expression, an amount comparison or a search over completed actions. Collapsed invoice details still contribute their retained text. Your optional rejection note is not proposal text and is not searched.

The query and type remain when Python returns an updated queue. While Python is working, these controls are disabled. If that Python session is lost, the last displayed cards are labeled inactive and the filters remain. An unsuccessful reset or restart keeps them. A successful explicit Reset, or a successful Restart that returns an empty sandbox, clears the filters.

If displayed cards cannot be matched in order to the accepted queued IDs and their original approve/reject buttons, the finder refuses to hide cards. It shows all current cards with an explanatory message. A later valid queue can restore filtering without discarding your query.

These controls are in memory in this tab. They add no network, storage, download or provider action. The existing demo still uses local Python and its in-memory PayPal-style mock; the finder does not connect it to a live service.

## Focused native checks

From `web-demo`, with the repository's admitted dependencies:

```sh
node node_modules/vitest/vitest.mjs run tests/approval-filter.test.ts tests/engine-recovery.test.ts tests/approval-preview.test.ts
npm run build
```

The actual browser receiver uses Playwright with an explicitly supplied local Chromium executable and a strictly new output directory. It drives the built app and real staged Pyodide engine. It also holds one real send and injects terminal transport errors before a reset and restart to check those boundaries; it does not substitute an Agent or fabricated success reply.

```sh
python3 tests/approval-filter-browser.py --browser "/path/to/chrome" --output "/new/private/receiver-output"
```

The receiver uses only authored fictional inputs and blocks off-origin requests. Its disposable browser profile is separate from its retained receipts and captures. Passing native checks is not a claim of Pages deployment or live-provider qualification.
