# Independent receiving: exact invoice values before draft creation

## Decision

Accepted the bounded extraction, invoice-builder and pre-draft admission component at the source tuple below. The final unchanged independent suite passes **31/31** cases. The full original, author and independent native suites pass **130/130** cases together. All 22 native source, test, fixture and configuration inputs were hash-identical before and after the final run.

This is source-level receiving for the offline native Ledgerly component. It does not itself merge, deploy, enable an HTTP client or attest the later combined current-invoice component. The composition owner receives the exact tuple separately.

| Accepted source | Git blob | SHA-256 |
| --- | --- | --- |
| `ledgerly/extract.py` | `18b01b5c9b448b99bbead856d3a0e038a004e3e5` | `2afaf50c17b49ea9197367d77ded4b44421c6d8d46eb589d985693d61a65fa6d` |
| `ledgerly/paypal.py` | `43554a287c3b94b48e5376d9fa10f9287e1bea3f` | `61e86702ffd72eeadb680fb5bddb3e8498427852a9130b064ec7a63ce9ac4dfe` |
| `ledgerly/agent.py` | `41082ddcb64985a838220e602d6ad99e631fcc4b` | `be59a4e305ff0dc3874a7070f7b446b06fd11a5d199caa9cdc11039eb0e1c773` |

Baseline: `d4d3802b7f5ccd78795d91159d907b08cb3e978f`. The first author candidate was committed at `5293f42a2365976afd76eee10f67944272b7dc70`. Intermediate corrected working-tree versions and the final freeze are identified by exact file blobs and SHA-256, without inventing commits for them. The accepted source pins are also machine-readable in `accepted-source-pins.json`.

## Independence and method

The reviewer read the baseline extraction code, the original extraction tests and the candidate source diff before writing the independent cases. The reviewer did not read the author's new `tests/test_invoice_value_boundaries.py` while designing them. This is independently authored receiving, not a blind source review. The reviewer made no production-source changes.

The first 26 cases remained byte-identical. Three controls discovered during correction review were added in a separate file; two final lexical controls were added in another separate file. The complete 31-case suite was then executed unchanged against baseline, each preserved rejected candidate and the final accepted candidate. Positive controls require exact draft, local ledger and review values; negative controls require a structured review result with no invoice-number request, draft, ledger row or pending approval.

Every rejected candidate was copied from the exact observed author files before later corrections, then independently hash-checked and executed in a separate package. No rejected version was reconstructed. `rejected-r1/` contains the complete three-file initial tuple; later rejected extractors are retained separately because `agent.py` and `paypal.py` did not change. `rejected-source-pins.json` records their identities.

All provider-facing exercise uses the project's native offline `SandboxMock`. Fake model output is a supplied lambda returning a fixture JSON string. No network or live provider is needed by these cases. Successful deposit controls execute the existing human-approval method and verify one mock payment; a direct subsequent payment attempt still raises `ApprovalRequired`.

## Comparative results on the same final 31 cases

| Source | Extractor blob | Passed | Failed | Raw log |
| --- | --- | ---: | ---: | --- |
| Baseline | Commit `d4d3802b7f5ccd78795d91159d907b08cb3e978f` | 7 | 24 | `baseline-final-suite.log` |
| Rejected r1 | `9e9fb7a94b05e89bc8c24f5d67bab9632cdd2f7c` | 16 | 15 | `candidate-r1-final-suite.log` |
| Rejected r2 | `15117b84b3722fa6ba4f7d702c68d512cec8d210` | 26 | 5 | `candidate-r2-final-suite.log` |
| Rejected r3 | `11d289a49d3816eefb1d160e4dfaac5ebaaba442` | 29 | 2 | `candidate-r3-final-suite.log` |
| Accepted r4 | `18b01b5c9b448b99bbead856d3a0e038a004e3e5` | 31 | 0 | `candidate-r4-final-suite.log` |

`candidate-r4-native-composition.log` records **130 passed**: 52 original tests, 47 author tests and 31 independent tests. Earlier staged logs remain in the packet for provenance; they used the original 26 or expanded 29 cases and should not be confused with the final 31-case comparison above.

## Consequential findings and corrections

### Whole-job validation before any request

The initial candidate validated individual items but not the aggregate currency total. Two individually representable maximum-sized USD amounts, or two corresponding JPY amounts, could exceed the supported total precision. With a valid EUR part first in the same job, the agent allocated invoice numbers and attempted draft creation before raising `InvalidOperation`, leaving the earlier draft and pending approval behind.

The corrected validator forms each currency total with sufficient arithmetic precision and checks that total against the existing currency representation rules before any draft loop. The independent cases require both the agent and direct `build_invoice` entry point to refuse the unrepresentable amount. The agent must retain no partial state and issue no mock requests. This proves admission before effects for the tested validation failures; it does not add rollback for a later provider transport failure.

### Prior-payment currency and precision survive extraction

Rules extraction previously discarded a deposit's currency. A USD 100 job with a stated EUR 25 deposit could consequently record a USD 25 payment after approval. The same failure affected explicit `US$` deposits in a CAD document and mixed-currency deposit lines. Two individually invalid USD 0.005 deposits could also sum to a superficially valid USD 0.01.

The corrected parser retains each deposit currency, checks each deposit's precision before aggregation and requires the payment currencies to match a single item currency. Bare dollar amounts use the existing explicit document currency context consistently. The review verifies refusal for foreign or mixed deposits and verifies exact successful USD, EUR and CAD deposit flows through the human-approval gate. No exchange rate or implicit currency conversion is introduced.

### Complete numeric input, exact quantity and explicit review

The initial rules parser could change `-$10` to positive 10, `$1e3` to 1, and `$1,23` to 1. Table quantities `.5` and `-1` could become 5 and 1. Each malformed-source case includes a valid anchor item: silently dropping the malformed line is therefore detected as an incorrect partial draft, rather than accidentally passing as an empty extraction.

The corrected parser retains signs, validates comma grouping, consumes whole quantities and prevents valid-looking numeric prefixes from hiding the remaining input. Scientific notation may be supported exactly or refused for review; it may not be shortened. Accepted controls also prove that quantities `0.5`, `0.00001` and `1E+6`, including a valid fractional JPY quantity, survive the builder and mock ledger without quantity rounding or exponent serialization changes in the outgoing quantity field.

### Corrections were themselves checked

The first correction introduced a `KeyError` when a supplied extraction's invoice currency did not match its sole item currency and a prior payment was present. It also admitted finite `1e999999999` into rules summaries or deposit addition, causing `Decimal.Overflow` before structured review. The next correction checks that the matching total exists and rejects values outside the existing 28-integer-digit arithmetic range before those operations.

The third candidate still allowed regex backtracking into a shorter numeric prefix. With a USD 5 anchor, `USD 12.345.67` produced a total of 17.34, and `USD 1e33e2` produced 1005.00. The final change adds the missing remaining-digit boundary. Both complete-token controls now return review before any request, while all 29 prior independent cases and 99 native original/author cases remain green.

### Public entry points revalidate supplied extraction state

Additional controls supply a high-confidence extraction with an empty stale issue list but a missing quantity, nonfinite unit price, currency mismatch or negative deposit. `validate`, `build_invoice` and `Agent.tool_create_invoice` must all reject the invalid monetary state. The agent's review must not mutate the caller's extraction. A multi-currency job with an invalid later part must not create an earlier valid draft. Fake-model nonfinite price and payment values must return review rather than throw or issue requests.

## Runtime and reproduction

Final receiving ran on 2026-10-08 with Python 3.12.14 and pytest 9.1.1. Exact commands, source selection, UTC start times, interpreter path and environment are recorded in `accepted-run-metadata.json`. `native-input-sha256.json` lists the 22 native inputs used for the 130-test composition. The three reviewer test hashes are in `receiving.json`, and `artifact-sha256.json` covers the complete packet except that manifest itself.

For a repository containing this evidence and these reviewer tests, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider -q tests
```

The final reviewer snapshot and logs were initially written to a bounded memory-backed directory because the shared overlay returned `ENOSPC`. The previously used test interpreter had also been removed; final receiving used an already installed environment with the same Python 3.12.14 and pytest 9.1.1 versions. No package installation, production rewrite or substitution of test outcomes was used. These execution details are preserved to explain the path change, not to change the accepted code scope.

## Receiving boundary

Accepted behavior is bounded by Ledgerly's existing currency set, precision rules, supported extraction grammar and offline `SandboxMock` semantics. Amounts outside those rules are held for review; this component does not implement currency conversion, new invoice-edit semantics or payment-provider limits. All 12 repository fixtures remain included in the native input hashes and test composition. Browser/Pyodide and current-invoice composition are handled by the receiving owner using the accepted source tuple; this packet makes no separate claim about their results.

The exact final source needs no further change from this review. Any later source change should be received against its own tuple rather than inheriting this acceptance silently.
