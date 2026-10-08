# Review prior-payment language before recording a deposit

Source contribution: `hamon-62d01a8a-product`, under Jacob's autonomous HAMON execution mandate. Coordinated in [Ledgerly #15](https://github.com/Jacob-Met/ledgerly/issues/15). Independent reviewer: `hamon-62d01a8a-coordination`.

## User-visible correction

The existing extractor treated any priced line containing a payment cue such as `deposit` as money already received. Against exact main source, all three of these statements produced `amount_paid=500`, no blocking issue, and a USD 2,000 draft whose pending send action also promised to record a USD 500 external payment:

- “A deposit of $500 is due before work begins.”
- “The $500 deposit has not been paid.”
- “I will pay a $500 deposit next week.”

The correction requires a complete supported statement of a completed payment. An uncertain detected payment line contributes no received amount and creates an actionable `amount_paid` error. The existing Agent then makes no invoice-number or draft request and creates no pending action. The existing review adapter lets the visitor explicitly correct the amount received, check the fields, create a draft, and approve its send separately.

The original “We already paid a $1,000 deposit by bank transfer last week” fixture still records that supported amount only after the existing separate approval. Every field of all twelve shipped fixture extractions remains identical to the original source.

## Recognition boundary

This remains the repository's deterministic rules extractor. The existing payment-cue detector is unchanged. Within that path, recognized completed statements include `We already paid ...`, `We have paid ...`, `Prepaid ...`, `Deposit paid: ...`, and supported passive paid/received statements. Optional simple completed-payment context includes bank/wire transfer, cash/check/cheque, upfront/in advance, today/yesterday, and last week/month.

The full line must match and contain exactly one recognized money amount. Negations, future or conditional statements, quotations, questions, unsupported tails, and multiple amounts require explicit review. A positively supported amount on another line remains visible, while the uncertain line still blocks automatic drafting. Unsupported wording may therefore ask for review even when a human can tell that payment occurred. The parser does not authenticate a payment, implement a general natural-language inference system, or change detection outside the existing payment-cue path. Explicit human corrections and the separately owned numeric/currency validator keep their existing contracts.

## Exact source and scope

| Subject | Git identity |
| --- | --- |
| Author canonical base | `27193d726c9a7c24bbce77f5bcc961629b484ee6` |
| Author base tree | `1b64c91887f203b694e72af694e9ada95c2c16ab` |
| Original `ledgerly/extract.py` | `a0130ab7cd9930a05a05c0a42e9eb38a8d10711d` |
| Qualified extractor | `c4ee64a72f6b7613d5ded235de4ca09a9bbd55f6` |
| Independent receiving main | `1871942ecb19aa9756bb36b380795bc6c7bf238d` |
| Independent receiving tree | `a26d5ff9705e83bc248857d4b501068da0b6fb16` |

Qualified extractor SHA-256: `1a1d733f366b648f9acb5465c50f708fa30fb2f6021045c0764a8c9a914fd653`.

Production edits are three adjacent grammar definitions and the existing `_line_items` payment branch. The independent byte-preservation proof reconstructs the original file exactly when those two hunks are reversed. The shared numeric/currency validator (#7), reminder behavior (#8), due-date work (#12), provider/approval code, and browser/review source are unchanged. No AGENTS.md exists in the inspected complete author/receiving trees. The local source snapshot has isolated qualification history and does not claim full canonical Git ancestry.

## Native qualification

| Evaluator | Original source | Strict candidate |
| --- | --- | --- |
| Authored, 11 unittest methods | 7 nonpassing methods, 26 failing subcases; 4 passing methods | 11 pass, normal and `-O` |
| Independent, 11 unittest methods | 7 nonpassing methods, 15 failure entries; 4 passing methods, normal and `-O` | 11 pass, normal and `-O` |
| Shipped fixtures | Baseline complete extraction objects retained | All 12 objects exactly equal |

Subcases/failure entries are not counted as additional methods. Both successful suites have zero skips or cancellations. Author qualification uses Python 3.12.14 with the actual RulesExtractor, Agent, SandboxMock and unmodified native browser bridge/review adapter. Independent qualification also preserves the newer Agent blob `19f261b1430769952057697d68472722a11cf643` on the later main, which differs from the author's older Agent. All provider operations use only SandboxMock. No browser, live invoice, real provider, client message, account, credential, external network, or runtime service was involved. Local pytest is unavailable; no full pytest suite, hosted CI, browser rendering or deployment pass is claimed.

The first author harness expected an `ok` field in the successful approval result. The actual interface returns `deposit_payment_id`; that test assertion was corrected before the paired baseline/candidate result. Its initial log is retained. The first implementation used paid-phrase matching with excluded words. Independent review demonstrated five actual false-payment flows for future contractions, quoted history and inverted conditionals; its expanded 11-method evaluator still had 12 failure entries across 6 methods. The accepted full-statement successor passes that unchanged evaluator. Both rejected source and failure evidence are retained under `independent/predecessor-evidence/`.

Shared scratch reached ENOSPC during evidence preservation. Failed/truncated writes were not counted as completed qualification. Exact source hashes were checked and the small owned packet was copied to private shared memory, where both successful author runs and the optimized baseline run were retained. Other contributors' files were untouched.

## Replay

From an exact candidate checkout:

```sh
python3 -B -m unittest discover -s tests -p test_prior_payment_language.py -v
python3 -B -O -m unittest discover -s tests -p test_prior_payment_language.py -v
LEDGERLY_REVIEW_ROOT="$PWD" python3 -B docs/receiving/prior-payment-language-62d01a8a/independent/independent-payment-review.py
LEDGERLY_REVIEW_ROOT="$PWD" python3 -B -O docs/receiving/prior-payment-language-62d01a8a/independent/independent-payment-review.py
```

The independent packet includes its frozen minimal receiving source, exact dependency pins, original/provisional source, unmodified evaluator and full available logs. Its `REVIEW.md` explains source composition and the independent receipt. `fixture-equivalence.json` retains the twelve complete original extraction objects. Publication must preserve all unrelated target-tree leaves and refresh the extractor/dependency pins before extending this acceptance to a newer target.
