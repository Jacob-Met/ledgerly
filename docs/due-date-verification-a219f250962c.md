# Preserve invoice deadlines through delayed approval

Receiving base: [`main@dc5e188c062bb7b45a8ddbbd23a3da75126e17a8`](https://github.com/Jacob-Met/ledgerly/tree/dc5e188c062bb7b45a8ddbbd23a3da75126e17a8).
Verified locally on October 8, 2026, with Python 3.12.14 and pytest 9.1.1.

## Product behavior

`build_invoice()` already serializes a positive payment term's deadline relative to the
invoice date. Previously, `LedgerEntry.due_on` discarded that deadline and derived a
different date from the later send approval. This also postponed the overdue scan and
changed the date used in reminder wording.

For an October 1 draft with Net 12, the existing builder produces
`DUE_ON_DATE_SPECIFIED` and `due_date: "2026-10-13"`. Explicit approval on October 8
must not move that specified date to October 20.

| Receiving step | Canonical implementation | This correction |
| --- | --- | --- |
| Draft on October 1 | Invoice deadline October 13 | Invoice deadline October 13 |
| Approve send on October 8 | Ledger deadline October 20 | Ledger deadline October 13 |
| Scan on October 14 | No overdue invoice | One invoice, one day overdue |
| Draft reminder | No reminder queued | October 13 reminder queued for approval |
| Automatic reminder sends | 0 | 0 |

The new optional `invoice_due_on` fact comes from the exact serialized draft, before
the draft request. Positive-duration terms use it after sending. `sent_on` still
records the actual approval/send date. Zero-day terms remain due on that send date;
missing terms remain undated. Unsent entries retain their existing `due_on=None`
behavior. Directly constructed older entries retain their send-date fallback, and the
new field is appended to preserve the existing positional constructor.

PayPal's [primary invoice schema](https://developer.paypal.com/api/invoicing/v2/schema.json)
defines a specified-date term by the date written on the invoice, distinguishes
receipt terms, and describes `due_date` as the payment deadline. Its send operation
sends an invoice with a current or past issue date immediately. These documented
distinctions support retaining the positive-term date without backdating receipt terms.
The provider builder's existing assumption about submitting both a term type and date
remains unqualified against a live API; this change does not establish provider
compatibility.

## Native verification

Run from the repository root:

```sh
python -B -m pytest -p no:cacheprovider -q
```

The available local cached runner was:

```sh
uv run --no-project --offline --with pytest==9.1.1 \
  python -B -m pytest -p no:cacheprovider -q
```

| Source and controls | Result |
| --- | --- |
| Original canonical `d4d3802`, original suite | 52 passed |
| Original canonical `d4d3802`, new date test file copied byte for byte | 8 failed, 4 passed |
| Current canonical `dc5e188` plus correction, full suite | 64 passed |

The added controls exercise the actual `Agent.tool_create_invoice → approve` path.
They cover Net 15, specified-date Net 12, month/year/leap-year boundaries, same-day
approval, approval after the deadline, the overdue-day boundary, reminder wording and
its separate approval gate, receipt and missing terms, and legacy construction.
The negative control was independently repeated against source files materialized
from canonical Git objects in a temporary directory. Canonical then advanced to
`dc5e188` when the invoice-review interface landed. Its core, original native tests,
and fixtures are unchanged. The candidate was rebased onto that exact commit and
the full native suite was run again.

At 08:42:29 UTC, independent receiving also executed the current Python browser
bridge and its newly landed review adapter against canonical and candidate source
loaded directly into separate Python module instances. Both the ordinary draft route
and a source-bound reviewed correction from Net 15 to Net 12 reproduced the table
above. Due-on-receipt corrections retained the actual send date. Every scenario kept
the unauthorized send blocked,
exactly one explicitly approved mock invoice send, zero automatic reminder sends, and
zero external calls. This is execution of the real bridge in CPython; it does not claim
an additional browser/Pyodide or deployment qualification.

## Composition with active contributions

[Issue #7](https://github.com/Jacob-Met/ledgerly/issues/7) owns amount/currency
validation earlier in `tool_create_invoice`. Preserve that validation when combining
the ledger-construction change.

[Issue #8](https://github.com/Jacob-Met/ledgerly/issues/8) owns reminder freshness and
observed provider reconciliation. Its inspected candidate already gives a confirmed
`provider_due_on` precedence over inferred terms. Preserve that provider override
ahead of this draft-date fallback; retain its ability to confirm that an invoice has
no deadline. Append `invoice_due_on` after its existing fields when combining the
dataclass so those positional fields do not move.

That candidate's status refresh already fixes positive-term dates on the current
browser `RulePlanner` route, which reads status after drafting. This contribution's
additional value is the native tool/Planner contract: a valid planner can create its
draft and finish without an optional status read. The independent receiving control
used exactly that planner and observed the following on October 14:

| Implementation | Date after October 8 approval | Queued reminders |
| --- | --- | --- |
| Canonical | October 20 | 0 |
| Inspected #8 candidate alone | October 20 | 0 |
| This correction on canonical | October 13 | 1 |

The inspected #8 source was a local, read-only snapshot with SHA-256
`d59821b88b140edd0e0d2f826006651257cd1e2023d0b0e98d977679094e82e8`.
This is a composition finding, not a claim that those independent changes have been
integrated. The source patch changes only date facts and their selection; existing
approval, provider, reminder, webhook, and browser implementations remain owned by
their existing contributors.

## Source identities

- Corrected `ledgerly/agent.py` SHA-256:
  `24b04881943c6649ccb0f5ba5be2eab582f08253cadf1c79928b1640f3ec024e`
- New `tests/test_due_date_receiving.py` SHA-256:
  `e76ed73a6a429c064a4baee811cf72bfe31d6ff3803fdff3a8ab2d34f590e4ff`
- Unchanged browser bridge SHA-256:
  `3e589806d38909801fd4307bf54b9f1f28d3ba7c653d158122e7f18302779eda`
- Unchanged review adapter SHA-256:
  `08e07817db8d106d3e3c3b281082845a46987e66b1e275d2183c9d5d81a37447`
- Unchanged hourly fixture SHA-256:
  `e48dcc2f587e8978b1a97008c7e3fec7a7a489f7ef7571dc3c95d8b8e8036902`
