# Ledgerly invoice-send review freshness — authored receiving

Contributor: `runtime_execution`, coordinated with the current estate through root.
Claim: https://github.com/Jacob-Met/ledgerly/issues/32 .
The native source reservation was recorded at 2026-10-08 13:36:51 UTC, before source edits.
The neighboring money owner was notified in PR19 comment6061119042.

## Source and concrete outcome

Baseline main is `2d3a90a9aa794d849ec54ca9d32a720959ddc5db`, tree
`cb1877320fc40166cc7f10c035d5e7866be53713`.
Baseline agent blob is `3ae7fcae5b1b243f608ab1bea6e25313a2fea091`;
its SHA-256 is `1547047380e848e2527374cf0f0c381d4ef1155e04d729bd9af74e1e8dd14c05`.

Frozen successor agent blob is `45b8fc05cd18b3e8ca5a42bf97b0ade9a4fbbb98`;
its SHA-256 is `f2bc79188eb9b4933f969ba3c6a08397fec5b6b3f4678add22c396fb5d0584eb`.

The real Agent queued the original invoice body, but approval previously sent the current
provider invoice by ID without another read. The unchanged five-case public probe shows
three unintended sends after the provider draft changes: another billing recipient,
different work at the same total, and another deadline. An unchanged draft and a metadata
change are the two passing baseline controls. The successor passes all five, preserving
the original review and issuing no send POST for the three changed drafts.

No actual provider account, email delivery, payment, or network transport was exercised.
SandboxMock is the repository's native in-memory provider; its records and public methods
supply the authored changes and observable calls.

## Implemented boundary

Only Agent.approve is changed among the 20 existing Agent methods. The other 19 existing
method source segments are byte-identical. Two send-specific helpers and an import of the
existing quantize function are added. Draft allocation, extraction, provider code, reminder
policy, due-date projection, web implementation, and the outgoing failure handler remain
unchanged.

Approval performs a current-invoice read before opening any outgoing permit. The read must
identify the same invoice. A known non-DRAFT status rejects the original action. For a
usable draft, the complete supported writable content is compared with the queued body.
A difference rejects the action and preserves the payload as history. Repeating that
rejected action causes no further provider call. The cached deposit and its currency must
also remain consistent with the queued send/deposit review.

The projection permits known delivery metadata, read-only generated item/group IDs, empty
CC lists, equivalent finite decimal strings, and matching generated totals on the simple
untaxed invoices emitted by build_invoice. Any new fee, recipient, item, term, setting, or
other unrecognized invoice content stays visible to comparison. Incomplete or inconsistent
responses, nonzero payment facts, or unavailable reads stop before a permit and leave the
review pending for an explicit retry. They do not claim an unknown outgoing result.

After outgoing execution starts, the existing PayPal-error and FAILED/UNKNOWN consumption
rules remain intact, including response loss after a send or recorded deposit.

This is an observable pre-send freshness check. The current HttpPayPalClient performs
separate reads and send-by-ID requests. A later provider edit can race that boundary;
there is no atomic comparison or live-provider qualification claim. The primary API
references are [show invoice](https://developer.paypal.com/api/invoicing/v2/invoices-get),
[update invoice](https://developer.paypal.com/api/invoicing/v2/invoices-update),
[send invoice](https://developer.paypal.com/api/invoicing/v2/invoices-send), and
[the provider schema](https://developer.paypal.com/api/invoicing/v2/schema.json).

## Native receiving

The local interpreter is Python 3.12.14, Clang22.1.3. The project test runner is pytest9.1.1.
All commands use `-B`; pytest cache writing is disabled. The public fixture is the
repository's fictional `fixtures/01_simple_usd_hourly.txt`.

| Receipt | Baseline | Frozen successor |
|---|---:|---:|
| Unchanged original stale-send probe, SHA a97347bd… | 3 failures / 2 controls passed | 5 passed |
| Additive public boundary probe, SHA d922bb8e… | 32 failures | 32 passed |
| Original inherited suite, excluding the two authored probe files | 185 passed, 63 subtests passed | See explicit adapters below |
| Complete assembled suite, including both probes and adapters | — | 222 passed, 63 subtests passed |
| Real scripted `python -m ledgerly.demo` | — | exit0; network calls0 |
| Real interactive CLI, decline every approval | — | exit0; network calls0 |

The additive controls require the fresh GET before the normal send, so even their
otherwise-sendable baseline executions fail that missing-preflight assertion. The original
five-case probe independently retains two positive baseline controls; the 32 failures are
not presented as 32 distinct product defects. There are no skipped cases in these runs.

The unchanged original first probe is
`a97347bd3635c05aa4d94047b6aaf79bd65d8230efc30856d7dfda203cbc4959`.
The additive test is
`d922bb8e2af7f110f3460fe1e82de7c2d1d573a94fc45e1d57092103cfcc4f2d`.
The raw reports include call logs, old review payloads, provider records, action states,
exceptions, and source fingerprints. Original failed output is retained unchanged.

The browser's unchanged stage-python.mjs blob f06d27ecc0a4ff4a09517ca6d3fef5887e8be7d6
copies the root agent.py to its Python assets. The unchanged engine.worker.ts blob
efff0b9f8e88d7471f89b46cb20f1a28eaad62c1 loads that staged source into Pyodide.
This establishes the source receiving path; it is not evidence of an installed or already
running browser receiving the change. The eventual actual-head CI is a separate gate.

## Explicit receiving adapters

The original `tests/test_approval_outcomes.py` blob
`f4c7abe598388131fd207b935e87a8bf3ca68024` is retained. Its PayPal-refusal fixture
previously set CANCELLED before approval. The fresh read now correctly refuses that known
status without a POST. The adapted fixture instead asserts that a fresh GET saw DRAFT,
then changes status at the outgoing boundary and calls the real SandboxMock send.
It observes one refused POST and preserves the original PayPal body, failure audit,
consumed approval, no-retry, and closed-permit assertions.

Three methods in original `tests/test_receipt_term_receiving.py` blob
`fb5d293f3944480b86524eb98c8ee19a7ce53174` changed provider terms and then approved
the earlier invoice body. The adapter first asserts rejection, no POST, exact payload
retention, and unchanged cached date facts. A separately labeled external SandboxMock send
then feeds the existing current-invoice projection. Every original due-date assertion
continues to run. The untouched raw/reviewed receipt workflow methods still exercise
actual Agent-approved sends across calendar boundaries. No source-level receipt behavior
is relaxed, and no test creates a new approval by rewriting a queued payload.

Exact adapter hashes:

- Outcome fixture: `3d178a8200e771d4c3ceda056d78efdc0486813f7971ffb9eef0a5927bb6a3f3`.
- Receipt fixture: `635b01a43b27594fca056abfce20d3d044d7356512b55eab691e5da2a8679b29`.

The original four selected methods were replayed against the final f2bc source before
these adapters were accepted. Their exact pytest result is retained:
`6 failed, 1 passed, 5 subtests passed`. The failures include three parameterized
provider-term subcases. The source pin is printed at the beginning of that raw log.

## Reproduction and custody

The archive preserves complete compact baseline/successor Python source capsules,
fictional fixtures, original test files, original and successor logs/reports, CLI outputs,
and a per-member manifest. Archive paths are regular relative files; file bytes are
unchanged. Tar header ownership/time are normalized for reproducibility.

From a capsule with pytest installed:

```sh
python -B -m unittest discover -s tests -p test_invoice_send_freshness.py -v
python -B -m pytest -q -p no:cacheprovider tests/test_send_review_boundary.py
python -B -m pytest -q -p no:cacheprovider
python -B -m ledgerly.demo
```

For the original inherited-only baseline result, exclude both authored probe files from
the full pytest command. The raw first broad successor failures also preserve their exact
initial candidate source; the later selected-adapter failure log binds the final f2bc source.
Independent receiving and actual-head hosted CI are recorded separately from this author
qualification.
