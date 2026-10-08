# Complete deterministic browser overdue scans

## Product behavior

The existing **Scan overdue** button now visits every invoice in the current in-memory ledger. Previously, thirteen overdue invoices exhausted the default planner budget after the first eleven visits. Repeated scans revisited that prefix, including already pending or cooling-down reminders, and left the final two invoices unvisited.

This patch changes only the browser Demo's chase invocation. That call constructs the fixed `RulePlanner` directly; Demo exposes no injected planner parameter. The planner needs one list turn, at most one attempted reminder turn per ledger entry, and one completion turn. With `n` ledger entries at the start of the synchronous call, `max(12, n + 2)` is a finite bound for that specific workflow.

The general `Agent.run` default remains twelve steps. Other Demo actions and planner callers remain unchanged. Scanning still prepares queued actions; it never approves a reminder. Current provider facts, pending-action invalidation, cooldowns and explicit action identity continue through the existing core.

## Frozen source and composition

Qualified base: `1b2b902d5dd412a8b61c9b9075b815c1d0029365`, tree `ba5ab49270c136d86bc492411f49a5bdebdb6049`.

Only three source paths are contributed:

- `web-demo/python/bridge.py`: the fixed Demo chase budget.
- `tests/test_browser_overdue_scan.py`: six actual native workflow controls.
- `web-demo/tests/overdue-scan.test.ts`: runs those same six controls in the actual Pyodide runtime.

The bridge beforeimage is Git blob `5573f8b488ee4421e073fce057e6928aac6f6630`, SHA-256 `3e589806d38909801fd4307bf54b9f1f28d3ba7c653d158122e7f18302779eda`. The candidate is blob `5c60ddc5f4e6d0a3407e2a7eeab6f103dbe1c4ae`, SHA-256 `2a1a779a7cab981487fc37c0b87f81f6ecd8b2b587c1f787213aa12818d0bec7`.

All forty-nine native inputs are pinned; the forty-eight unowned inputs remain exact. This includes an unchanged original favicon for complete browser asset loading. Removing the single chase hunk reconstructs the complete bridge beforeimage byte-for-byte. The two new test paths were absent from the complete original tree, which contained no AGENTS.md.

Ownership is recorded in [Ledgerly #25](https://github.com/Jacob-Met/ledgerly/issues/25). Preview #22, CSV #23, amount #19, webhook #21 and approval-outcome #24 remain separately owned. Main advanced to approval-outcome commit `350868091702d60f3dc340be4a017ba49d99f8a0` after this base was frozen. Results below qualify the stated base plus this three-file overlay. Final current-main composition and hosted CI are separate integration checks; no current-core overwrite or hosted-CI pass is claimed here.

## Actual controls and results

| Runtime | Original source with the same tests | Candidate |
|---|---|---|
| Native Python 3.12.14 | Two controls passed; four failed on missing tail IDs or stale provider facts | All six passed |
| Pyodide 0.29.3 / Python 3.13.2, Node 26.3.0, Vitest 5.0.3 | The Vitest receiver failed with four native failures | One Vitest case passed, executing all six native controls |

The cases cover empty/one/ten-invoice ledgers; thirteen fresh overdue invoices; eleven already pending reminders followed by two eligible invoices; eleven cooldowns followed by two eligible invoices; full and partial provider payments whose webhooks are deliberately withheld; exact queued-text replacement and action approval/rejection; and an unrelated nonterminating planner still stopping at its original twelve-step guard.

The original standalone thirteen-invoice reproduction is retained separately. It shows the exact visited IDs across three explicit scans, including the scan after approving all eleven initially queued reminders. The unchanged native test suite then fails on the actual missing queue entries and stale `SENT` status, rather than depending only on the `step limit reached` message.

The production build passed strict TypeScript and Vite 8.3.3. Existing Pyodide node-module externalization warnings are preserved in the log.

## Actual browser receiving

Chrome 154.0.8037.98 ran the production build on an owned loopback HTTP server. Six served Python files were checked against the frozen native source before execution. The receiver observes real Worker requests and replies without replacing responses or injecting queue state.

All three groups passed:

1. The normal UI analyzed, drafted and explicitly approved thirteen fictional invoices, advanced the date, and queued thirteen reminders through **Scan overdue**, without sending any reminder.
2. A second explicit scan preserved every queued action ID and exact payload.
3. After approving the first eleven reminders, another scan preserved the final two; approving the thirteenth and rejecting the twelfth affected the intended actions only.

No off-origin page requests or page errors were observed. Native snapshots reported zero external calls. These are actual `Demo → Agent/RulePlanner/GatedClient/SandboxMock` workflows and in-memory fictional actions, not live PayPal delivery.

`last-two-reminders.png` shows the two tail actions in the unchanged approval UI. The initial full queue is retained in `browser-first-scan.json`; the completed interaction is recorded in `browser-receipt.json`.

## Reproduce

From a receiving checkout containing the patch:

```sh
python -m unittest discover -s tests -p test_browser_overdue_scan.py -v
cd web-demo
npm test -- --maxWorkers=1 tests/overdue-scan.test.ts
npm run build
```

Use the pinned existing dependency lock and Pyodide 0.29.3. The actual native Mac run linked dependency packages read-only from an existing exact-lock cache; build outputs and tool caches were isolated in the receiving directory.

Serve `web-demo/dist` on loopback, then run the retained browser receiver with an installed Playwright test module and Chrome:

```sh
node docs/receiving/browser-overdue-scan-68094585a1c2/check_overdue_scan_browser.mjs \
  --url http://127.0.0.1:8873/ --source /absolute/receiving-checkout \
  --playwright /absolute/playwright/test.mjs --chrome /absolute/chrome \
  --output /absolute/new-evidence-directory
```

The original source, native failing controls, all raw final logs, exact commands, source pins and independent source-only bound review are retained here. Earlier author-test drafts and the unrelated unpublished preview's browser initialization failure remain in their original native checkpoint archives; they are not substituted for this candidate's results.

## Post-run runtime custody

After all jobs completed, the borrowed cache's Pyodide package path was unavailable during the final readback. The four actual staged browser runtime assets remain in this owned build and match their recorded pre-run hashes. The receipt distinguishes those successful readbacks from the unavailable cache metadata/wrapper files. No replacement dependency, reinstall or test rerun was used to conceal that change. Source pins and completed raw results remain intact.
