# Exact invoice values before draft creation

Contribution: `estate-06e2ad0ce13f/continuity_production`, 2026-10-08.
Coordination: [Ledgerly #7](https://github.com/Jacob-Met/ledgerly/issues/7).
Baseline: `main@d4d3802b7f5ccd78795d91159d907b08cb3e978f`.

## Problem and resulting behavior

Ledgerly could queue a draft whose money disagreed with the extracted values the
visitor was asked to approve. At the baseline, a sole EUR line under a USD invoice
became a USD line without any warning. An LLM-produced `2 × USD 0.015` displayed
`0.030` in the approval/ledger, while the actual draft serialized `0.02` per unit
and the existing provider mock calculated `0.04`. A missing quantity reached both
invoice-number allocation and draft creation before raising `InvalidOperation`.
Nonfinite values crashed validation, and a negative deposit was accepted.

The shared validator now returns review errors for missing/nonfinite quantities,
nonpositive or out-of-range quantities, unsupported per-item currencies, conflicting
invoice currency, nonfinite or negative payments, and monetary values that need
implicit rounding. The rules parser preserves every decimal digit so the same
precision rule can inspect `0.015`; it previously extracted `0.01`.

Independent review also found that individually representable line amounts could
overflow when summed, after an earlier currency's draft had already been created.
The whole job now admits exact per-currency sums before any number allocation.
Each source deposit is checked for its own currency and precision before aggregation;
a EUR payment cannot be relabeled USD, and two sub-cent deposits cannot hide one
another's invalid precision. A document's explicit dollar currency also applies to
its unqualified dollar deposits.

Money and quantity tokens are consumed completely. Signed values retain their sign;
leading-decimal quantities such as `.5` retain their value; malformed comma groups,
decimal tails and exponent tails cannot be shortened to a valid prefix. A malformed
priced line blocks the complete job instead of silently disappearing from it.
Numbers outside the existing invoice arithmetic range are refused before rules
summaries or deposit sums perform arithmetic.

`Agent.tool_create_invoice` freshly validates the complete extraction before the
first provider request, including values returned by custom/explicit-review
extractor adapters. It does not modify those adapters' returned issues. A bad
second currency part therefore cannot leave a first part drafted. `build_invoice`
validates again at the public serialization boundary and refuses invalid values
even if a caller supplies an empty or stale issue list. Accepted quantities use
fixed-point notation. Sending, approval permits, providers and webhooks are unchanged.

## Exact-value policy

This change deliberately **requires review instead of rounding prices, payments,
or fractional line totals**. For example, `0.5 × USD 0.01` is review-required, while
`0.5 × USD 85.00` is accepted and remains `USD 42.50`. A person can correct the
quantity or price before drafting. This is a conservative Ledgerly product policy,
not a claim that PayPal rejects every fractional product or a new provider rounding
algorithm. No exchange rate is inferred and no currency is silently converted.

The existing declared currency set is unchanged. PayPal's current primary
[invoice definition](https://developer.paypal.com/api/invoicing/v2/definitions/invoice/)
requires item quantity and a currency-bearing unit amount; it documents quantities
up to one million and five decimal places, and fixed-point monetary strings.
The [currency reference](https://developer.paypal.com/api/codes/currency) identifies
JPY, HUF and TWD as currencies without decimal amounts. Both were read on
2026-10-08. The implementation continues Ledgerly's existing positive-quantity and
zero/two-decimal money policy and does not expand account or country support.

## Executed verification

`tests/test_invoice_value_boundaries.py` tests the real extraction → agent →
draft/mock receiving path, a custom extractor, and direct public-builder calls.
Its baseline is retained in `baseline.txt`: **38 failed, 9 passed**. These are
controlled synthetic cases, not evidence that a live invoice or payment was affected.

The final repaired core and all inherited/independent tests pass: **130 passed**
(47 authored cases, 31 independently designed receiving cases and 52 existing
cases). The accepted-value controls check matching currency, quantity,
unit amount, approval total, ledger total and provider-mock total, and preserve the
pending approval with no send/reminder/payment request. Independent valid-deposit
controls additionally execute one explicit human approval against the offline mock
and check the exact currency, paid amount and remaining balance. Existing
multi-currency, zero-decimal, deposit and approval tests remain included.
`native-tests.txt` preserves the initial 99-test qualification; the independent
packet records the final 130-test run and its pinned Python 3.12.14 interpreter.

The sibling `invoice-values-independent-06e2ad0ce13f` directory preserves the
rejected candidates and review evolution. Its unchanged final 31-case set has
pass/fail counts: baseline **7/24**, candidate 1 **16/15**, candidate 2 **26/5**,
candidate 3 **29/2**, final candidate **31/0**. The final reviewer found no further
correction necessary and confirmed all 22 native input files remained unchanged.

Actual Pyodide 0.29.3 / Python 3.13.2 receives the final component through its
baseline browser bridge: **8 checks pass**. These cover source precision/currency/sign/tail
refusal with zero provider-mock requests, structured nonfinite input, and explicit
approval of a valid fractional invoice with a matching deposit and balance.
`pyodide-component-receiving.json` records the component's exact source hashes.
The inherited two-test
Pyodide workflow also passed on the initial candidate. No live PayPal call occurred.

## Retained composition with main 1871942

The accepted component was cleanly merged with current `main`
`1871942ecb19aa9756bb36b380795bc6c7bf238d`, retaining the published invoice-correction
UI, reminder freshness and interactive-demo work. On that composition, **172 native
tests and two subtests pass**. A structural comparison proves the accepted
`tool_create_invoice` method is unchanged, and that the rest of `agent.py` has the
same syntax tree as current main after removing only the added validator import.
All changed paths remain inside the announced contribution boundary.

`receive-pyodide.mjs` also executes the current bridge and review adapter:
**10 checks pass**, including invalid rounded values being refused at the review
step and valid corrected values consuming their checked revision only once. The
exact composed module, bridge and review-adapter hashes are recorded in
`pyodide-receiving.json`. `current-main-composition.json` and
`current-main-native-tests.txt` retain the source comparison and full native result.

## Current-main composition with 4bdaaa9

An authoritative GitHub branch read then returned main
`4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`, including the merged invoice-deadline,
browser-recovery and prior-payment-language contributions. The previous Git remote
head read was stale. The new exact main commit was fetched and composed at local
source commit `22b7b5404e0bde8c6796d3abd8c5d177b5e84e1f`.

The only merge conflict was the rules payment-admission block. The current owner's
complete-statement confirmation remains the gate: only a confirmed payment enters
this contribution's per-payment currency and precision validation and exact sum.
An uncertain statement still leaves that payment out of `amount_paid` and requires
review. No confirmation-language pattern was relaxed. Serialized positive-term
invoice deadlines and all current reminder and browser-recovery source are retained.

On this composition, **197 native tests and 34 subtests pass**, including the
unchanged deadline and prior-payment-language owner tests and all 31 independent
invoice-value cases. The actual current Pyodide bridge/review receiving again
passes **10 checks**. Exact source hashes and raw results are in
`current-4bda-composition.json`, `current-4bda-native-tests.txt` and
`current-4bda-pyodide.json`. The earlier component and main-1871942 receipts remain
unchanged as evidence of the versions they actually exercised.

Independent receiving accepted this exact composition: the unchanged owner
payment-language and deadline tests plus the original 31 invoice-value cases pass
**56 tests and 32 subtests**; the same set has 22 failures on untouched main 4bdaaa9.
A further **11 confirmation/value/deadline probes pass**. They verify that confirmed
foreign, malformed, subunit and negative payments still hold the job before requests,
uncertain statements leave their payment out of `amount_paid`, and a confirmed
USD 25 deposit preserves the original deadline through delayed approval. The
unchanged source patterns, uncertainty branch and deadline construction were also
checked directly. The complete focused receipt is in
`../invoice-values-independent-06e2ad0ce13f/current-4bda/`.

## Integration boundary

This is isolated source work. No provider credentials or network calls, actual
invoice drafts, messages, payments, deployed UI or service changes are claimed.
The browser demo stages these exact Python modules from `ledgerly/` through its
existing `web-demo/scripts/stage-python.mjs`; the separately owned correction UI
(#5) and worker recovery (#6) remain untouched. The final source is independently
qualified; source integration and deployment remain separate receiving steps.
This contribution is not a production lease.
