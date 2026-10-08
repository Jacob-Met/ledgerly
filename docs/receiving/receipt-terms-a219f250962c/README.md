# Receipt terms follow the approved mock send

Contribution: [Ledgerly issue #16](https://github.com/Jacob-Met/ledgerly/issues/16),
`estate-a219f250962c/workspace_access`. Local receiving base is the independently
accepted PR13 composition `b484417baf4e515a0a86cfa13a5983c99293e5f6`, tree
`ac23b2fa46774f961a20ec105606c436f0f0d5c4`. It preserves canonical reminder main
[`1871942`](https://github.com/Jacob-Met/ledgerly/commit/1871942ecb19aa9756bb36b380795bc6c7bf238d)
and adds the separately owned positive-term deadline fallback.

## Reproduced behavior and correction

The actual `Demo -> RulePlanner -> Agent -> SandboxMock` path created a receipt
invoice on October 1 with a synthetic October 1 deadline. RulePlanner's draft status
read treated that value as an observed provider date. Explicitly sending October 8
therefore left the new invoice seven days overdue; a same-day chase queued a reminder
claiming October 1 was its deadline. The separate reminder approval still prevented
an automatic outgoing reminder.

The correction changes only `ledgerly/agent.py` and `ledgerly/paypal.py` among
existing files:

- The receipt builder emits `DUE_ON_RECEIPT` without an invented absolute date.
- An observed draft receipt term without the `due_date` key has its own appended
  `provider_receipt_pending` state. It remains undated while the invoice is a draft,
  and uses the actual local send date after explicit approval. This state overrides
  an older positive-term fallback when the provider changes a draft to receipt terms.
- The mock materializes an absent receipt date from its successful send timestamp.
  The timestamp is computed once after send validation. An explicitly supplied date
  is preserved.
- Every valid provider presentation replaces the receipt marker. Explicit provider
  dates and confirmed `NO_DUE_DATE` remain the first authority in date selection.

The approval/send implementation, reminder freshness checks, HTTP client, browser
bridge, review adapter, and existing positive-term fallback are unchanged. No extra
post-send read was introduced. Amount serialization and prior-payment language remain
with their existing owners.

## Primary contract and limits

The current [v2 invoice detail definition](https://developer.paypal.com/api/invoicing/v2/definitions/invoice_detail/)
distinguishes receipt terms from a specified date and lists `due_date` as optional.
The [create reference](https://developer.paypal.com/api/invoicing/v2/invoices-create/)
uses that same invoice payment-term shape. The [send reference](https://developer.paypal.com/api/invoicing/v2/invoices-send)
distinguishes immediate sends of current or earlier issue dates from scheduled sends
of future-dated invoices. Sources were read on October 8, 2026.

Resolving receipt at a successful mock send is an explicit simulation convention.
It does not establish when a real recipient receives an invoice. No live provider,
credentials, invoice, payment, message, browser/Pyodide execution, or deployment was
used in this qualification. The actual Python browser bridge ran in CPython.

Only an omitted `due_date` key on a valid `DRAFT` receipt term opens the pending
receipt state. A present malformed value is refused. A non-draft provider receipt
term without a resolved date remains unsupported and is held without replacing
cached facts; the implementation does not invent a date from today, an old positive
term, or an external send for which there is no local evidence. Existing in-memory
sessions containing old synthetic dates are not migrated.

## Native receiving

Python 3.12.14; cached pytest 9.1.1; no dependency or network installation.

| Receiving set | Result |
| --- | --- |
| Final receipt controls against original base package bytes | 11 methods; 14 assertion failures; zero errors |
| Final corrected complete native suite | **119 passed, 28 subtests passed** |
| Added receipt controls within the suite | 11 methods and 26 subtests, all passing |

The final baseline and candidate use the identical test file, SHA-256
`a1b0c4e396b20972a413fe1093063460f66682493e0e95407303f343aa65348e`.
Baseline package files were materialized directly from the receiving base's Git
objects, imported from that isolated path, and source-checked before test discovery.
Bridge, review adapter and fixture bytes are unchanged. `baseline.json` and
`native-final.json` retain source hashes and the actual outcomes; the corresponding
logs retain detailed output. `initial-baseline.*` records the earlier nine-method
challenge before the additional parse/state controls were added.

The controls exercise ordinary extracted and source-bound reviewed receipts across
year, leap-day and non-leap-day boundaries. They verify undated drafts, delayed
approved sends, no same-day reminder, next-day wording and separate reminder
approval, plus refusal of repeat approval. Other cases cover failed and unapproved
sends; explicit provider receipt dates; `NO_DUE_DATE`; positive-to-receipt term
changes; repeated provider term replacement; malformed date values and atomic
refusal; unchanged positional fields; changed-date reminder invalidation; and an
external send with unresolved receipt information. All effects use `SandboxMock`.

Reproduce the complete native suite from the repository root:

```sh
uv run --no-project --offline --with pytest==9.1.1 \
  python -B -m pytest -p no:cacheprovider -q
```

Run only the receipt controls with the standard library:

```sh
python -B -m unittest discover -s tests -p test_receipt_term_receiving.py -v
```

## Frozen production bytes

| File | SHA-256 |
| --- | --- |
| `ledgerly/agent.py` | `cc72f7d3ee10ac42298180f2da6736687e915e1fcbc342c4855aa2bc8aff5949` |
| `ledgerly/paypal.py` | `6cacfd8a09dec18a936690965d8177e73f5787d157bfc9670bc9c3ffcebde82f` |

## Independent receiving

The separate reviewer accepted source `8a1be8e8163698b88108c01c7fc886f1ca542171`,
tree `2aabfa3b074101b859c674f91be1ef83738f1701`. Its four unique test groups pass;
the identical independent controls produce 40 assertion failures and zero errors
on the receiving base. They cover all 64 three-refresh term histories, a mixed
three-invoice ledger and cooldown, ten malformed preflight/retry variants, and
both RulePlanner and direct-tool approval with post-send reads unavailable.

The complete 17-file reviewer packet is preserved byte for byte under `independent/`,
including its eight-file baseline and checksum manifest. See `independent/REVIEW.md`
for the independent source comparison, control counts, reproduction and limits.
No receipt production bytes changed after that acceptance. Canonical publication
composes those bytes on main `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`, preserving
the prior-payment parser and its receiving packet, browser recovery source and
qualification packet, and all prior due-date receiving files. The two files
replaced by this correction still match the reviewed base before replacement.

The author materialized the current native source with the accepted receipt
replacements and verified all 38 file blobs against that composition. The complete
native suite passes **130 tests and 60 subtests**. The author also reran the
unchanged independent review harness on this composition: all four groups pass.
These new observations are retained in `composition-main4bda-native.{json,log}`
and `composition-main4bda-independent.{json,log}`; they do not modify or replace
the reviewer's frozen packet. Merge and deployed browser receiving remain
separate steps.
