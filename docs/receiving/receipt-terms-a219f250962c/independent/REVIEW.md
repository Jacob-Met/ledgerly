# Ledgerly receipt-term independent receiving

Disposition: ACCEPT the frozen receipt-term candidate for source integration. No blocking defect was found in the reviewed scope. No reviewer product-source edit was made.

## Exact source

- Candidate: `8a1be8e8163698b88108c01c7fc886f1ca542171`.
- Candidate tree: `2aabfa3b074101b859c674f91be1ef83738f1701`.
- Sole parent and negative control: `b484417baf4e515a0a86cfa13a5983c99293e5f6`.
- Candidate source root: `/dev/shm/ledgerly-receipt-a219f250962c`.
- `ledgerly/agent.py` SHA-256: `cc72f7d3ee10ac42298180f2da6736687e915e1fcbc342c4855aa2bc8aff5949`.
- `ledgerly/paypal.py` SHA-256: `6cacfd8a09dec18a936690965d8177e73f5787d157bfc9670bc9c3ffcebde82f`.

The receiving base already contains the separately reviewed positive-term fallback and current reminder work. This candidate changes only the agent and PayPal module among existing files. Exact source comparison confirms `Agent.approve`, `_refresh_invoice`, `_invalidate_reminders`, `tool_create_invoice`, and `_invoice_facts` are unchanged, as are the browser Python bridge, review adapter, and extractor. The appended state field preserves the old positional field prefix.

## Product boundary and primary contract

An undated receipt term observed on a draft is a pending event, so its current deadline must not come from an older positive-term invoice date. After an explicit local mock send, the actual send date resolves that pending event. A later explicit provider date or `NO_DUE_DATE` replaces the pending state. Present malformed dates and unresolved non-draft receipt terms remain refused without partial cache changes.

The official [PayPal Invoicing v2 schema](https://developer.paypal.com/api/invoicing/v2/schema.json), read on October 8, 2026, distinguishes `DUE_ON_RECEIPT` from a specified payment date. Its `invoice_payment_term` extends the term object with an optional `due_date`. This supports the term-only receipt draft representation. It does not establish when a real recipient receives an invoice; resolving receipt at a successful SandboxMock send remains the author's explicit simulation convention.

## Independent executable challenges

These controls use the real `Demo`, `RulePlanner`, `Agent`, and `SandboxMock` in CPython. They do not import the author's receipt tests. `urllib.request.urlopen` is blocked during the suite. Every invoice/send/reminder effect is confined to the existing in-memory mock.

| Independent group | Candidate outcome |
| --- | --- |
| All three-refresh histories over receipt, no date, explicit receipt date, and positive date | 64 histories, 256 provider refreshes and 64 explicit mock sends; current provider authority always wins while the historical positive draft deadline remains unchanged |
| Mixed ledger | Three delayed invoices retain distinct receipt, positive, and no-date behavior; no same-day receipt reminder; correct next-day receipt reminder, later positive-term reminder, and unchanged cooldown |
| Malformed receipt preflight recovery | Ten malformed date variants leave the entire cached entry, pending action/payload, audit, and approval permits unchanged; restoring the provider response permits one explicit retry and no duplicate reminder |
| Send without follow-up read | RulePlanner and direct-tool entry paths both approve successfully while every potential post-send GET is made to fail; the new code adds no read dependency after the effect |

Final candidate result: four test groups, zero failures, zero errors. The identical independent test file against the exact baseline package produces 40 assertion failures and zero errors. The baseline package was materialized from Git objects and its eight source/fixture hashes are retained in `baseline-source.json`. Twenty-seven all-explicit/no-date histories remain valid on that baseline, while histories containing an unresolved receipt term expose the old refusal or date behavior.

The negative and positive runs use the same unchanged bridge/review/fixture source. The malformed preflight recovery group also passes on the baseline, making it a preservation check for the existing approval boundary rather than a claim of a new repair there.

## Receiving verdict and limits

No blocker remains for the two pinned production source files. The new receipt state stays subordinate to genuine provider dates, supersedes a stale positive fallback when needed, and clears on every valid replacement. The patch leaves approval and reminder execution code unchanged and introduces no post-send read.

This acceptance is for source behavior through the real Python bridge and mock. No browser/Pyodide execution, live PayPal endpoint, actual recipient receipt, provider scheduling, deployed site, or production invoice was tested. Existing in-memory sessions with previously synthesized receipt dates are not migrated. The separately owned positive-date PR and current reminder tree remain integration prerequisites; do not substitute an older main snapshot for the reviewed base.

## Reproduction and evidence

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B check_receipt_receiving.py \
  /dev/shm/ledgerly-receipt-a219f250962c candidate-result.json
```

Use the retained `baseline/` directory as the first argument for the historical control, writing to a separate result file. Its expected suite exit status is one.

- `check_receipt_receiving.py`: independent executable histories and failure/retry controls.
- `candidate-result.json`, `candidate.log`: passing candidate receipt.
- `baseline-result.json`, `baseline.log`, `baseline-source.json`, `baseline/`: exact negative control.
- `source-scope-result.json`: pinned changes and unchanged method/file evidence.
- `SHA256SUMS.json`: reviewer packet hashes.
