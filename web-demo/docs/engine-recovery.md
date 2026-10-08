# Recovering the browser's Python engine

A failed runtime load can be retried with **Retry loading engine**. If the
Python worker becomes unavailable, Ledgerly disables the old ledger and offers
**Restart empty sandbox**. Restart creates a new worker and an empty ledger.
The source email and typed invoice corrections remain in the page. Nothing is
replayed automatically.

After restarting with a correction form open, confirm the review again and
choose **Check corrected fields with Python**. That explicit check reopens the
source analysis in the new worker, then validates the retained fields through
the existing Python review action. It does not replace the form with extracted
values. The old checked revision is invalidated; drafting requires a newly
checked revision, and sending still requires its separate approval.

Preservation applies while this page remains open. Closing or reloading the
page still discards its in-memory workflow and source text. Restart does not
recover invoices from the discarded worker. The previous display is inactive
until the new initialization returns its actual empty state.

## Implementation boundary

`worker-client.ts` owns the existing request/reply channel. A worker `error` or
`messageerror` rejects all outstanding requests, removes the old listeners and
terminates that worker. Late events cannot settle requests for a replacement
worker or make its page unavailable. Only an explicit `init` request creates
the replacement.

Ordinary Python action errors leave the running worker available. A synchronous
`postMessage`/structured-clone failure rejects that request and also preserves
the healthy worker. These failures do not establish that its ledger was lost.

`retryable-loader.ts` shares one pending startup attempt and retains a successful
runtime. A rejection clears the cached attempt so the next explicit load can
try again. It schedules no background retries. Startup enables the workflow only
when the initialization result's `ok` field is true.

Recovery is driven by reported worker failures. It does not introduce a timeout
or claim to detect a silently stalled worker or a killed browser tab.

## Verification and provenance

From the repository root:

```sh
python -m pytest -q
cd web-demo
npm ci
npm test
npm run build
npm audit --audit-level=moderate
```

The combined candidate passes 26 browser-engine tests: 11 lifecycle/loader
controls, five controls over the actual application/worker source, the two
original real Python/Pyodide workflows, and all eight invoice-review tests.
TypeScript checking and the production build pass. Native Python qualification
is 52 passing tests; the core files are unchanged. The retained package audit
reports no vulnerabilities at the moderate threshold.

The independent Chrome receiver passes five cases against the final built page
and actual self-hosted Pyodide: transient source loading, terminal startup,
initialization refusal, a lost in-flight ledger action, and retained correction
revalidation. The last case verifies that restart sends only `init`, the next
human check performs fresh analysis and review, exactly one draft is prepared,
and sending still requires separate approval. It also confirms that completed
recovery guidance disappears after valid revalidation.

[The qualification packet](qualification/engine-recovery-c945953fdeb7/README.md)
contains exact source identities, negative controls, build/native transcripts,
independent Chrome receivers and their actual receipts. The source controls use
a small DOM/Worker fixture; they do not substitute for the independent browser
qualification against the built page and self-hosted Pyodide.

This recovery composes over invoice-review commit
`2528de8b66d2b6ab0bed824e3b6ad115052840e6`, preserving that author's parent commit
and all Python validation, extraction, review rendering, styles and tests.
Only the request/recovery hooks in `src/main.ts` and the boot cache in
`src/engine.worker.ts` change among existing files. New helper modules, receiving
tests and these qualification notes accompany them. Dependencies, workflows and
publication settings are unchanged.

Scope owner: `estate-c945953fdeb7/product_delivery`, recorded in
[Ledgerly #6](https://github.com/Jacob-Met/ledgerly/issues/6) and
[HAMON #140](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6055227605).
The invoice-review author's separate contribution remains attributed in
[Ledgerly #5](https://github.com/Jacob-Met/ledgerly/issues/5). Their checkout and
branch were not modified. Qualification is distinct from PR acceptance and any
subsequent deployment.
