# Independent Ledgerly payment receiving — approved V2

**Disposition: APPROVE the exact V2 source below for the bounded sandbox payment-admission repair.** V1 contained a real regression found in this review and remains preserved as a failing intermediate.

## Source and boundary

Current receiving base is `2d3a90a9aa794d849ec54ca9d32a720959ddc5db`, tree `cb1877320fc40166cc7f10c035d5e7866be53713`. The baseline includes PR30's overdue-scan change. The reviewed delta changes only the decimal import and `SandboxMock._apply_payment` in PayPal, one amount-normalization expression in the bridge payment arm, and the owner's dedicated test file.

| Input | SHA256 |
|---|---|
| V2 owner freeze | `0c0576bacea4c05d662157d1fd8e3dcf5594a03b56cec792bac2ceefc85ee816` |
| V2 `ledgerly/paypal.py` | `c5e5df0a9286ae212b8e45111ea95db835e32b9eeb040338876d4ab620e7dace` |
| V2 `web-demo/python/bridge.py` | `bd810828b71069004866d1db341a44d230acdcad551ef068f88901f7210ab315` |
| V2 owner test | `7f971cc281485417f83eed9f48db55b420b06287aee4966092252f61b489cedf` |
| Unchanged independent probe | `606d3ae4818854aac0b7529f291942f684fb3e9d0073f97efeee1ffbd3b638e7` |

All 34 captured baseline and 35 candidate inputs matched SHA256 and Git blob identities before and after V2 execution. The 32 captured existing files outside the two production changes were unchanged, including Agent/webhook code, extractor/invoice code, review/approval code and PR30's native overdue-scan test. The bridge chase arm is unchanged from the actual receiving base. Whole-repository preservation and hosted CI remain publication gates.

## Distinct receiving and the repaired regression

The two independently authored methods use the real `bridge.handle_json` → `Demo.dispatch` → `SandboxMock` → Agent path, fictional invoice text and explicit approval of the queued mock send.

1. **Normal invoice rounding remains payable.** Authored quantities 1.5 and 1.3 at GBP0.01 produce the existing rounded totals GBP0.02 and GBP0.01. Exact-cent payment, partial completion where applicable, and duplicate event replay must succeed. V1's blanket `Inexact` trap rejected both valid cases while the original baseline accepted them. V2 removes that broad trap while retaining exact submitted-amount admission and staged invoice recalculation.
2. **Repeated refusal does not poison a live invoice.** One invoice starts with a GBP12.34 partial payment. Numeric zero, false, NaN text, a negative cent amount, a fractional-cent amount and negative numeric zero are each refused. Every refusal preserves the full retained invoice, Agent export, prior event and mock-request count. Each is followed by duplicate replay and a successful GBP1.23 retry on the same invoice. Final full-balance settlement reaches GBP800.00 with exactly eight transactions. Replaying the original partial event remains a duplicate and does not regress the settled invoice.

| Subject | Actual result |
|---|---|
| Original baseline, normal Python | Rounding method passes; sequence method fails because numeric zero pays the remaining balance |
| Candidate V1, normal Python | Sequence method passes; rounding method has two failed subcases |
| Candidate V2, normal Python | 2 methods pass; 0 failures, errors or skips |
| Candidate V2, optimized Python | 2 methods pass; 0 failures, errors or skips |

Both final processes used existing CPython **3.12.14**, set `LEDGERLY_ALLOW_NETWORK=0`, blocked HTTP-client construction and network entry points, and recorded zero network attempts. Standard unittest assertions remain active under `-O`. The author's wider native suite was not repeated.

Final normal receipt SHA256: `b5194ec3798fcdc7763acc5e465748e435c8cea7a18d70b7f5bb547feacb5976`.

Final optimized receipt SHA256: `1e8e60e31d648e87b152e6bc82f4f384330d27bbee9b71f21832452249152ba0`.

Controller/69-input guard receipt SHA256: `69f30e55c8dae85ae2211558ad0312ebde3eb2a5da792ab8211438814b51af02`.

## Evidence and practical limits

The packet preserves the original standalone observation, raw baseline/V1 failures, V1 reconstruction patch, unchanged regression probe, final native logs and receipts, both owner manifests, and source guards. Historical `V1_FINDING.md` describes the earlier request for change; this disposition supersedes it for the exact V2 source only.

A private, unexecuted V2 duplicate copy hit ENOSPC. Only that incomplete reviewer-owned duplicate was removed after each member was checked against the original bytes or a truncated prefix. The incident receipt is retained. Final V2 execution read the owner's immutable candidate directly with `-B` and in-memory fixtures; before/after guards confirm no source mutation.

This review qualifies pre-commit payment refusal and calculation staging in the actual CPython bridge. It preserves existing invoice rounding, overpayment policy, approval boundaries and post-commit webhook/replay behavior. It does not claim atomic rollback after a payment has committed and a later webhook read fails, nor a new browser/WASM execution, hosted CI result or deployment. No real invoice, payment, account or sending action occurred.
