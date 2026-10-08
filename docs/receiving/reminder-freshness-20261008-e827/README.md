# Reminder review stays attached to current invoice facts

Contribution: `estate-e82707f2bc62`, coordinated in Ledgerly issue #8.
Original source: `main@d4d3802b7f5ccd78795d91159d907b08cb3e978f`.

## Product behavior

A reminder reads the provider invoice before drafting and again before approval.
Its original subject, note, recipient, balance, due date and review day remain
bound to that review. A partial payment, a changed invoice or a later review day
rejects the old action with a retained reason. The user drafts and separately
approves a new reminder; the rejected message is never silently rewritten.

The invoice read validates its requested identity, one billing recipient,
currency-consistent finite nonnegative amounts, a representable balance, and
an explicit due date or `NO_DUE_DATE` before updating any cached presentation.
Fresh drafts then use those refreshed facts, including changed recipient names,
totals and due dates. Incomplete or unsupported responses cannot authorize a
reminder. A read failure sends nothing and leaves the pending action available
for an explicit retry. Equivalent decimal formatting and unrelated delivery
metadata do not invalidate an otherwise unchanged review.

The existing browser bridge consumes this behavior without a source edit.
Returned pending-action views are detached from the internal queue, so display
code cannot mutate the reviewed message through a returned dictionary.
Invoice-send/deposit approval, extraction, provider code and browser startup/
correction UI retain their existing owners and interfaces.

## Evidence and replay

The authored 10-method suite retained eight failures, one error and one passing
control on the original source. The independently authored 27-method suite
retained 22 failures and five controls. The first candidate passed the initial
18 independent checks but failed five further provider-change checks: a new
review could bind fresh provider metadata to an old local total, due date or
recipient, or accept a missing balance or wrong invoice identity. Those findings
caused the atomic presentation refresh in the final implementation.

Final focused execution: **37 passing methods** (10 authored plus 27 independent)
through the real Agent, SandboxMock and unmodified browser bridge. The unchanged
27-method independent review was also rerun separately with stable source hashes.
Raw original failures, the final log and independent receipt are retained here.
These tests use fictional data and perform no provider network calls.

### Composition with the current browser review flow

While this PR was publishing, browser correction PR #9 reached main at
`dc5e188c062bb7b45a8ddbbd23a3da75126e17a8`. Its bridge now imports the sibling
`review.py`. The initial hosted run `37752507854`, on receiving checkout
`ce2885001b79dfdc66dcf3428512d4083a4a16c3`, passed all 10 real Pyodide tests,
the browser build and dependency audit. Python collection failed twice because
the new tests loaded the bridge without its sibling module directory. The
actual failure log is retained as `ci-initial-failure.log`.

Only the two test loaders were corrected to expose that directory temporarily.
The production Agent remained byte-identical, the current browser files remained
byte-identical to PR #9, and every reminder assertion remained intact. The raw
draft protocol still exists in the current bridge; no protocol adaptation or
test skipping was required. All 37 focused tests then passed on this composition,
including a separate independent replay of all 27 receiving tests. The new
`current-bridge-*` logs, manifest and independent receipt pin this composition;
the earlier logs and `source-manifest.json` still describe the original bridge.

```sh
python3 -m unittest discover -s tests -p 'test_reminder*.py' -v
python3 -m pytest -q
```

The first command is stdlib-only. The second is the existing repository suite
and runs in the unchanged GitHub `Verify Ledgerly` workflow, together with the
real Pyodide browser-engine tests and build. Local pytest was unavailable when
this packet was prepared; its hosted result must be read from the exact PR head,
not inferred from the focused result. Test baselines can be replayed by placing
these new tests over the immutable original checkout; no production state is
needed. `source-manifest.json` pins selected inputs, candidate code and tests.

## Scope and receiving limits

This closes stale observed-state approval in the existing synchronous product.
A provider can still change after the final GET and before the reminder request;
the current provider interface has no atomic compare-and-send operation. These
tests do not claim that stronger guarantee or real PayPal sandbox qualification.
Multiple billing recipients, absent due-date evidence, or balances that cannot
be represented by the existing total-minus-paid ledger are refused for review.
Original queued actions and audit history remain in the current in-memory store.
No automatic action replay, new persistent store or real client communication is
introduced.

Current source integration, hosted CI and any existing Pages deployment receipt
are recorded in the receiving PR. Parallel core amount-validation issue #7 and
browser issues #5/#6 retain their disjoint implementation scopes.
