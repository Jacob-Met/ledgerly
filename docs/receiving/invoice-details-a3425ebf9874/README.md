# Retained sandbox invoice details

## Delivered behavior

The ledger now lets a visitor open **Invoice details · sandbox record** after an invoice has been explicitly approved or rejected and after later payments or unrelated analysis. The view shows the retained recipient, sender, items, original unit prices, payment terms, note, provider status, provider totals and recorded sandbox payments. It reads the existing in-memory Python mock; opening a disclosure does not request an invoice, approve an action, calculate a new total or write storage.

The displayed record must match exactly one requested ledger identity. Missing or ambiguous records do not fall back to another invoice or a pending action. The Python projection deep-copies an explicit field list and omits private mock bookkeeping. Imported strings are escaped, including identifiers and monetary text. Provider amounts remain separate from the Agent ledger summary and from other currencies. Missing values are labeled rather than changed to zero.

Open disclosures and keyboard focus survive ordinary snapshot replacement. An action in progress and an unavailable Python session have explicit last-snapshot labels. Read-only disclosures and their scrollable table regions remain usable after worker loss, while the existing action controls remain disabled. Reset and explicit empty restart clear the retained view.

This is a browser sandbox feature. It is not a payable invoice, accounting record, provider connection, session-restoration feature or deployment claim. All execution below used shipped fictional fixtures and authored synthetic text.

## Exact source and receiving boundary

The native checkout uses real upstream Git objects and normal ancestry. It is retained at `/srv/hamon-estate/receivers/estate-a3425ebf9874-ledgerly-invoice-details/source` on branch `work/invoice-details-a3425ebf9874`.

| Boundary | Commit or tree |
|---|---|
| Initial gap reproduced | `350868091702d60f3dc340be4a017ba49d99f8a0` |
| First implementation parent, including queued previews | `f044ee3c5f77ab062d51684d8718f888e48540b2` |
| Current webhook owner received | `5493205cd69a32be75ed2f7dfc669b122efe5563` |
| Final upstream parent, including complete overdue scans | `2d3a90a9aa794d849ec54ca9d32a720959ddc5db` |
| Final qualified native source | `47f9f427f66ff69b7ba356359905965d96d0111f` |
| Final qualified native source tree | `46a03be471b4fd3199735c4a9cc341da878bc82e` |

`source-manifest.json` pins the complete changed-file set, the unchanged upstream leaves and exact source bytes. The independent review's original source pins remain historical; its corrected renderer pin maps to the final source without rewriting its original receipt. A public GitHub API commit may have a different commit identity; any such mapping must establish tree and blob parity separately.

The product scope is the new projection, disclosure renderer/CSS, tests and browser receiver. Shared changes are additive snapshot/mount/availability hooks and admission of the new Python filename in the Worker, asset staging and isolated Pyodide fixtures. The existing recovery test's import-stripping VM receives the actual new controller; its recovery assertions remain unchanged.

The current `Demo.dispatch` overdue budget from #25 / PR30 is preserved exactly. Its newly merged isolated Pyodide test needs `invoice_details.py` in its module-copy list because it imports the composed bridge; no owner assertion changed. The webhook owner from #21, preview owner from #22 / PR26, active CSV scope #23 / PR27 and the separate completed-review scope #31 retain their boundaries. No Agent, provider, extraction, monetary-admission or approval rule is authored by this change.

## Actual qualification

| Evidence | Exact result and scope |
|---|---|
| Original native missing-capability control | One intended failure on the untouched f044 bridge: no `invoice_details` snapshot key; seven unrelated new cases deselected |
| Full native Python on received 5493 composition | 187 passed and 60 subtests passed |
| Full TypeScript/Pyodide before the final interaction correction | 45 passed |
| Renderer/recovery after the interaction correction | 13 passed; existing recovery assertions unchanged |
| Final overdue/main composition | 14 native cases and 3 subtests passed: eight inspector cases plus the owner's six overdue controls |
| Final actual Pyodide composition | Five Vitest cases passed, including execution of all six native overdue controls inside Pyodide/Python 3.13.2 |
| Final production build | Strict TypeScript and Vite passed with the unchanged dependency lock |
| Final actual browser | 13 groups passed on Chromium 153.0.8010.47, actual Worker/Python, loopback-only requests, no page errors or source changes |
| Independent disclosure receiving | Original unchanged driver: one pass/two failures; corrected renderer: three passes/zero failures |

Counts identify the source and boundary actually executed; they are not summed into an invented full-suite result on a later commit. Hosted CI and integration readback are later gates.

The browser receipt at `qualification/browser-overdue-composed/browser-receipt.json` has SHA-256 `ff65bf24150d43aea89a05b8a0d1d9e11a60ef91c60b94d585050c16f9cf11a2`. Its source map includes the current overdue bridge, actual current Agent, exact renderer and existing recovery/preview modules. Its four captures show original details, actual recorded payment, literal hostile-looking/Unicode text at 390 pixels and keyboard table scrolling. Desktop and phone captures were visually inspected; the unchanged frontend's earlier four captures were also inspected.

The receiver records real Worker requests/replies through a transparent observer; it does not substitute the Python engine or fake result messages. It exercises drafting, approval, another email, actual partial payment and exact duplicate replay, date advancement, reminder review/approval, mixed identities/currencies, reset, injected terminal worker failure and explicit empty restart. The accessibility-tree gate checks that read-only invoice controls are enabled after session loss while existing action controls remain disabled.

## Preserved findings and corrections

The initial production TypeScript build rejected iteration over `NodeList` with the repository's existing DOM libraries. The renderer uses `Array.from` and the corrected build passes; the original log is retained.

The actual mobile browser exposed a 435-pixel page at a 390-pixel viewport. The new item table imposed its minimum content width on the invoice card. A measured CSS probe established that allowing that card to shrink restored a 390-pixel page while preserving horizontal table scrolling. The final source adds a class only to cards containing this inspector and applies `min-width: 0`. The original overflow receipt and screenshot remain intact.

The independent reviewer found a real native disclosure scheduling race. A click changes `details.open` immediately but queues its `toggle` event. An arriving snapshot could therefore close a just-opened panel or reopen a just-closed panel. The final controller reads the attached DOM's current open properties before replacing it. The independent production-renderer driver and both original failures are preserved byte-for-byte; the same driver passes both corrected directions and a removal/reintroduction control.

The inherited disabled ledger region also marked the usable read-only disclosure disabled in Chromium's accessibility tree. An isolated native probe established that `aria-disabled="false"` on this action-free disclosure corrects both its summary and table regions without enabling neighboring actions. The strengthened actual-app driver first failed on the old renderer after ten passing groups, then passed all thirteen on the correction and final current-main composition.

Runner failures are distinguished from product defects. Initial browser startup encountered a missing system Playwright driver and Snap's refusal of a profile under `/dev/shm`; later harness attempts selected a fixture absent from the dropdown and tried to fill a closed existing editor. Their logs, receipts and exact earlier driver bytes remain retained. The final driver uses the existing paste route for such fixtures and explicitly opens the editor. A mistyped `npm run stage:python` command was refused; the next runner used the repository's actual `node scripts/stage-python.mjs`, with no source or assertion change. No failed run is relabeled as accepted execution.

## Runtime and custody

Native Python was 3.14.4; Node was 22.22.1. The unchanged npm lock supplied TypeScript 5.9.3, Vite 8.3.3, Vitest 5.0.3 and Pyodide 0.29.3. Dependencies and build outputs were isolated in `/dev/shm/hamon-a3425ebf9874-ledgerly-invoice-details`; they were not installed into another owner's project or the deployed application.

The system Python Playwright package lacked its JavaScript driver. The receiver used an unmodified Playwright 1.55.0 wheel downloaded from official PyPI and verified by its published SHA-256; `qualification/browser-runtime-custody.json` records exact custody. It was extracted only into the receiver's own temporary runtime. Chromium used a new temporary profile under the receiver's own Snap-compatible directory. No normal browser profile, account, provider key or real invoice was accessed.

The source evidence preserves all text logs, receipts and historical driver versions, the independent packet, the decisive overflow capture and the final four captures. Additional intermediate screenshots remain immutable in the native receiver; `evidence-manifest.json` identifies their original paths and hashes without duplicating every image in Git. The exact source/evidence Git bundle and publication mapping are retained separately in the same receiver.

## Replay

Use the repository's pinned dependencies and a new receiving checkout. Run the Python suite and the ordinary web commands documented in `web-demo/README.md`. The focused final composition controls are:

```sh
python -m pytest -q tests/test_browser_invoice_details.py tests/test_browser_overdue_scan.py
cd web-demo
node scripts/stage-python.mjs
npm exec -- vitest run tests/invoice-details.test.ts tests/overdue-scan.test.ts --maxWorkers=1
npm run build
python tools/check_invoice_details_browser.py --project .. --build dist \
  --chrome /path/to/chromium --output /absolute/new-receiving-directory
```

The browser driver requires Playwright and refuses to overwrite its output directory. Independent isolated-DOM replay instructions are in `qualification/independent/REVIEW.md`; they do not claim to repeat the native full-application gate.
