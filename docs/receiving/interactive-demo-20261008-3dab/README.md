# Interactive demo: declining every invoice

The documented `python -m ledgerly.demo --interactive` should let a reviewer
decline every queued send and still finish the walkthrough. On original main
`d4d3802b7f5ccd78795d91159d907b08cb3e978f`, four no responses leave the invoices
as drafts. The CLI then indexes the empty `sent` list, raises `IndexError` at
`ledgerly/demo.py:64`, and exits before the final ledger and network summary.

The correction runs the existing mock payer/webhook step only when a sent
invoice exists. Otherwise it explains that the mock payment is skipped, then
continues to the existing overdue check and final ledger. It does not convert
a rejection into approval, choose a different financial action, or change the
approval gate. The original scripted walkthrough remains available.

## Exact source scope

Only `ledgerly/demo.py` changes in production source. The focused standard-library
test file is `tests/test_demo_interactive.py`. Core extraction, pricing, provider,
approval/reminder methods, browser source, README and workflows retain their
existing owners and bytes. Current issues #5 through #8 were read before this
scope was announced to the root coordinator and in commentary.

| Candidate file | SHA-256 |
| --- | --- |
| `ledgerly/demo.py` | `6c4106f9a2fdc5ab4555a5efa1b95c61b2da2cee5c864661f7063540af572a1f` |
| `tests/test_demo_interactive.py` | `dd0b507e0f542ea158ec5a6cb13907880ff774723deb5d41dae9fcbab37c1205` |

## Native verification

The original ten materialized source/fixture blobs match their exact Git
identities. All original source bytes remain in a separate baseline copy; the
nine untouched candidate blobs match that baseline. The linked
[native receipts](native-receipts.json) preserve these pins, the actual commands,
runtime identity, exit statuses and complete stdout/stderr with their hashes.
They contain no whole-source archive.

| Control | Original source | Corrected source |
| --- | --- | --- |
| Actual interactive CLI, all no responses | Exit 1, `IndexError`, no final ledger/report | Exit 0, skipped mock payment, final ledger/report |
| Explicit no and default blank in the native mock | Empty-list errors | Every invoice remains DRAFT; no send, reminder or recorded payment request; no payment transactions |
| First invoice rejected, later invoice approved | Pass | Only that later approved invoice is sent and paid in the mock |
| Two sends approved, later reminder rejected | Pass | Reminder still requires its separate decision; no reminder request occurs |
| Original scripted mode | Exit 0 | Exit 0; existing payment and reminder walkthrough retained |

The five-method suite fails the two refusal methods on the original source
(one method has explicit-no and blank-answer subcases). It passes all five
methods on the candidate. The tests inspect the actual `SandboxMock` requests
and invoice states and also execute the real module entry point in a fresh
process.

```bash
python -B -m unittest discover -s tests -p test_demo_interactive.py -v
python -B -m ledgerly.demo --interactive
```

All receiving uses the repository's in-memory `SandboxMock`, synthetic fixtures,
and `LEDGERLY_ALLOW_NETWORK=0`. No provider account, credentials, real sending,
payment, financial decision or live application is exercised. This is a CLI
workflow correction; it does not qualify PayPal integration or browser changes.

[Independent review](independent/REVIEW.md) approved the exact candidate after
three separately authored methods: the original refusal failure is retained,
while the candidate passes refusal, later-only approval, and independently
declined-reminder controls. The reviewer used the actual SandboxMock with
network calls disabled. Its source pins, probe and raw outputs remain in the
[review manifest](independent/manifest.json). These three methods are separate
from the five author methods above.

The root integrator also reviewed the narrow source delta. Exact published-head
checks and hosted CI are recorded in the accompanying pull request. The existing
main-branch workflow includes `ledgerly/**` and may schedule Pages publication;
browser staging does not copy `demo.py`. No deployment workflow is changed.
