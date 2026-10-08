# Completed-review history receiving

The maintained browser demo now exposes completed approvals as a read-only history: the original invoice or reminder, its queued timestamp and identity, and the result actually recorded by the Python Agent. This packet qualifies issue #31 and PR #36 through the current invoice-send freshness integration.

## Qualified source and outcome

Qualified head: **ae1e859aa26bffdee7e8b8cb673acd6c74420263**  
Tree: **de61c0086dd1591413820c05de33a3f2a7d49491**  
Received main: **fba278f552e868ad2b94b7f1dc309eed6f1e8514**, including PR40 invoice-send freshness.

[Verify Ledgerly run37808603895](https://github.com/Jacob-Met/ledgerly/actions/runs/37808603895) and [invoice-record run37808603940](https://github.com/Jacob-Met/ledgerly/actions/runs/37808603940) succeeded. The actual hosted merge checkout is **b1aeba460fe9b6b321248ef534d7cd3b0dc444b7**; its complete tree equals the qualified head's tree.

| Gate | Actual result |
|---|---|
| Native Python | 347 tests and 118 subtests passed |
| Frontend, including actual Pyodide | 96 tests in 11 files passed |
| Normal audit, strict TypeScript and production build | Passed |
| Existing CSV and offline invoice-record browser receiving | Passed |
| Completed-history Chrome receiving | 29/29 checks passed; process exit 0 |
| Exact application and build custody | All 45 declared source inputs and 32 dist files unchanged |
| Real browser cleanup | Both processes exited0, no signal/fallback, both owned profiles removed |
| Screenshots | Four exact PNGs visually inspected; stable target geometry and matching PNG dimensions |

This final evidence publication changes only the packet and its documentation after that qualified source. The PR's final publication head and normal current-head gate are reported separately in the pull request and integration receipt.

## What the visitor receives

The **Completed reviews** panel keeps APPROVED, REJECTED and FAILED actions available after they leave the approval queue. Each record shows its original queued proposal, Action ID, **Queued at** value and recorded result. The ordering is most recently queued first; no completion timestamp is invented.

An actual recorded UNKNOWN outcome appears in the collapsed summary as **FAILED · OUTCOME UNKNOWN**, with a visible instruction to check the invoice before creating another approval. A provider's explicit refusal retains its actual body and does not acquire an invented UNKNOWN label. Automatic rejection reasons stay distinct from a visitor's rejection.

Opening a record, inspecting an invoice, selecting result text, or resizing the view does not post a Worker action or refresh provider data. The original pending approval controls remain separate. History belongs to the current in-memory sandbox session; explicit Reset or a new Python session clears it. If the Worker becomes unavailable, the last received history is labeled accordingly until the visitor explicitly restarts.

Both outer review and nested invoice disclosures retain their open state and the exact focused summary across an ordinary snapshot. This includes closing the nested disclosure immediately before the next actual Analyze snapshot.

## Actual browser journey

The maintained Node 22 receiver uses installed Chrome, the built application, its real Web Worker and bundled Pyodide. It observes actual messages and Python replies while delegating the Worker constructor and postMessage.

The healthy journey approves an invoice, rejects an invoice containing Unicode and literal HTML-like text, automatically invalidates a reminder after the date changes, and explicitly approves a new reminder while preserving every unrelated pending approval exactly. It verifies read-only keyboard disclosure and result selection, outer and nested focus, existing invoice details, 390px layout, labeled Worker unavailability, explicit restart, and confirmed Reset.

A separate browser context serves the exact bridge plus a recorded receiving-only suffix. The suffix delegates to the real SandboxMock send, then raises TimeoutError to model a lost response. Actual provider state becomes SENT while the Agent's ledger remains DRAFT; the consumed action appears as FAILED/UNKNOWN. The receiver checks the visible collapsed label, exact original proposal/result and absence of any retry caused by reading history.

Every declared Python asset is checked against its actual source. Page requests are intercepted; Worker requests are observed after enabling Network before resuming each Worker, under the served same-origin CSP. Each observed bridge request is correlated to an attached Worker session. There are no off-origin application requests or uncaught page/Worker exceptions. Browser diagnostic streams are retained rather than described as empty.

Raw final evidence is under [browser/hosted-final](browser/hosted-final):

- [browser.json](browser/hosted-final/browser.json):29 assertions, source/build hashes, network sessions, real fault outcome and process cleanup.
- [healthy Worker observation](browser/hosted-final/healthy-worker-observation.json) and [lost-response Worker observation](browser/hosted-final/lost-response-worker-observation.json): actual requests and replies.
- [qualification.json](browser/hosted-final/qualification.json), [source-preservation.json](browser/hosted-final/source-preservation.json), and [binding-readback.json](browser/hosted-final/binding-readback.json): exact checkout and receiving provenance.
- [visual-review.json](browser/hosted-final/visual-review.json): capture identities, dimensions and visual findings.

### Captured views

| View | Exact dimensions | Inspection |
|---|---:|---|
| [Desktop completed reviews](browser/hosted-final/desktop-completed-reviews.png) | 546×2471 | Original invoices, distinct approved/rejected reminders and recorded results are legible |
| [Phone approved reminder](browser/hosted-final/phone-completed-reminder.png) | 336×595 | Complete heading, message and result; no neighboring card intrudes |
| [Phone literal invoice](browser/hosted-final/phone-literal-invoice.png) | 336×790 | Unicode and HTML-like input remain literal and wrap within the card |
| [Phone UNKNOWN result](browser/hosted-final/phone-outcome-unknown.png) | 336×944 | Complete FAILED/UNKNOWN heading, original invoice and warning/result |

These are element captures from 1440px and 390px browser viewports, not claims that every card fits within the 844px phone viewport. The receiver sets its scrollbar state before navigation and records the document-space clip, viewport, target rectangle and PNG dimensions. Product CSS and application source are unchanged by that receiving condition.

## Independent review and preserved failures

The initial published implementation is 838f1f5; the nested-disclosure correction is 2d5e275. The independent unchanged oracle reproduced the original defect: seven controls passed and the nested disclosure reopened and lost focus. On the corrected source all seven application controls passed. That native process still failed at its final screenshot after a Chromium GPU/capture error. A separate zero-check native startup failure is preserved as an environment boundary. See [independent/REVIEW.md](independent/REVIEW.md) and its exact raw receipts. The separate [final independent addendum](independent/FINAL-HOSTED-REVIEW.md) accepts the exact current-main source, actual hosted semantics, cleanup, geometry and source preservation; it attributes direct pixel inspection to the integration reviewer.

The original native baseline includes eleven healthy controls and three expected missing-history checks. Two altered-source controls fail semantically under the unchanged history oracle: omitting FAILED records and allowing nested payload/result aliasing. Their original source, streams and receipts remain in [native/history-baseline.json](native/history-baseline.json) and [native/history-negative-controls.json](native/history-negative-controls.json).

The hosted sequence remains immutable:

| Packet | Observed result |
|---|---|
| [Attempt 1](browser/hosted-attempt-1/boundary.json) | Zero application checks; unsupported Worker Fetch command stopped the receiving harness |
| [Attempt 2](browser/hosted-attempt-2/receiving-note.json) | Twelve checks passed; an incorrect global-empty-queue assertion failed while an unrelated approval correctly remained pending |
| [Attempt 3](browser/hosted-attempt-3/qualification.json) | All 29 checks passed on then-current main; visual review found one phone capture clipped its target heading |
| [Attempt 4](browser/hosted-attempt-4/capture-boundary.json) | Current-main 347/96 gates and thirteen browser controls passed; the added geometry guard detected a changed card width during screenshot capture |
| [Final](browser/hosted-final/qualification.json) | Current-main gates, all 29 browser controls, stable geometry and all four complete captures passed |

The merged send-freshness policy performs a read before any outgoing permit. The history test's old CANCELLED-before-approve fixture would now correctly auto-reject before sending. Its narrow receiving adaptation asserts the fresh GET saw DRAFT, then changes only the test fixture at the real outgoing call and delegates to SandboxMock. The exact GET→POST failure still retains FAILED, the actual provider body and no UNKNOWN. Existing preflight, provider, queue and payment policies are preserved.

Earlier fixture and receiver corrections are also retained: text payment terms required by the existing adapter, structured/literal renderer expectations, an overescaped test-only regex and a missing native Playwright executable. Historical paths describe actual custody; they are not installation requirements.

A separately launched native broad receiver, process 3369422 under an existing 240-second wrapper bound, became unreadable during a service-wide RDC outage. Its completion is **unknown**, and no duplicate native run or successful archive transfer is claimed. This remains separate from the fully retrieved hosted acceptance.

## Reproduction and integration

After the normal installation and build in `web-demo`, use a new output directory:

~~~sh
node tools/check_review_history_browser.mjs --source .. --dist dist --chrome /path/to/chromium --output /path/to/new-receiving-directory
~~~

A normal Git checkout supplies its own exact source binding. An isolated text hydration must supply `--source-manifest` explicitly. The existing CI step runs this receiver after the CSV receiver. Setting `LEDGERLY_HISTORY_EMIT_BUNDLE=1` emits only bounded regular receipt/capture files from the owned output directory through normal job logs. All 649,011 bytes of the final 11-file packet were reconstructed with ordered chunk/length checks and exact returned Git-blob identities; producer SHA256 fields are preserved in its manifest.

The repository's configured destination is [jacobmetoyer.com/ledgerly](https://jacobmetoyer.com/ledgerly/). The established `.github/workflows/pages.yml` builds and publishes `web-demo/dist` after relevant main pushes. Deployment and live-site acceptance belong to the subsequent normal integration receipt; this source qualification alone does not claim that an already-open page has updated.
