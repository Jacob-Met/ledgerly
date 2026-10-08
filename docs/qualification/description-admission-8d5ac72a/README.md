# Preserve reviewed invoice descriptions before drafting

A work description that extends beyond the existing invoice writer's 200-character slice now returns to the normal review flow before Ledgerly allocates an invoice number, draft or pending action. The full description stays available for correction. Accepted descriptions remain literal.

This is the source-native author packet for `estate-8d5ac72a6fae/receiver`. Root owns independent receiving and integration. It records actual Python execution of the maintained review, Agent and SandboxMock paths; it does not claim DOM/browser, installed-service, live-model or PayPal-provider acceptance.

## Exact source

Repository: `Jacob-Met/ledgerly`.

- Actual parent commit: `c498f55883c755553b59921199d54689d99c9730`.
- Actual parent tree: `efb9d2f50f79336588f7b14beca29a889899e1a9`, directly associated through the Git commit endpoint.
- Complete parent tree: 767 leaves, no truncation and no AGENTS.md.
- Original extractor: `3f39e513a45a42da9dd3b498ce0a81fd83262f96`.

| Overlay path | Git blob | Bytes |
| --- | --- | ---: |
| `ledgerly/extract.py` | `41795c76aef15af45e608efed43f7670168dc148` | 36,992 |
| `tests/test_description_admission.py` | `0b97fb7a271ee5d7a88a5d0a96196e64765e21f1` | 9,426 |
| `docs/qualification/description-admission-8d5ac72a/author-receiving.json` | `2125c536e9151ca81f46df8686b07ef265eef623` | 80,784 |

The source and test blobs were read back exactly. The evidence envelope was also read back exactly. This README is the remaining additive documentation leaf; it makes no change to the parent source.

## Original user-visible loss

The frozen witness uses the actual native `handle_json` Analyze → Review → reviewed Draft route. Its 229-character description consists of a 200-character prefix followed by “ Excludes translation rights.” The original review accepts and returns every character, but the resulting SandboxMock invoice contains only the prefix. The literal suffix is lost by `build_invoice`'s existing `li.desc[:200]` slice. An otherwise identical 200-character control reaches the actual invoice unchanged.

The original process exits 1 with one passing control and one expected failure. Complete JSON exchanges, source text, retained invoice names and mock request logs are inside the envelope. These are generated synthetic records, with no approval or outgoing action.

On the frozen correction, the same unchanged witness exits 0: both controls pass. The 200-character description is retained exactly in its invoice. The oversize review has `valid: false`, retains the complete work description and makes zero mock requests. It cannot issue a reviewed draft revision.

## Three-line correction and support boundary

Inside the existing line-item loop in shared `validate`:

```python
        if isinstance(li.desc, str) and len(li.desc) > 200:
            out.append(Issue(f"line_items[{n}].desc", "error",
                             "Use at most 200 characters for this work description before drafting."))
```

The normal validator is already reused by RulesExtractor, LLMExtractor, human review, Agent whole-job admission and the direct invoice builder. The correction therefore holds the complete job before the first allocation, including an oversize description on a later currency. It does not create another validation framework or a new serialization path.

The bound follows the existing Python writer: **200 Python Unicode code points**. It is not a UTF-8 byte, UTF-16 code-unit or grapheme limit, and this packet makes no assertion about live PayPal API limits. A 200-emoji description survives the native writer literally; 201 emojis receive the review issue. The change introduces no normalization, text clipping or new support for non-string descriptions. Existing admission rules for other fields stay in place.

Removing precisely the three added lines reconstructs every original extractor byte. A separate native AST comparison preserves every top-level node outside `validate`. The serializer, Agent, browser adapters and all other production inputs match their original Git blobs after execution.

## Executed qualification

The runs below are separate receipts. Counts are not added together or relabeled as a full repository pass.

| Native run | Result |
| --- | --- |
| Original actual bridge witness | 1 pass / 1 expected failure; exit 1 |
| Initial frozen regression on original source | 8 methods; 10 assertion failures; exit 1 |
| Two corrected regression methods on original source | 5 assertion failures; exit 1 |
| Complete corrected regression on candidate | 8 methods pass; exit 0 |
| Unchanged original bridge witness on candidate | 2 controls pass; exit 0 |
| Exact inherited invoice-value test file on candidate | 47 pytest cases pass; exit 0 |
| Exact source and AST scope verification | Pass; exit 0 |

The eight maintained methods exercise:

- Literal 199/200-character ASCII, 200-code-point CJK/emoji, quotes, markup-looking text and accents in actual created invoices.
- Oversize supplied model responses and RulesExtractor output, with the original description kept for correction.
- A custom extractor whose reviewed value has no preexisting issues, and the direct builder's own revalidation.
- An oversize USD item after an otherwise valid EUR item, with complete refusal before either new currency allocation.
- Existing invoice, request, sequence, ledger and pending-action preservation across refusal, followed by a successful corrected retry.
- The maintained human-review adapter and the exact affected line-item issue field.

The inherited 47-case test file is unchanged blob `7d2b6487751857f1affeaec63e83fa7609ef5422`. It retains existing amount, quantity, currency, prior-payment, nonfinite and whole-job allocation boundaries.

### Retained receiver corrections and preflight failure

Before candidate creation, source review found that one still-unreached assertion in the initial regression expected a nonexistent `result.extraction` field. The current Agent refusal returns issues without that field. The corrected test checks the actual LLM extraction and unchanged supplied input instead.

The mixed-currency fixture was also corrected before candidate creation: `split_by_currency` sorts currencies, so valid EUR followed by oversize USD is the actual later-currency boundary. The original fixture used oversize EUR and valid USD. Both original test text and original run remain preserved, and only the two changed methods were replayed against untouched source. The initial unused Decimal import was removed at the same time. The final candidate received the complete corrected eight-method suite.

Primary Python 3.12.14 has no pytest. Its original `ModuleNotFoundError` occurred before any retained test started and remains in the archive. The 47-case run then used the previously qualified, read-only runtime at `/workspace/scratch/20b27c2ea29e/workers/estate-production/venv/bin/python`: Python 3.12.14 / pytest 9.1.1. It used `-B`, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-p no:cacheprovider` and a caller-owned temporary directory. No dependency installation or owner-environment write was performed.

## Envelope and replay

`author-receiving.json` is a UTF-8 JSON envelope containing a gzip/base64 payload. It records both compressed and decoded byte counts and SHA-256 identities. The decoded document contains:

- `metadata`, exact original/candidate/test identities and the explicit oracle correction.
- `files`: all seven original native modules in `source-inputs.json`, candidate extractor/test, initial test version, original bridge witness, source verifier, and the exact inherited test/configuration inputs.
- `raw_receipts`: every original and candidate process result, arguments, exit code, stdout/stderr and the failed pytest preflight.

Decode and verify it with an existing Python installation:

```python
import base64, gzip, hashlib, json
from pathlib import Path

envelope = json.loads(Path("author-receiving.json").read_text())
packed = base64.b64decode(envelope["data"], validate=True)
assert len(packed) == envelope["gzip_bytes"]
assert hashlib.sha256(packed).hexdigest() == envelope["gzip_sha256"]
raw = gzip.decompress(packed)
assert len(raw) == envelope["decoded_bytes"]
assert hashlib.sha256(raw).hexdigest() == envelope["decoded_sha256"]
receipt = json.loads(raw)
Path("decoded-receiving.json").write_bytes(raw)
```

For execution, materialize `source-inputs.json`'s exact `files` under separate `baseline/` and `candidate/` directories. Then materialize the archive's `files` entries, whose `candidate/` entries supply the frozen correction and tests. Put the preserved initial test version at `baseline/tests/test_description_admission.py` for the original eight-method run. The corrected two-method original run uses the final test file against the original module closure; that distinction is retained in the raw arguments.

The recorded commands use Python 3.12.14:

```sh
python -B original-probe.py baseline
python -B original-probe.py candidate
```

Run `python -B -m unittest discover -s tests -p test_description_admission.py -v` from the selected source root. The retained test command is `python -B -m pytest -q -p no:cacheprovider --basetemp /your/isolated/temp tests/test_invoice_value_boundaries.py` from the candidate root, with the environment settings above. The supplied `verify-source.py` checks the two reconstructed module closures and exact three-line inverse.

## Ownership and integration

The exact reservation preceded production edits:

- [Established invoice-admission thread, #19/comment6069376244](https://github.com/Jacob-Met/ledgerly/pull/19#issuecomment-6069376244).
- [Central HAMON #140/comment6069379031](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6069379031).
- [Shared extractor notice, #57/comment6069381258](https://github.com/Jacob-Met/ledgerly/issues/57#issuecomment-6069381258).

All three comments were read back exactly. Discovery covered 57 current project issue/PR bodies and 692 central comments. This records bounded public ownership evidence, not a native runtime lease.

#50 retains table segmentation, #57 retains its private LLM shape helper and LLMExtractor changes, #52/#54 retains draft-interruption handling, and #55 retains unfinished intake preservation. Their branches, evidence and implementation remain untouched.

All four current Ledgerly workflow definitions were inspected and have no issues/issue_comment trigger. Ordinary coordination comments and unattached immutable Git blobs were the only external writes by this lane. Jacob's Actions hold remains in force: no ref/branch/PR lifecycle, main, workflow, provider or installed-host action occurred. Full repository pytest, frontend build, hosted gates and browser receiving are unrun for this correction. Root's independent receipt and current-tree integration must be attributed separately.
