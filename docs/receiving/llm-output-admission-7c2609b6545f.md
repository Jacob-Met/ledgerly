# Ledgerly: admit model output before invoice allocation

Status: accepted native source, prepared for a source-review branch only. All new GitHub Actions remain paused. Root separately inspected the current workflow event definitions and may write a unique non-main review branch only after its current guards pass. PR creation and main-branch merge remain held; workflows and required gates are unchanged. This packet makes no hosted-CI, full-pytest, canonical-integration or deployment claim.

## Defect and behavior

LLMExtractor promises an extraction with bounded confidence and review issues. Its original decoder assumed several returned field shapes after parsing JSON. A model response could therefore raise AttributeError in email normalization, line-item parsing or invoice-body construction; an object-valued currency or malformed severity could raise TypeError. Other malformed responses silently discarded issue entries, retained NaN confidence, or truncated fractional payment days.

The original native witness preserves 16 individual cases: three ordinary controls pass and thirteen violate the frozen admission contract, including seven uncaught exceptions. The portable regression suite then reproduces the receiving consequence through the actual Agent and SandboxMock: NaN confidence, fractional days and discarded issues could allocate drafts; an object client name could reach invoice-body construction after number allocation.

A separately attributed root-review probe later found that amount_paid values [], {} and false became zero through the shared parser's defaulting expression and each allocated a number, draft and pending proposal on both the original current-parent source and the first candidate. Those negative receipts are preserved. The final helper refuses these malformed shapes before shared conversion while preserving null, empty text and compatible numeric values.

The change admits known decoded shapes before calling the existing shared value parser and validator. A malformed response becomes the existing empty, zero-confidence extraction with an error issue beginning "LLM output unusable:". Agent already projects that result to needs_review before number or draft allocation. No new invoice policy or Agent special case is introduced.

## Exact scope

Only ledgerly/extract.py changes in existing product code:

- Add the private _validate_llm_output helper beside the existing LLM response parser.
- Require complete() to return a string before stripping a code fence.
- Validate decoded shapes before shared conversion and construct every admitted issue instead of silently discarding malformed entries.
- Refuse supplied boolean/container amount_paid values before the shared parser can default them to zero; retain its null/empty-text and numeric behavior.
- Include numeric OverflowError in the existing malformed-content exception projection.

The complete() invocation remains outside that catch. Exceptions raised by the completion service keep their identity and propagate to its caller.

Extraction.from_dict, validate, RulesExtractor, _TOTAL_RE, table handling, numeric/amount precision rules, Agent, PayPal adapters, browser surfaces, dependencies and workflows remain unchanged. SOURCE-CHANGE-REVIEW.json proves exact two-span text composition and whole-module AST equivalence after removing the helper and restoring the original LLMExtractor.extract method. The companion Agent, PayPal and package-init files retain their exact baseline bytes.

The current parent includes the separately owned total-label fix, Ledgerly PR51 by hamon-3dc74ef3b04d. Its complete source is preserved in this composition. The separate-table owner (Ledgerly #49/#50, estate-44df5c2e45ae) retains RulesExtractor._table. A later publisher must compare a fresh authorized parent and preserve both owners' work.

## Admission contract

| Returned field | Behavior |
| --- | --- |
| client_name, client_email, currency | Missing or null remains accepted for existing validation; a supplied non-null value must be a string. |
| line_items | Missing or null retains the existing empty default. A supplied value must be a list of objects. Non-null desc, currency and unit members must be strings. |
| issues | Missing or null remains empty. Every supplied entry must contain exactly field, severity and message, all strings; severity is error, warning or info. Missing, extra or unsupported members cause refusal. |
| confidence | Missing defaults to 0.5. Supplied values use the existing float conversion but must be finite and in [0, 1]; booleans are refused. Supplied null remains unusable as before. Compatible numeric text is preserved. |
| due_days | Missing or null remains None. Integers and integral numeric floats are accepted; fractional floats and booleans are refused before int() can truncate them. Existing int-compatible text, including whitespace or a leading plus sign, keeps its behavior. Decimal/exponent/comma text remains subject to the original int conversion. Negative or oversized integers still reach the existing business-range validator. |
| amount_paid | Missing/null, empty text and compatible numeric/text amounts retain their existing behavior. Supplied booleans and containers are refused before the shared default can turn them into zero. Existing decimal conversion, prior-payment and currency rules remain in force. |
| qty, unit_price | Existing shared numeric conversion and business rules remain in force. The repair does not create a new amount policy. |

These are checks on the decoded JSON value using the existing decoder. They do not introduce an arbitrary-precision JSON-number format, reinterpret currencies, infer missing attribution, repair historical stored extractions, or guarantee arbitrary completion-adapter behavior. Unknown top-level fields retain the prior parser behavior.

## Exact source and replay

Original inspected parent: a4c7f05d511fb6e9ae4e357d78f696b464625ffc, tree d67d6d0479ea2fad0e4778365c6fcd06aa13edf6.

Final composed parent: da2e47043d7f18aa231d80b568dd30e31ed8b77c, tree ea9857cebc1fa91582f1f65ea6be34cd86eb23c0. The observed main advance changes only the total-label source and adds tests/test_total_labels.py. SOURCE-CHANGE-CURRENT.json proves the same frozen admission hunks compose exactly, preserves all other current-parent AST, and confirms that the original-to-current Extraction, Issue, LineItem, _dec, validate, _strip_fence, LLMExtractor, HybridExtractor and split_by_currency ASTs are identical. Agent and PayPal retain their original bytes.

| File | Before Git blob | Candidate Git blob | Candidate SHA-256 |
| --- | --- | --- | --- |
| ledgerly/extract.py | 3f39e513a45a42da9dd3b498ce0a81fd83262f96 | 9199a9d67f9953c862e22c109f3a34690bd25bc4 | 110bf6409e9e48592b32ba9bff5e8533fb6bfb8b33a605e484c8f3ee989930fa |
| tests/test_llm_output_admission.py | New | 39d561f85a69aa5aafec6cccf3f89659c1e53fce | b88ef085170a890d3461b268671d07004131f2eff76a0b16df0e56a4598a2046 |

From a repository checkout with this change, run:

    python -B -m unittest discover -s tests -p test_llm_output_admission.py -v

The test is portable standard-library unittest and can also be collected by pytest. It injects only complete(); extraction, validation, HybridExtractor, Agent, GatedClient and SandboxMock are the actual imported project implementations. The native runner records loaded module paths, before/after hashes, individual subtest outcomes and original failure tracebacks.

Native Python: 3.13.15 at the existing LA7 runtime. The original source passes 4 of the initial 11 method groups, with 27 failure and 18 exception records including subtests. The original candidate and first current-parent composition each pass the unchanged 11-group suite. These stages remain distinct: original candidate SHA-256 7d5357411ae1a803d3a13e318ab504ea5a840388de0c805839b59bd40971e0ff; first current-parent candidate 2ae9eb55cd16410a4cab9a4deb14efaf53832216259fbdc2ab4e0cbd3f0fbce9.

After the root-review amount_paid finding, two changed portable test methods first reproduce six assertion failures against that frozen current-parent candidate: three direct malformed-content cases and three actual Agent allocation cases. The final candidate above passes all 12 method groups, with no failures or errors. All runs preserve their loaded source/test pins. SOURCE-CHANGE-FINAL.json proves the final two-hunk composition against the observed current parent.

Four original undecorated inherited assertion functions also pass on the exact final source: fenced response, hallucinated-email rejection, garbage refusal and the healthy-rules/no-model-call versus low-confidence fallback control. A standard-library runner directly invokes their unchanged AST nodes, _fake/load helpers and two exact fixture files. It records node/file hashes and preserves the complete source inputs. This is four inherited functions executed directly; pytest collection and the full repository suite were not run.

The suite covers valid fenced responses and compatible numeric text, malformed fields/issues, confidence boundaries, exact integral days, nonstring/invalid JSON, optional values, existing grounding and amount precision, prior-draft preservation and healthy retry, real Hybrid refusal, and completion-service exceptions.

Independent receiving accepts the exact final source: 94/94 checks pass, comprising 86 frozen-contract cases, seven separately attributed root-review paid checks and one exact-source-boundary check. The current baseline passes 45/94 and retains 49 failures. A separate nine-case actual Agent/SandboxMock probe confirms [], {}, false and true paid values refuse before number/draft/pending allocation while 0, null, empty text, '0' and '25.00' retain compatible success. Prior-state preservation and healthy retry pass; all source pins remain unchanged.

The initial independent expectations were sealed before candidate inspection. The root-requested amount_paid challenge is explicitly a later source-review probe with separate receipts and attribution, not a blinded expectation. Compact independent acceptance SHA-256: 5fc323e5ed336b30ed82226f1f04f8cc4dba1feeaac53024ae0146fbe10f23e4. Final executed receiver receipt: 1f09930c7ce6da0bfc4689644a857062443875d0e97fd7b1c1fa183e6e9814b1. Exact bytes and the receiver's complete archive are copied with its permission and original attribution.

The current interpreter has no pytest, so no full repository pytest run is claimed. No hosted suite was started. Required integration gates remain the publisher's responsibility; a source-only branch does not constitute canonical integration or deployment.

The final source-review carrier uses fresher parent c498f55883c755553b59921199d54689d99c9730, tree efb9d2f50f79336588f7b14beca29a889899e1a9. Its PR48 intake-file changes do not alter the four executed Python modules or any of this packet's three path beforeimages. The accepted runtime remains byte-identical; no settled behavior test was rerun. The base-leaf manifest and exact tree composition preserve every unrelated incoming file.

## Provenance and limits

Author: estate-7c2609b6545f/commons_execution.
Independent receiver: estate-7c2609b6545f/la7_runtime, with separately frozen expectations and fixtures.
Native author stage: C:\Users\minec\hamon\stage\ledgerly-llm-admission-discovery-7c2609b6545f

Retained evidence includes the exact original source, probe_llm_output.py, ORIGINAL-WITNESS.json, SCOPE.md and claim readback, the portable test and native runner, baseline/candidate receipts, CHANGE-RECIPE.json, CANDIDATE.patch and SOURCE-CHANGE-REVIEW.json. The later current-parent source, exact composition inputs/script, CURRENT-CANDIDATE.patch, SOURCE-CHANGE-CURRENT.json and current-candidate receipt are preserved separately. The final paid-shape correction adds FINAL-CHANGE-RECIPE.json, FINAL-CANDIDATE.patch, SOURCE-CHANGE-FINAL.json and both the new negative and final passing receipts. OWNERSHIP-REFRESH.json records the inspected current scopes and explicitly partial native coverage. This is an advisory external contribution, not a native goal or installed-source lease.

No real model, provider, invoice, payment or email is used. The actual Agent receiving check uses only in-memory SandboxMock drafts; no approval or send operation is called. Source qualification is distinct from deployed adoption.

Primary implementation references:

- [Original extraction boundary](https://github.com/Jacob-Met/ledgerly/blob/a4c7f05d511fb6e9ae4e357d78f696b464625ffc/ledgerly/extract.py)
- [Original Agent admission and draft creation](https://github.com/Jacob-Met/ledgerly/blob/a4c7f05d511fb6e9ae4e357d78f696b464625ffc/ledgerly/agent.py)
- [Actual SandboxMock and invoice-body implementation](https://github.com/Jacob-Met/ledgerly/blob/a4c7f05d511fb6e9ae4e357d78f696b464625ffc/ledgerly/paypal.py)
