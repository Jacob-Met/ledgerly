# Sandbox payment admission and atomic application

This packet supports Ledgerly issue #29. An invalid sandbox payment could previously enter the transaction list, change balances, or leave a NaN invoice that an ordinary later payment could not repair. The browser bridge also treated explicit JSON zero and false as an omitted amount, paying the full remaining balance.

The production change is confined to the decimal import and `SandboxMock._apply_payment` in `ledgerly/paypal.py`, plus one expression in the bridge's payment arm. The dedicated native regression lives at `tests/test_sandbox_payment_admission.py`.

## Resulting behavior

A submitted amount must be finite, greater than zero, and exactly representable under the existing currency rule. A fractional-cent GBP amount and a fractional JPY amount are refused; equivalent values with trailing zeros remain valid. Absent, null, or empty-string bridge amounts keep their existing full-balance meaning. Explicit zero, false, arrays, and objects cannot become full-balance payments through truthiness normalization.

After admission, the mock stages the transaction and recalculates a detached invoice. It commits the changed payments, amount, due amount, and status only after calculation succeeds. A refusal or calculation failure leaves the retained invoice and previous invocation state available for an ordinary retry on the same mock instance.

The existing invoice-total rounding remains unchanged. In particular, 1.5 hours at GBP0.01 produces the existing GBP0.02 invoice, which accepts a GBP0.01 partial payment and completion. Overpayment policy and explicit approval boundaries are unchanged.

This is pre-commit admission and calculation staging. If payment commits successfully and a later webhook/current-invoice read fails, the committed payment remains; the original event can be explicitly replayed. This patch does not promise rollback of that later workflow.

## Qualified subjects

| Subject | Source identity | Recorded result |
|---|---|---|
| Original source before webhook composition | `f044ee3c5f77ab062d51684d8718f888e48540b2` | Original negative, zero, fractional-cent, and NaN witnesses retained |
| Current webhook composition before repair | `5493205cd69a32be75ed2f7dfc669b122efe5563` | Invalid payment defects and bridge zero/false full-payment behavior retained |
| Rejected V1 | `v1/source-freeze-v1.json` | Author tests passed after correcting five numerical assertions; independent fractional-quantity controls exposed a real regression |
| Approved V2 on PR30 | Base `2d3a90a9aa794d849ec54ca9d32a720959ddc5db`; source manifest `0c0576bacea4c05d662157d1fd8e3dcf5594a03b56cec792bac2ceefc85ee816` | Full native suite: 197 tests and 96 subtests passed in each of normal and optimized CPython; independent two-method receiving also passed in each mode |
| Final composition with PR33 invoice details | Base `2ab89fdd65d200355dda381ba7bae82a22e268fc`; source manifest `b92bc2abbbd0b5d8c8f00eb057f88f6b88a6b9a9b77a28dab636fa907e18d428` | Existing 12 payment methods and eight invoice-details methods passed in each mode; 37 source hashes unchanged and zero network/provider attempts |

V1 used a blanket decimal Inexact trap around the existing invoice recalculation. Independent receiving showed that this rejected legitimate rounded invoice totals. V2 removes that broad trap while preserving strict submitted-amount admission and staging. The original failed V1 remains in this packet; its historical pass results are not an approval.

The final composition preserves PR33's invoice-details import and additive snapshot field, its helper and test, and PR30's chase budget. PayPal and the new payment test retain their exact approved V2 bytes. All other current repository leaves are preserved by the publication tree; `publication-manifest.json` inventories the contribution.

## Evidence and replay

- `baseline/` retains original and webhook-composed receipts, their probes and source pins. The standalone zero-transport observation was captured from an inline command; no separate historical script is claimed.
- `v1/` retains the initial test-assertion correction, corrected regression, full original failures, and rejected intermediate native receipts.
- `v2/` retains the approved source freeze, native command controller, complete logs, and production patch.
- `independent/` is the exact 27-payload reviewer packet plus its original manifest. Manifest SHA256 is `dac61e7b4b568f8d010048bd0bf79a916c62c14545882d7e9cdcac470c3bd77a`. Its approval is bounded to the exact V2 source; it is not silently relabeled as a review of the later composition.
- `composition/` records the PR33 peer delta, exact current source freeze, focused native run, and final source/test patch.

The recorded runtime was CPython 3.12.14. The core package has no third-party runtime dependencies; the broader author suite used the existing pytest 9.1.1 environment. The optimized pytest run retains its standard assertion warning. The dedicated payment, independent, and composition methods use unittest assertions that remain active with `-O`.

From this PR checkout, the focused composition can be reproduced without pytest:

```sh
python -B docs/receiving/sandbox-payments-20261008-3dab/composition/run_native_composition.py . docs/receiving/sandbox-payments-20261008-3dab/composition/source-freeze-pr33.json
python -B -O docs/receiving/sandbox-payments-20261008-3dab/composition/run_native_composition.py . docs/receiving/sandbox-payments-20261008-3dab/composition/source-freeze-pr33.json
```

The runner verifies the pinned source before and after execution and blocks network/provider entry points. Historical controllers retain their original workspace paths; their receipts and immutable source identities are preserved unchanged.

A temporary capacity failure prevented writing the composition runner locally. The zero-byte, unexecuted owner file was removed after verification; the final exact runner text was compiled in memory, and its stdout/stderr were retained verbatim for publication. No frozen source, prior evidence, other-owner data, or existing test environment was removed.

These results cover authored, in-memory SandboxMock fixtures. Hosted CI and browser/WASM receiving of this final composition remain integration gates. No real invoice, payment, account, or sending operation occurred.
