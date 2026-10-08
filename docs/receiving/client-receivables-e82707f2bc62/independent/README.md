# Independent client receivables receiving

Receiver: `estate-e82707f2bc62/root`. Contribution: [Ledgerly issue 39](https://github.com/Jacob-Met/ledgerly/issues/39).

The independent protocol, native fixture and five-case Node receiver froze at **2026-10-08 15:28:29 UTC**, before candidate implementation or author candidate tests were opened. The receiver first read the immutable native bridge, `LedgerEntry`, original ledger-export tests and the agreed public projection contract. All 13 supplied baseline source pins were verified.

## Native beneficiary case

Each run executes 18 actual bridge commands through unchanged `Agent`, `RulePlanner` and `SandboxMock`: seven drafts, six explicit approvals, partial and full simulated payments, clock advance and a repeated snapshot read. The authored Clock begins on 2032-02-28 and advances through the native command to 2032-03-01. This crosses a real leap day without relying on the host clock.

Juniper has USD 0.07, USD 0.14, EUR 9.9 and a partially paid USD 50.01 balance; Boreal has JPY 701, a fully paid invoice and an unapproved draft. The board must expose five outstanding invoices in two exact client groups, with independent USD 50.22, EUR 9.9 and JPY 701 totals. Overdue USD is 50.08, due-today USD is 0.14, and the later EUR balance stays separate. Native invoice IDs, names, balances, statuses and dates must remain exact. A second read leaves the snapshot unchanged, all Python source hashes remain exact, and no external call occurs.

Authored projection controls additionally require the exact USD sum `9007199254740993.10000001`, EUR `2.50010`, and JPY `1002`, spanning all four native open statuses. They preserve original balance strings, input fractional scale, literal names, leading-zero invoice references, case/whitespace-distinct billing identities, copied values after input mutation, empty state and undated rows. Thirteen malformed complete snapshots include nonstring/negative/nonfinite balances, invalid leap dates, duplicate identity, missing identity/currency and a malformed excluded paid row. Each must refuse the complete projection without changing its input.

## Actual results and retained corrections

| Received source/test stage | Actual result |
| --- | --- |
| Original b9c24ace baseline and frozen v1 receiver | 1 native control passed; 4 missing-module failures |
| Frozen board c2d4f6bd over original 8a native composition, after native-format correction | 4 passed; 1 exclusion-bucket observer mismatch |
| Same board/native source, one clarified bucket expectation | The affected exact-money/status case passed |
| Same board over current 1ebfaf09 monetary core, final unchanged receiver | **5 passed, 0 failed, 0 skipped** |

The original baseline records EUR `9.9` after extracting the draft text `9.90`. Before opening the candidate, two expected total strings were corrected to retain that actual snapshot scale; the original fixture and its amount text were not changed. The subsequent candidate failure was the receiver's assumption that a zero open invoice would be counted under `SENT`. The source contract uses the exclusion reason `ZERO_BALANCE`, rendered as “zero balance”; non-open rows retain their actual status. Only that expected key changed. Reversing each narrow edit reproduces its predecessor byte for byte. Original protocol, tests, failed logs and corrections remain in the archive; production code was unchanged.

Current main integrated invoice-value validation during receiving. The current-core replay therefore used a separate exact `1ebfaf093b4d992799901efec0ab05957be35eb1` composition, retaining the original baseline and earlier candidate untouched. The final full five-case run passed on Node **24.19.0** and Python **3.12.14**, with feature module blob `c2d4f6bd9206d7199fe053bd45e2e8df2ad96ad9` unchanged. This complete current run is separately recorded; it does not relabel earlier failures.

## Source review and remaining gates

The receiver read the complete projection/controller/CSS, additive main hooks, HTML and balance guide. Removing exactly five receivables lines from the current main module reconstructs its prior blob `ed7cb86a2ff4e5ac4b7d5a140b5db208633ec3a7`. Integer-based bounded decimal addition, exact identity, canonical calendar dates, complete admission, literal escaping and visible-state clearing were accepted. Existing invoice, approval and provider behavior stays with its native owners.

The complete real-Chrome receiver and separate workflow were also source-reviewed. They operate the built Pyodide page and real Worker replies, exercise keyboard filters and a 390px layout, and explicitly label authored reply holds, malformed copied replies and terminal errors. They preserve native snapshots, source/build hashes and actual PNGs. Source review is not browser execution or visual inspection. Existing full native/npm CI and this new actual Chrome gate must still qualify the final publication composition before integration. Tested synthetic and actual merge commits must be recorded separately.

`protocol.json` retains the original independent protocol. `receiving.json` contains exact stages, hashes and qualification boundaries. `peer-evidence.zip` preserves every original/final test, run log, case response, native source capsule, correction and source-review receipt with a member manifest. Every compressed member was read back and compared byte for byte. The portable active tests belong together under `web-demo/tests/`; the new workflow runs them using actual Python and Node type stripping. No browser, installed application, real-customer, external PayPal or demonstrated-benefit claim is made by the local native packet.
