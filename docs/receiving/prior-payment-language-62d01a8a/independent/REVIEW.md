# Independent review: Ledgerly prior-payment recognition, issue #15

## Acceptance

Accept the frozen extractor blob `c4ee64a72f6b7613d5ded235de4ca09a9bbd55f6`, SHA-256 `1a1d733f366b648f9acb5465c50f708fa30fb2f6021045c0764a8c9a914fd653`, for the bounded prior-payment recognition change in [Ledgerly issue #15](https://github.com/Jacob-Met/ledgerly/issues/15).

The unchanged independent 11-method evaluator passes in normal Python and under `-O`, using the later current-main Agent implementation. All methods completed without skips, errors, or cancellation. The independent evaluator SHA-256 is `9ab16e70c968cc678bff03c80417415f0521d272be1cae092885567a987f566e`.

The change admits supported completed-payment statements inside the existing payment-cue path. Other detected payment language receives an actionable `amount_paid` error and reaches the existing human-review flow before draft creation. This acceptance covers the native rules parser, current Agent, existing review adapter, and in-memory SandboxMock integration.

## Why the receiving review mattered

The first repair checked for a paid phrase plus a list of excluded words. Independent native witnesses showed it still accepted future-perfect contractions (`We'll have paid ... by Friday`), single/curly-quoted statements about another project, and inverted counterfactuals (`Had we paid ..., we'd ...`). At the exact provisional candidate each of five initial witnesses yielded `amount_paid=500`, created a mock draft and pending approval, and recorded a mock external payment of 500 after fixture approval.

The strict successor checks the complete supported statement. The same independent evaluator now rejects these cases, including additional backtick quotation, unsettled-receipt tails, and mixtures of a supported receipt with an uncertain payment line. The amount from a supported line is retained while the uncertain line still blocks drafting; a high confidence score cannot erase the blocking issue.

## Exact comparison

| Source | Native methods | Result |
| --- | --- | --- |
| Original extractor `a0130ab7...` | 11, normal and `-O` | 4 pass; 7 nonpassing methods, 15 failure entries |
| Observed first repair `ca861ba8...` | 11, normal | 5 pass; 6 nonpassing methods, 12 failure entries |
| Strict successor `c4ee64a7...` | 11, normal and `-O` | 11 pass in each mode |

Failure entries include subtests and are not additional independent methods. The initial five concrete flow witnesses are included in the later evaluator's semantic coverage and are not counted as five more independent workloads. Original-normal results are recorded as a structured summary of the completed tool observation; original `-O`, provisional normal, and both strict runs retain complete native output logs.

## Effects and human correction

Uncertain recognized payment statements produce zero mock provider requests, including invoice-number and draft requests; no ledger entry or pending approval is created. A supported original deposit fixture remains recognized and still requires the existing explicit approval before either send or payment recording.

The existing human-review adapter accepts a corrected prior payment of zero. The resulting invoice and approval summary omit the false received-deposit claim. Sending that reviewed invoice creates no payment record. A separate explicit human correction to 375 is preserved exactly and recorded only after a separate fixture approval. Correction scope ends with the source-bound operation; it cannot silently bypass later review or apply to changed source text.

The agent, review adapter and PayPal implementation were not modified. Only SandboxMock was instantiated. No real invoice, provider action, network request, credential lookup, or estate runtime operation was performed.

## Current-main receiving custody

Author base was `27193d726c9a7c24bbce77f5bcc961629b484ee6`, whose Agent blob was `5fb6c302d6c6bd343842578f39aea3b2c93866e3`. Independent receiving used later main `1871942ecb19aa9756bb36b380795bc6c7bf238d`, actual tree `a26d5ff9705e83bc248857d4b501068da0b6fb16`. The complete tree contained no AGENTS.md files.

| Dependency | Exact reviewed blob |
| --- | --- |
| Original extractor | `a0130ab7cd9930a05a05c0a42e9eb38a8d10711d` |
| Current Agent | `19f261b1430769952057697d68472722a11cf643` |
| PayPal implementation | `02f73474cfb5e6bbb8ac0f791d6595c8d756deef` |
| Existing human-review adapter | `35abc10433174d3f5282c7dbd88b1e2c0df4c5d8` |
| Strict extractor | `c4ee64a72f6b7613d5ded235de4ca09a9bbd55f6` |

The source-preservation proof removes exactly the three added payment grammar definitions and restores the one previous `paid += amt` branch. The result is byte-identical to the original extractor. All other parsing, validation, numeric/currency, due-date, LLM, and table code is unchanged. The current Agent's newer reminder work is retained. Issues #7, #8, and #12 remain separately owned.

## Evidence and replay

`source-preservation.json` records the byte-preservation proof. `strict-source-pins.json` pins every receiving dependency. `strict-candidate-normal.json` and `strict-candidate-optimized.json` pin the evaluator, source and complete logs. `predecessor-evidence/` retains original/provisional source and failure records. `authored-test-snapshot.py` is the author's frozen test source (SHA-256 `da54e63f8d0d1c49159ec6f2e4992a478ac0b3af2439fd069bd812b278886f1e`), copied for custody; this review's counts come from the independent evaluator.

To replay the independent checks against a full exact source checkout, set `LEDGERLY_REVIEW_ROOT` to that checkout and run `python independent-payment-review.py` or `python -O independent-payment-review.py`. The full checkout supplies the existing fixture and review adapter. The included `source/` directory is the narrowly frozen receiving copy used here.

Shared scratch reached ENOSPC during preparation. This modest isolated receiving packet was written to private shared memory; only verified duplicate replay source copies owned by this reviewer were removed elsewhere. Unique evidence and other workers' files were preserved. Root retains GitHub write serialization and will persist the exact source and selected evidence in the contribution.

Before publication, refresh the target branch and source leaf. If the extractor remains `a0130ab7...`, the qualified successor applies unchanged. Preserve current unrelated source leaves and use the accepted exact successor bytes. A change to the extractor or relevant dependencies requires an explicit receiving comparison before extending this acceptance.
