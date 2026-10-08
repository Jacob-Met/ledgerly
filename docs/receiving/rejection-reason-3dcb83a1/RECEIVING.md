# Rejection reasons: author receiving

The browser now carries an optional reviewer note into the existing rejection
result and audit for the selected pending send or reminder. It does not change
the core Agent, its approval policy, invoice data, provider, or completed-history
owner. The scope is recorded in [HAMON issue 140](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6063937559).

The core already retained a supplied reason. The original browser bridge
discarded the request's reason and used a fixed default; the original built UI
also had no reason field. Both boundaries were executed directly against
`fba278f552e868ad2b94b7f1dc309eed6f1e8514`, before any source publication.

## Received behavior

Six focused native methods improve from nine failed assertions in the unchanged
baseline to zero in the candidate. They use the complete current Demo, Agent and
SandboxMock: exact literal reasons and audit storage, duplicate refusal, legacy
blank defaults, type/length refusal before consumption, a valid 500-code-point
retry, another queued action's independence, ordinary approval, and reminder
rejection without a send.

The actual built browser receives two separate currency actions and passes eight
control groups with the real Pyodide 0.29.3 worker. Typing alone sends no worker
message. Notes survive an unrelated busy snapshot and an actual bridge refusal;
explicit keyboard rejection submits only the selected note and preserves the
other draft. An unfinished over-limit note does not change the independent
approval payload. Narrow-screen reminder rejection and empty/default/reset
behavior are received. The phone screenshot was directly inspected.

All observed HTTP requests remain on the test server's local origin. The date
input's embedded SVG is recorded separately as a browser resource. Selected
rejections add no mock provider request; the independent approval control makes
its ordinary sandbox requests.

## Replay

The native regression is an ordinary collected unittest module:

```sh
python -m unittest discover -s tests -p test_browser_rejection_reason.py -v
```

After the repository's normal pinned build, use Node 22 or later and an installed
Chrome with its normal sandbox:

```sh
cd web-demo
npm ci
npm run build
cd ..
node web-demo/tools/check_rejection_reason_browser.mjs \
  --project . --browser /path/to/chrome \
  --output /path/to/new-rejection-reason-evidence
```

The browser driver starts a private local server and an exclusive temporary
profile, records real Worker replies, and removes only that profile on completion.
It never replaces Python or provider results. One original reply is delayed to
receive busy controls; one authored invalid outgoing action ID obtains a real
bridge refusal. These test interventions are explicit in its source and receipt.
Its disk, memory and retained-output guards are unchanged.

## Evidence boundaries

`author-results.json` is a compact derivation of the pinned raw native/build/
browser receipts. It records commands, source and runtime pins, all eight browser
groups, the actual Worker request sequence and compact reply projections.
The complete raw browser snapshots and command logs remain at the native roots
listed there. The exact small browser negative-control receipt is preserved as
`browser-baseline.json`; it starts the genuine engine and stops at zero reason
controls versus two actual pending actions.

The normal Linux Chrome attempt refused before page load because a usable
sandbox was unavailable. That refusal is retained; no sandbox protection was
disabled. The subsequent Windows run uses existing CfT 154. Two original
receiver failures are also retained: unsupported Worker Fetch-domain control and
misclassification of a native inline date SVG as an HTTP request. All eight
product groups already passed in those runs; their overall failed statuses are
not relabeled. The exact small transitions are in
`receiver-transitions.json`; no product source changed during those refinements.

Native Python 3.13.7 first established the full-source bridge witness in memory
without Mac source copies. Linux Python 3.14.4 ran the six-method comparison.
Ordinary isolated installs of the unchanged lockfile built both variants on
Linux Node 22.22.1 and Windows Node 24.21.0. No shared dependency, configuration,
service, provider account or installed app was changed.

The independent review is published in the adjacent independent evidence
directory with its own contract, fixture and attribution. Hosted final-head CI
and source integration are recorded in the PR; these native results do not
claim either event.
