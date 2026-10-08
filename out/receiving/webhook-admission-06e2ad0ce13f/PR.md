## Problem

Delayed payment notifications can overwrite newer ledger facts. The current ID-only
index also consumes unknown-invoice notifications and treats changed content under
an accepted ID as an exact duplicate. This can display an obsolete balance and
unnecessarily discard a still-current reminder review.

## Change

For a known new event, reuse the current-invoice read and reminder invalidation from
merged PR #10 before recording the event ID. Require canonical event/invoice IDs,
bind accepted IDs to the complete canonical JSON body, and reject content conflicts.
An unavailable read or unknown local invoice leaves the notification retriable.
Signature verification still precedes duplicate acknowledgment when configured.

Production edits are limited to the import, index initialization and webhook handler.
The eighteen other Agent methods, current invoice-deadline behavior and prior-payment
evidence code remain exactly main `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`.
The pending extraction/value-validation component is separate.

## Validation

- All 12 author regressions fail against the exact original source and pass with
  the repair. The independent reviewer sees 23 failures and 3 controls on that
  baseline, then 26/26 passing on the accepted component.
- Final current-main native suite: **157 passed, 34 subtests passed**.
- Independent clean composition with the separately accepted extraction change on
  the same current main: **235 passed, 34 subtests passed**, plus actual npm staging
  and **10/10 Pyodide tests**. The composite source and exact preservation proofs
  are in `out/receiving/ledgerly-composition-independent-06e2ad0ce13f/current-4bda/`.
- After receipt-term PR #20 advanced main to `1b2b902`, an independent clean
  composition of the actual published PR #19 and #21 heads passed **246 tests and
  60 subtests**, plus actual npm staging and **10/10 Pyodide tests**. The new owner's
  receipt terms and methods remain exact. The complete packet is in the adjacent
  `current-1b2/` receiving directory. No source correction was required.
- The accepted predecessor passed **132 native tests and 2 subtests**, the actual
  Pyodide browser bridge/review suite (**10 tests**), and the production build.
- Two old assertions were updated after independent review: monetary equality
  replaces a decimal-string spelling check; an unchanged current GBP 500 review
  survives a delayed snapshot and sends its exact text once only after approval.
  Original failures, reviewed diffs, source copies and hash manifests are retained.

See `out/receiving/webhook-admission-06e2ad0ce13f/README.md` and the adjacent independent
packet for exact source pins, commands, negative controls and bounds.

The event index remains in memory. All provider-facing verification used offline
`SandboxMock`; this PR does not establish live PayPal delivery or durable replay
storage. No provider activation or deployment was performed.
