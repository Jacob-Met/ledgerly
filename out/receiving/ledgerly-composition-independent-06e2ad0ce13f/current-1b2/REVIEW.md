# Ledgerly published-pair receiving on main1b2

**Accepted for this exact published pair and pinned owner main.** Published extraction PR19 and webhook PR21 merge cleanly with the newer owner receipt-term fix. The receiver made no production-source changes and resolved no merge conflicts.

## Published inputs and local composition

| Role | Commit | Tree |
| --- | --- | --- |
| Pinned owner main | `1b2b902d5dd412a8b61c9b9075b815c1d0029365` | `ba5ab49270c136d86bc492411f49a5bdebdb6049` |
| Published PR19 | `f67e2c4034804f657eccad38887f377f28011e98` | `ae425d9afb682b55138143780b461d1c61e9e820` |
| Published PR21 | `d4ff41c66abe816a0c8b891bf75e0ad21ebaa755` | `cd1bfada6fc4070250a73f0b6390efc755de568c` |
| Local receiver composition | `4b1375645ee98af6cb0afeaacafaaf642776f98b` | `7bbd3e34686e633e71908eb4f2bc4c0342451731` |

All three remote commits were fetched by exact SHA. The published extraction tree matches the announced tree, and the published webhook tree matches the author's native `e9c482778c737f52d7a7936cc471b6be9384e108` tree. Both published branches' complete executable, native test, and web trees match the previously qualified immutable component commits. Local merge commands and outputs are preserved in `git-operations.json`.

## Qualified combined source

| File | Git blob | SHA-256 |
| --- | --- | --- |
| agent.py | `8ba49c074571f74cbdab3e851861648322de8f17` | `c187df78892ecee3993b12bb447e4df1caccbf51fad848c3251669be40b9ac65` |
| extract.py | `100e581d3ef0d99555f49264859d01b535c6094f` | `4921f5df19cb35089afc8db3641cae9b8fbd089279dd84ef9555c10b759e2f16` |
| paypal.py | `1d805837d9ed4fe29f42ae7093764c47b0060edd` | `e04fa6abc90747f9b723660aa8d76a174e4bff89e1e41067aefb4c75bc971965` |

The full composite source files are included. Exact source-span checks retain the published extraction create method, published webhook initializer/handler, and the other 17 owner Agent methods. The complete owner LedgerEntry class, invoice receipt presentation, payment-term function, and mock send method are unchanged. Whole-module AST comparisons prove that the agent and PayPal modules contain only the accepted method/function replacements and their admitted imports over latest owner main. The extractor is byte-identical to the published extraction file.

The new receipt-term owner tests are byte-identical to main1b2. Those tests cover raw and reviewed receipt workflows, delayed sends across calendar boundaries, explicit provider dates and no-date replacements, malformed terms, failed sends, current-reminder invalidation, and unresolved external sends. Complete UI source, UI tests, and Python bridge trees remain identical to owner main.

## Executed qualification

| Gate | Result |
| --- | --- |
| Complete native suite | 246 passed and 60 subtests passed; no failures |
| Existing engine/review tests in actual Pyodide | 10 passed across two files; no failures |
| Frozen source, native tests, fixtures and web configuration | All 45 unchanged through both runs |
| Standard staged Python, fixture and runtime files | All 22 byte-equal to their source inputs |
| Original Pyodide runtime inputs | All five unchanged |
| Tracked receiving checkout after testing | Clean; exact same commit and tree |

Native execution used Python 3.12.14 and pytest 9.1.1 with bytecode and pytest cache disabled. The browser-runtime run used Node 24.19.0, npm 11.9.0, Pyodide 0.29.3, and Vitest 5.0.3. The original npm test command executed its full standard Python, fixture, and runtime staging. Dependencies were linked into an owned node_modules directory, with all generated files and caches isolated from author checkouts.

```sh
python -B -m pytest -p no:cacheprovider -q tests
npm test -- tests/engine.test.ts tests/review.test.ts
```

Exact commands, interpreter, working directories, UTC timestamps, raw logs, input hashes, staged-file mappings, and setup provenance notes are retained. The pre-existing npm proxy-configuration warning did not affect execution. These runs qualify the offline core and SandboxMock through native Python and actual Pyodide; no provider or live payment operation was enabled.

## Integration boundary

The local receiving composition was not rebased, published, or deployed. The receiver did not edit either author's tree. The prior main187 and main4bda receipts remain separate; their negative controls were reused by exact source pins and were not rerun. This receipt qualifies the published pair on pinned main1b2, not future executable changes or unselected JavaScript suites. Copy this directory unchanged into the established repository evidence venue. Manifest paths are relative to repository or packet root.
