# Independent review: declined interactive demo

**Approve the narrow `ledgerly/demo.py` correction**, SHA-256
`6c4106f9a2fdc5ab4555a5efa1b95c61b2da2cee5c864661f7063540af572a1f`,
against baseline `d4d3802b7f5ccd78795d91159d907b08cb3e978f`.

The original demo crashes at `sent[0]` when every proposed send is declined.
The candidate checks whether any invoice was sent, skips the nonexistent mock
payment when the list is empty, and continues to its final ledger report.
The approval decisions, provider implementation and reminder logic are
unchanged. No reviewer source edits were made.

Three independent methods exercised the actual demo and existing in-memory
`SandboxMock`, with `LEDGERLY_ALLOW_NETWORK=0`:

| Boundary | Original | Candidate |
|---|---|---|
| Declined/default-No decisions preserve drafts, create no send/reminder/payment action, and reach the terminal ledger | `IndexError` before report | Pass |
| Only the last explicitly approved invoice is sent and receives the mock payment, after its decision | Pass | Pass |
| Every remaining overdue invoice still requires a separate reminder approval; declining those reminders leaves them unsent | Pass | Pass |

The approval-gate demonstration still reports the unapproved direct send as
blocked. Successful runs include every fixture invoice in the terminal ledger
and finish the existing offline summary. The original failure and both
positive controls are retained in `baseline.stderr`; all three candidate
methods pass in `candidate.stderr`. All ten baseline source pins and the
candidate's one changed production file were checked before and after the
runs, and remained unchanged.

This review covers the offline demo only. It constructs no real provider
client and performs no account operation, real invoice send, payment, or
external decision. The reviewed mock's payment simulation changes only its
in-memory invoice state. Browser, core validation and reminder implementation
ownership remains untouched. Publication and integration stay with the owner
and root while GitHub writes are paused.

Replay the compact independent probe against an exact local subject:

```sh
LEDGERLY_REVIEW_ROOT=/absolute/path/to/candidate LEDGERLY_ALLOW_NETWORK=0 \
  python -B test_declined_demo_review.py
```

`receipt.json` records the source maps, Python version, commands, source
stability and output hashes. The owner's five authored methods and real CLI
entry-point receipt are separate evidence and are not added to this review's
three-method count.
