# Independent receiving: invoice-send freshness

Reviewer: research_integration, a separate contributor from runtime_execution under the same estate account.
Repository: Jacob-Met/ledgerly. Scope: issue #32.
Disposition: **PASS for the final source and the three explicit test adapters**, subject to publication and actual tested merge-tree gates.

## Exact source and negative evidence

| Role | SHA-256 |
|---|---|
| Original agent | `1547047380e848e2527374cf0f0c381d4ef1155e04d729bd9af74e1e8dd14c05` |
| First freshness candidate | `f2bc79188eb9b4933f969ba3c6a08397fec5b6b3f4678add22c396fb5d0584eb` |
| Accepted status-aware successor | `969b6f62ed0958705b3041831cfc0624951cd49893419f3ac2b1d5232d56dd97` |
| Unchanged independent public probe | `cb4465f43a4a3ec9f9281208d83c459bd8a2a999847937a154f355bb1856dd85` |
| Current b9c native provider source | `c5e5df0a9286ae212b8e45111ea95db835e32b9eeb040338876d4ab620e7dace` |

The final agent is Git blob `5c4eb0ad5ae81a15ffd45f29f9d48e737f3499ea`.
The source successor adds the existing native `STATUSES` import and membership check to the first candidate's read guard. All other first-candidate source bytes remain unchanged. Its original outgoing permit, response-failure handling, audit and approval-consumption code remains intact.

The author identified a remaining status-classification concern while review was in progress. This separate probe independently reproduced three different unusable status strings: lowercase `draft`, a tab, and `FUTURE_PROVIDER_STATE`. First candidate f2bc consumed those reviews as REJECTED even though the read did not establish a known provider state. The successor leaves them pending and permits an explicit retry after a usable read. An empty status is retained as a refusal control; known REFUNDED still rejects before any POST.

## Independent native behavior

The probe uses the actual public Agent, Extractor protocol, native Extraction/LineItem types, and SandboxMock. No production method is replaced. Provider method wrappers return authored read variations or lose an acknowledgment around the actual native mock operation. All invoices and addresses are synthetic.

Seven methods contain fifteen authored cases:

- Seller identity, line order and partial-payment permission remain reviewed invoice content.
- A failed JSON read leaves the original review, complete cached ledger and audit unchanged. A later changed draft is rejected, while a separate healthy invoice can still be approved.
- Equivalent decimal/scientific notation, fractional quantities, and USD/JPY representations preserve ordinary sends. Zero refund/gratuity response facts are tolerated.
- Nonzero paid, refund and gratuity aggregates cannot disappear as bookkeeping metadata.
- The same JSONDecodeError has different outcomes at the two relevant boundaries: a GET failure leaves PENDING; response loss after an actual mock send consumes the ID as FAILED/UNKNOWN, preserves its audit, and cannot replay.
- Unusable status strings remain retryable read failures; a known refunded invoice is refused before sending.

| Exact replay | Result |
|---|---|
| Original 154704 source | 11 failed cases, 1 native-domain error, 3 passing controls |
| First f2bc candidate | 3 status cases fail; the other 12 cases pass |
| 969b successor with matching prior native dependencies | All 7 methods / 15 cases pass |
| 969b with current b9c native dependencies | All 7 methods / 15 cases pass |
| Same current-source probe under optimized Python | All 7 methods / 15 cases pass |

There are no skips. The original domain error is the real mock refusing the attempted POST to a refunded invoice, rather than a harness/import error. Complete original source capsules, raw logs and native request/action/ledger/provider/audit reports are retained. The reports are preserved byte-for-byte, including the before-repair failures.

The current-native receiving source is main `b9c24ace6b57a17215a53c50b674bd187d13f8ed`, provider blob `a1da2ebff1ec2963ab94ca094300c8f5b42aa704`, with unchanged current initializer and extractor. Python is 3.12.14 on Linux. This does not claim a live provider transaction or atomic remote GET/POST behavior.

## Exact test-adapter receiving

The reviewer inspected all original and adapted bytes:

- `test_approval_outcomes.py`, blob `f4c7abe598388131fd207b935e87a8bf3ca68024` to `f01f9fadb168543bab230a20175c9b90224ce25a`: the provider now changes to CANCELLED after a verified DRAFT read and before the real outgoing mock operation. The test retains its original error-body identity, failure audit and consumed-ID assertions, and explicitly requires one POST.
- `test_receipt_term_receiving.py`, blob `fb5d293f3944480b86524eb98c8ee19a7ce53174` to `35f9c1fdf330fd32e374968d2bd7b9670036be9d`: three stale-review fixture paths first prove rejection, unchanged review/cache and no send, then explicitly simulate an external mock send and perform the native refresh. All original due-date assertions remain. Ordinary raw/reviewed workflows still use Agent-approved sends.
- `test_browser_invoice_details.py`, blob `4fc4c0b5e110a3a3eebee4791846195c539088c2` to `c861ef775517ac7561e01596aa50ba3c74a24b6d`: the added call is checked as the exact GET followed by POST, not only a looser total. Original invoice-detail, recipient/item, no-external-call and other consumer assertions remain intact.

These adaptations match the newly explicit freshness contract. They do not conceal a native implementation change or substitute a fake outgoing success.

## Source-preservation receiving

The reviewer independently fetched authoritative base tree `0f457eb8ded2b462bd1be4d335c3a257cd19c630` (604 leaves) and authored successor tree `77f215cc55f817679ad8183e602133616c9ba820` (613 leaves). Exactly 599 existing leaves are unchanged. The five modifications are the agent, README and the three explicit test adapters. There are nine additive source/evidence leaves and no deletions. Current PayPal, bridge, browser, staging, worker, extractor and other native implementation bytes are preserved.

This acceptance binds that exact authored tree before this independent packet is added. The final published head and GitHub's actual tested merge tree require their own fresh source/parent/check readback. The author reports the full current-native suite at 245 passed plus 96 subtests; this receipt's independent execution is the fifteen-case probe and does not relabel the author's suite as an independent rerun.

## Reproduction and custody

The archive member manifest binds each original byte sequence. Start from the contained `f2bc/ledgerly` native capsule, replace only `agent.py` with `successor/ledgerly/agent.py`, and for current-native reproduction also replace `paypal.py` with `current-b9c/ledgerly/paypal.py`. Set `LEDGERLY_REVIEW_SOURCE_ROOT` to the resulting parent directory and run `python3 -B test_send_receiving.py` (or add `-O`). Set `LEDGERLY_REVIEW_REPORT` to retain full public-operation reports.

Shared storage filled during review. The three final replays used private per-exec tmpfs directories; their complete original output was captured into memory before those directories ended. The compact lossless Git packet, including all decompressed reports and source pins, supplies durable custody. No other worker's source path, provider account or runtime was modified.
