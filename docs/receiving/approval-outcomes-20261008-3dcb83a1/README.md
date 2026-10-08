# Approval outcomes receiving — 2026-10-08

## Qualified behavior

An ordinary exception during the outgoing phase consumes that approval ID as `FAILED`, with an explicit `UNKNOWN` outcome, error type and instruction to check the invoice before creating another approval. The original exception still propagates. A retry of that ID is refused before another provider request. The existing approval failure audit records the uncertain outcome and reason.

The read-only reminder preflight remains before this handler. An unavailable read there leaves the original action pending for an explicit retry. Existing `PayPalError` result bodies and audit behavior are unchanged.

Production scope is 18 added lines inside `Agent.approve`, plus one new test file. Provider, extraction, amount, date, browser and workflow source are unchanged. Source coordination is [issue17](https://github.com/Jacob-Met/ledgerly/issues/17).

## Exact source and execution

- Original parent: `1871942ecb19aa9756bb36b380795bc6c7bf238d`.
- Actual parent tree: `a26d5ff9705e83bc248857d4b501068da0b6fb16`.
- Original Agent blob: `19f261b1430769952057697d68472722a11cf643`.
- Candidate Agent blob: `c1c88bd74bc96328f296688ef6592e67cd5c38cb`; SHA256 `416ecbadf7c1024dbc1538b0da8ea7bee3f6c5af81140fe15031cfc211e16525`.
- Candidate new test blob: `f4c7abe598388131fd207b935e87a8bf3ca68024`; SHA256 `a7fbdfb6f73657a8a3f7c5f7b4c9444e9381783567aea83e89d30032f6f935c2`.

The isolated native workspace `/home/jacob/ledgerly-approval-3dcb83a1` contains 29 selected text source/config/fixture files. Every selected original byte sequence was checked against the canonical Git blob; 28 unmodified candidate files were also checked before and after execution. This is a sparse source collection, with the complete original source retained in Git. Python 3.14.4 and pytest 9.0.2 were already installed; no package install, shared cache edit or heavyweight build occurred.

| Native command group | Observed result |
| --- | --- |
| Complete original core suite | 94 passed; 2 subtests passed |
| New 11 controls on original source, with only the test overlaid | 8 failed; 3 unchanged controls passed |
| Complete candidate core suite | 105 passed; 2 subtests passed |
| Actual Agent/SandboxMock replay | Lost reminder response: one request, consumed approval and same-ID retry refused; preflight loss: zero initial reminder requests and one successful explicit retry |

The eight retained failures cover completed reminders with timeout, transport and JSON errors; send errors before/after the mocked effect; malformed successful send response; and send/deposit sequences with response loss during payment or the following read. They exercise ordinary exceptions through actual public Agent methods and real SandboxMock state transitions.

The initial control sent two mock reminders after retrying one approval ID, while the old ledger counted one. On the candidate the known mock effect count is one, while the local counter remains zero because its caller never received confirmation. No success or reconciliation is invented from a lost response.

## Independent receiving

A separately authored, unchanged four-method receiver runs the actual `bridge.handle_json` API through native Python. It produced two failures and two retained controls on the original source, and four passes on the exact candidate with no errors or skips. It independently checked the Agent method delta, seven unchanged receiving files, original/candidate hashes and permit revocation.

| Independent case | Candidate observation |
| --- | --- |
| Completed reminder then TimeoutError | Same-ID bridge retry cannot issue a second reminder |
| Completed send and deposit, then URLError in the final status read | Same-ID bridge retry cannot issue a second send or payment |
| Read-only reminder preflight URLError | Approval remains pending; explicit retry succeeds with one reminder |
| Existing PayPalError | Original error body, failure audit and revoked permit remain intact |

The bridge currently looks up only pending IDs. Its refusal of a consumed ID is reported as `StopIteration`; this unchanged presentation is distinct from the direct Agent API's explanatory `ValueError`. Neither receiver dispatches again. Browser rendering and worker lifecycle are outside this native review.

The unchanged harness SHA256 is `125bb8ae3f739ec9f655df9e68ee6e747c7b9d09666b0e9d64496210defb96bf`; the compact complete receiving summary SHA256 is `62271c498fc117dfce9fa4973a73c65efa8add3b577605cc4a509465c094ab9f`. Both are retained under `independent/`; raw original receipts remain in the separate receiver's native directory and are identified by hash in that summary.

## Reproduction and evidence

At a checkout of the candidate, the normal project command is:

```sh
python -m pytest -q
```

The new controls are in `tests/test_approval_outcomes.py`. `reproduce.py /absolute/path/to/source` is a standalone offline replay usable with either source version. It replaces `urlopen` with a failing guard and reports attempted external calls. The initial and final receipts report zero.

`source-pins.json`, `product-pins.json`, `native-results.json`, `baseline-reproduction.json` and `prepublication-compatibility.json` record source identities, exact commands, retained stdout/stderr and owner composition. `native_check.py` is the original one-shot native orchestrator, executed with adjacent `baseline/` and `source/` collections; it creates a separate baseline control containing only the new test. The product diff is reproducible from the two source versions and the retained orchestrator.

Before and after commands, the orchestrator requires at least 512 MiB free and limits its own retained file size to 16 MiB. Each subprocess has a 45-second timeout. Those are checks and deadlines, not kernel disk/memory quotas. The original recorded native size was below 700 KB and free space was approximately 3.8 GB. Later current-source overlays and compact publication payloads are retained under the same 16 MiB owned-file guard.

## Intervening current-source composition

After the frozen native receiving, main integrated PR13 at `327bd786dcca35a990152e7430eaf3d303975d27`, tree `04cb386caa190308946e367c2c6990e1d81ee66a`. Its approval method remained byte-identical to the original baseline; changes were deadline capture and five additive test/evidence files.

A separate native composition replaced only that unchanged method with the frozen candidate method, preserving every other current Agent byte. The exact current due-date tests plus the new approval tests passed **25/25**. This resolves the concrete intervening source interaction without reassigning the original full-suite or independent bridge results to a different source.

The composed Agent blob is `defa9fa5f96726713f9b1254716a15d2aeba2a14`, SHA256 `f4051a876d0ef1f6e5d1cb29eff4aaf6948994143ecea33e1df09f3c17976e7d`. `compose_current.py` and `current-composition.json` retain the exact recipe, input pins and result. The publication continues to parent original `1871942`; a normal three-way merge retains the other owner's separate contribution.

A later read found main at `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`, tree `00b89f15758d8c8cebcb48f6397b18d466ec355a`, after prior-payment extraction and browser recovery integration. The whole current Agent remains the same `892cf5c59cdc0ad9eafa2926164f45b5b0b36441` blob as the qualified deadline composition; extraction is now `c4ee64a72f6b7613d5ded235de4ca09a9bbd55f6`. A separate exact current overlay keeps that extraction and every other selected current byte, substituting only the same frozen approval method. The composed Agent remains `f4051a87…` above.

Current prior-payment, deadline and approval controls pass **36 tests and 32 subtests**. Because extraction changes the setup of the actual bridge fixtures, the author also replays the unchanged independently authored four-method harness on this composition: **4/4 pass**. The completed reminder and send/deposit scenarios still cannot dispatch again; the read-only preflight can still be explicitly retried. This is additional author current-source receiving, not a new peer acceptance of a different source. All 32 selected source/test files were pinned. `compose_latest.py`, `latest-composition.json` and the additional section of `prepublication-compatibility.json` record these pins, commands, effects and the retained raw bridge receipt.

## Boundary

Qualification covers ordinary Python exceptions and the same in-memory approval ID. It does not establish provider idempotency, durable restart recovery, concurrent approval serialization, process termination handling or automatic reconciliation. A new approval is a separate decision requiring the invoice to be checked. All effects were synthetic SandboxMock events; no provider credentials, actual invoice send, payment, message or installed browser deployment was used. Browser-engine hosted CI is reported separately by the PR; this native author run is not a Pyodide or browser execution claim.

## Receipt-term integration at current main

Current main `1b2b902d5dd412a8b61c9b9075b815c1d0029365` adds mock send resolution of receipt-relative terms. Its `Agent.approve` remains identical to the original approved action path; other Agent and PayPal mock bytes have changed and are preserved exactly in a new isolated composition. Substituting only the frozen corrected approve method produces Agent SHA256 `743d283a5525a33820b1a2616054384e0013927c5e54cd12275c9160b9b8fd3a`. The 22 approval and new receipt-term tests pass with 26 subtests, and the unchanged independently authored four-method bridge harness passes 4/4 when replayed by the author. All 33 selected files are pinned before and after. This current receiving is recorded in `compose_receipt.py` and `receipt-composition.json`; the original independent acceptance stays at its original source and is not relabelled as a new peer review.
