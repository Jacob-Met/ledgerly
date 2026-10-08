# Independent receiving: webhook admission on the merged reminder owner

## Decision and source boundary

Accepted the frozen webhook source and the two explicitly reviewed test-contract updates described below. The unchanged independent suite passes **26/26 cases**, and final native composition passes **132 tests plus 2 subtests**, with no failures. All 28 native inputs and the reviewer test were hash-identical before and after the final run. No production-source correction is requested by this review.

Baseline is current main commit `1871942ecb19aa9756bb36b380795bc6c7bf238d`, including the merged reminder freshness and provider-presentation behavior. This review concerns the narrow webhook addition on that main, not the earlier overlapping current-invoice candidate.

| Source | Git blob | SHA-256 |
| --- | --- | --- |
| Main `ledgerly/agent.py` | `19f261b1430769952057697d68472722a11cf643` | `d59821b88b140edd0e0d2f826006651257cd1e2023d0b0e98d977679094e82e8` |
| Candidate `ledgerly/agent.py` | `2dbf14c2eeeada3b1f26befa1039064500394c65` | `e8a60aa83a9647663da1c0cf52824e26a9af6c8ede0b25134db1f156e5164091` |

Only the `hashlib` import, the seen-event index in `Agent.__init__`, and `Agent.handle_webhook` change. Exact source-text comparison confirms all 18 other `Agent` methods are unchanged. In particular, `_refresh_invoice`, `_invoice_presentation`, `_invoice_facts`, `_reminder_facts`, `_invalidate_reminders`, `tool_send_reminder` and `approve` are the owner's merged methods. `accepted-agent.diff`, `source-pins.json` and `unchanged-owner-methods.json` preserve this boundary.

## Behavior received

A new supported notification for a locally known invoice invokes the existing current-invoice refresh before its event identity is consumed. The reported snapshot remains useful as event metadata; it cannot overwrite the current invoice presentation or restore a stale balance. If the read fails or its presentation is invalid, the event remains retryable and cached facts and reviewed actions remain unchanged. A notification for an unknown local invoice does not perform the provider read or consume the identity.

Accepted event IDs bind to canonical JSON content. Whitespace and object-key ordering can differ on a duplicate without producing a second read or state mutation; changed content under the same accepted ID is refused before invoice effects. Canonical identity validation and nonfinite JSON rejection precede current-state reads. When a verifier is configured, signature verification remains before duplicate handling; this ordering was exercised with the native mock signer and verifier.

The addon uses the owner's provider-presentation and reminder rules directly. Legitimate current edits to currency, total, invoice number, recipient and due date update the notified invoice and invalidate its obsolete reminder. A future due date or `NO_DUE_DATE` cannot be replaced by the old webhook's due date. An unrelated invoice and its pending review remain unchanged. The owner's next-day review invalidation is retained. A delayed event whose current read still matches an already-reviewed GBP 500 reminder preserves its exact text and pending approval; only the explicit human approval sends that text, once.

## Independent evidence

The reviewer read the main code, candidate diff and existing owner reminder tests before authoring the receiving cases. The author's new `tests/test_webhook_admission.py` was not read during independent test design. The tests are independently authored, although this is not a blind source review. No production source was edited by the reviewer.

The candidate package was copied from the exact frozen author files before independent test design. The baseline package was materialized from the exact main commit. All source copies and the single reviewer test file were hash-checked; no source reconstruction or substitution was used.

| Identical independent suite | Passed | Failed | Raw log |
| --- | ---: | ---: | --- |
| Main `1871942ecb19aa9756bb36b380795bc6c7bf238d` | 3 | 23 | `baseline-independent.log` |
| Candidate `2dbf14c2eeeada3b1f26befa1039064500394c65` | 26 | 0 | `candidate-r1-independent.log` |

The reviewer test is `tests/test_webhook_current_read_receiving.py`, SHA-256 `c76348a1b6abd856c0149fba5bd67155c081bf8142c2ad2d016ca9280e15ac7d`.

Its cases cover current full-payment precedence over an old partial snapshot; preservation and one-shot approval of a current reviewed balance; coherent provider edits and invoice locality; outage, wrong-invoice, missing-due, nonfinite and inconsistent-balance reads with successful same-ID retries; unknown-local retry; reencoded duplicates; accepted-ID conflicts in invoice identity, payment content and envelope time; signature verification on duplicates; invalid event and invoice identities; nonfinite JSON metadata; and the owner's review-date invalidation.

All exercise uses the existing offline `SandboxMock`. Payer simulation changes only that mock's current invoice. Successful send operations occur solely through explicit approval calls inside positive controls; webhook delivery itself must not issue `/send`, `/remind` or `/payments`. Denied direct reminder attempts verify the gate remains closed. No HTTP client or external service was activated.

## Two existing expectations required a reasoned contract update

Before any expectation edit, the reviewer independently ran the full owner, author and reviewer tests against the frozen source. The result was **130 passed, 2 failed, plus 2 passed subtests**. All 28 native input files were unchanged before and after this run. The two failures match the author report exactly; the original test files and raw failure log are retained.

| Existing test | Observed failure | Receiving judgment |
| --- | --- | --- |
| `test_unchanged_browser_bridge_cancels_stale_partial_payment_reminder` | Exported balance was `"500"`, while the assertion required `"500.00"`. | The unchanged owner refresh canonicalizes monetary values to the same numeric presentation already used by its status and reminder paths. The intended stale-reminder workflow should compare the exact monetary value and preserve its approval and dispatch checks. |
| `test_delayed_old_payment_event_cannot_restore_obsolete_balance_draft` | The explicit human approval sent the reviewed GBP 500 message, while the old test required no send and a new draft. | The old expectation depended on first regressing to the delayed GBP 700 snapshot and invalidating the still-current review. Current refresh observes GBP 500 throughout. The correct assertion preserves the original pending ID and payload, confirms no webhook dispatch, then proves explicit approval sends the exact reviewed message once. |

These are observable behavior changes caused by the intended move to current invoice truth. They are not silently excluded or reported as preexisting failures. `original-test_reminder_freshness.py`, `original-test_reminder_receiving.py`, `candidate-original-contract-composition.log`, `original-contract-run.json` and `original-native-input-sha256.json` retain the exact evidence before adjustment.

The final diffs were inspected independently: the bridge test now compares `Decimal` values while retaining its complete approval workflow; the delayed-event test now asserts the unchanged GBP 500 balance, same pending ID and payload, closed permit before approval, exact sent subject and note, and refusal of a second approval. Only these two of the 28 native inputs changed between the original-contract run and final run. The production source and the 26-case reviewer file remained unchanged.

| Received owner test | Git blob | SHA-256 |
| --- | --- | --- |
| `tests/test_reminder_freshness.py` | `164175c727e90a5f7b8b0e22fe9e996498c4fb4c` | `d2c697c0e515413f2fbdc60a0d7b248965e414396e004a1008818936d177bca1` |
| `tests/test_reminder_receiving.py` | `6f1446194b9d20d4ab42b5f3652332b37f72766a` | `8609348105ebb1ba07dd12dab5db30f9cdfbec40cac6f4d9c750452e78b789c7` |

`received-test-contract.diff` preserves the exact changes. `candidate-native-composition.log` records **132 passed, 2 subtests passed**. `native-run-metadata.json` and `native-input-sha256.json` record the final execution and exact native inputs. This green composition includes the complete owner suite, the author's 12 focused webhook cases and the reviewer's 26 cases; no failed test was omitted.

## Runtime, reproduction and limits

Receiving uses Python 3.12.14 and pytest 9.1.1, with bytecode and pytest cache writes disabled. Exact commands, source selection, UTC start times and log hashes are in the run metadata. The packet's artifact manifest is relative to repository root and excludes the manifest itself.

After placing the reviewer test in the repository, the complete native suite runs with:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider -q tests
```

Event identity is process-local, as was the prior seen-event set. This component does not add persistent deduplication, new webhook event types, new provider presentation rules or a combined read-and-send provider transaction. Its acceptance is limited to the exact source and received test tuple. Publication, integration and browser/Pyodide composition belong to the execution owner and are not claimed by this native receipt.
