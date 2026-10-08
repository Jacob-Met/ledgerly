# Ledgerly separate-table extraction: qualified native source

The accepted runtime is `c81365e864e63ad47de7ba37cc5e939dc0461465`, tree `20e4fed3a1f4ef21f7eebcf4d40fcfdbab7028a0`. Its `ledgerly/extract.py` SHA-256 is `15abf578941a8f216ac02e01b444c64f05344543260800674e8ea9382159a432`. Later commits in this contribution add evidence only.

Receipt paths named below (`final-author/`, `final-independent/`, `root-header-review/`, and `la7-recovery/`) are relative to this directory in the **full source/evidence bundle**. A compact review branch may contain only the extractor, focused tests and this guide. Retrieve the complete bundle and receipts through the [existing LA7 journal](https://app.notion.com/p/3f3aedcdf4a581518f79d34897ddac64); those receipt directories are not promised on the compact branch.

The repair keeps each new invoice table's column mapping, preserves unambiguous invoice continuations through prose/blank lines and separator rows, and retains invalid quantities and malformed rows for review instead of allowing incomplete drafts. New unrelated Markdown tables cannot borrow the invoice schema. A Qty/Budget table remains an ambiguous incomplete invoice header and conservatively requires review; this contribution does not weaken that existing diagnostic.

Only `RulesExtractor._table` is changed in production, with dedicated tests in `tests/test_table_boundaries.py`. The composition preserves the total-label owner's `da2e47043d7f18aa231d80b568dd30e31ed8b77c` source, every extraction byte outside `_table`, its `_is_summary_label(desc)` table branch, and all 732 unrelated current-parent leaves and modes. Agent, provider, approval, payment, browser and workflow code is untouched.

## Actual receiving

- Native Python 3.14.4: 36 focused cases and the full suite of **539 tests + 126 subtests**, all passing on the accepted runtime. Raw logs and exact source binding are in `final-author/`.
- Independent actual message → Agent → SandboxMock: **17 cases / 227 checks**, all passing, covering complete drafts, invalid-quantity refusals, blank/prose continuations, truncated-row refusal and separator continuity. No network or send/reminder/payment operation. `final-independent/` retains the unchanged original 125-payload packet, manifest and import verification.
- Root's unchanged independently frozen separator matrix: **256/256** variations pass. Original source passes 256; earlier candidate 020bf7 passes only 81. Exact original, rejected and accepted execution records are in `root-header-review/`.
- Separate receiving reconstructed the accepted source into a fresh LA7 Git repository using only the documented original public prerequisite, with no alternates. Its three unambiguous unrelated-table/prose controls pass 36 checks; the conservative ambiguous-table Agent refusal passes six checks. The original broader four-case expectation is truthfully retained as 47/48 with its no-error assumption rejected. The cross-host packet retains those distinct results.

## Retained failures and scope limits

The original a4c7f05d source drops/misreads reordered later tables. First candidate 1af771e wrongly treated header words inside billable data as a new header. Candidate bf7b95a and composition 88ae6fb dropped continuations after blank/prose boundaries; malformed-row handling also exposed an existing single-table warning-only flaw and a new second-table consequence. Candidate 020bf7 fixed those cases but dropped data around separator lines. All original source snapshots, negative outcomes, corrected receiver assumptions and accepted follow-up receipts remain retained. Earlier passing receipts qualify only their explicitly frozen cases; they are not broad acceptance of rejected candidates.

This is deterministic parsing and in-memory sandbox qualification. It is not a live PayPal or customer operation. No invoice was actually sent, no reminder/payment approval occurred, and no shared service or storage cleanup was performed.

## Publication hold and recovery

Jacob's 19:32 UTC no-new-GitHub-Actions instruction is recorded in the [primary HAMON143 relay](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6067592767). At this native seal, corrected source publication has not occurred. PR50 head updates, new PRs, main pushes/merges and Actions remain held. A separately guarded unique non-main review branch without a PR may carry exact repaired source when its complete trigger audit establishes that it starts no Actions; root records any such later publication separately. Draft PR50 still contains rejected earlier source 72b19a2c and must not be merged. Its three Actions runs were created at19:45:27Z after the quoted instruction but before this lane discovered the relay; all were already complete at the hold check. They do not qualify this final runtime. No workflow was disabled or bypassed.

The qualified source parent is dated da2e4704. Root subsequently observed main c498f55883c755553b59921199d54689d99c9730, an unrelated browser intake/CI change. Future authorized integration must preserve those and any later changes before final-head gates and merge. An unrun required gate is not a pass.

The native home disk reached zero free bytes after the original witness. Only this contributor's isolated checkout was copied into RAM. The final handoff therefore includes an incremental Git bundle containing every native source/evidence revision, with exact prerequisite `a4c7f05d511fb6e9ae4e357d78f696b464625ffc`. The handoff manifest identifies the final evidence-only head/tree and runtime pins. Restore into a fresh repository that has fetched that exact public prerequisite, verify the bundle, fetch its advertised contribution ref, and check out the manifest's final commit. Source-integration independently verifies recovery on LA7. Durable packet custody is recorded in the [existing LA7 journal](https://app.notion.com/p/3f3aedcdf4a581518f79d34897ddac64).
