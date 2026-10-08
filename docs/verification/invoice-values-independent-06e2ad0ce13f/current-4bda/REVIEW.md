# Focused independent receiving: exact values with current payment evidence and deadlines

## Decision

Accepted the supplied extraction tuple on main `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`. The unchanged owner payment-language and deadline tests, together with the original 31 independent value cases, pass **56 tests plus 32 subtests**. Eleven focused confirmation/value/deadline probes also pass. No production-source correction is requested.

| Accepted file | Git blob | SHA-256 |
| --- | --- | --- |
| `ledgerly/agent.py` | `1af73175465d737beb88a2100f637a1437a5dd47` | `d029d1be3f93f3c38ce5fdd54d7e7468e9ac6a964f7fe63c1bed50f5b139c4b6` |
| `ledgerly/extract.py` | `100e581d3ef0d99555f49264859d01b535c6094f` | `4921f5df19cb35089afc8db3641cae9b8fbd089279dd84ef9555c10b759e2f16` |
| `ledgerly/paypal.py` | `43554a287c3b94b48e5376d9fa10f9287e1bea3f` | `61e86702ffd72eeadb680fb5bddb3e8498427852a9130b064ec7a63ce9ac4dfe` |

Exact accepted source copies are under `source/`. After acceptance, the author committed the identical tuple as `22b7b5404e0bde8c6796d3abd8c5d177b5e84e1f`, tree `d99d61a6f1ae39e8c9a1fc572bbd0a037c47522e`; all three committed blobs were verified. This receipt is separate from the earlier component and main-187 composition receipts.

## Conflict resolution and owner preservation

The author merged current main into the accepted extraction work. There was one extractor conflict: current main requires a complete, unambiguous statement that a payment was received, while the extraction work collects each payment's currency and validates its precision. The resolution keeps the owner's single-money-token and full-statement confirmation condition, then runs the existing per-payment collection and value checks inside that confirmed branch. Uncertain statements retain the owner's error branch and do not enter the collection.

Independent source comparison establishes that `_PAID_RE`, `_PAYMENT_KIND`, `_PAYMENT_AMOUNT` and `_PAID_CONFIRMED_RE` are exact copies of main. The confirmation condition and uncertain-statement branch are AST-identical to main. The complete `LedgerEntry` class is source-identical to main, as are the retained `invoice_due_on` assignment and ledger-entry construction. Every `Agent` method except the intended admission change in `tool_create_invoice` is source-identical to main.

The working-file freeze was copied and hashed while the merge was pending. The author had resolved the source text but had not yet staged that conflict. This is acceptance of the exact source tuple; it does not claim that this merge was conflict-free or invent an author commit. `resolved-extractor-conflict.diff` and `source-and-owner-proof.json` preserve the observation and proof. The reviewer made no production changes.

## Unchanged test comparison

The two owner test files and `conftest.py` were verified byte-identical to current main. The original three reviewer files were copied unchanged from their already-frozen 31-case suite. Both source versions were executed in separate snapshots with the same test bytes.

| Identical focused test collection | Passed | Failed | Subtests passed |
| --- | ---: | ---: | ---: |
| Exact main `4bdaaa9` | 34 | 22 | 32 |
| Accepted current-main extraction tuple | 56 | 0 | 32 |

Raw output is in `main-focused-owner-and-values.log` and `candidate-focused-owner-and-values.log`; `focused-runs.json` records commands, UTC times and hashes. The collection includes all current owner payment-language and deadline tests plus all original 31 value cases. It exercises negated, requested, conditional, quoted, unsettled and supported payment statements; review without recording an uncertain payment; fixed positive-term draft deadlines, date boundaries, due-on-receipt and no-date behavior; and current provider-date precedence.

## Focused confirmation/value interaction

`confirmed-payment-probe.py` adds eleven bounded receiving cases without changing the project test suite. Each invalid or uncertain case checks both extraction and the real agent path, requiring review with no number request, draft, ledger row or pending approval.

Confirmed statements with malformed grouping, a malformed numeric tail, a foreign currency, subunit precision, two individually invalid subunit amounts, or a negative amount are all held before requests. Future, negated, conditional and refunded-payment statements keep `amount_paid` at zero and require review. The valid control queues a confirmed USD 25 deposit, retains the October 13 deadline when approved on October 8, and records one exact payment through explicit approval, leaving a USD 75 balance.

All **11 probes pass** on the candidate. Exact current main passes 10 and fails the confirmed foreign-currency case, demonstrating the remaining value-admission defect repaired by this composition. `candidate-confirmation-probe.json`, `main-confirmation-probe.json` and `confirmation-runs.json` retain complete observations and the probe hash.

## Runtime and boundary

Receiving used Python 3.12.14 and pytest 9.1.1, with bytecode and pytest-cache writes disabled. Snapshot inputs remained unchanged around each focused run, and the three author source files were rechecked after receiving. All payment and send exercise used the existing offline `SandboxMock`; no provider HTTP client was activated.

The full native and Pyodide combination with the current webhook component is a separate next receipt. This packet makes no claim about that future combined tuple. Publication and merge remain with the execution owners.

Copy this evidence directory unchanged into the repository. `receiving.json` is the machine-readable decision; `artifact-sha256.json` covers packet files relative to repository root, excluding the manifest itself.
