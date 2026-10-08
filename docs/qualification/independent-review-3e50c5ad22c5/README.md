# Ledgerly correction and amount-validation receiving

Independent receiver: `chatgpt-3e50c5ad22c5-production`, 2026-10-08.

## Result

The independently authored correction adapter from
[issue 5](https://github.com/Jacob-Met/ledgerly/issues/5) and numerical validation
from [issue 7](https://github.com/Jacob-Met/ledgerly/issues/7) compose successfully
through Ledgerly's actual native JSON bridge, Agent, RulePlanner, approval gate
and SandboxMock. **All seven independent receiving methods pass** on the exact
combined snapshot, including every currency declared by the repository.

The same final tests with the correction adapter over the original core retain
**four expected assertion failures across two methods**: a subcent unit price,
subcent line total, subcent prior payment, and an invalid EUR part paired with an
otherwise valid USD invoice are all admitted as checked revisions. These are the
existing issue 7 defect family at the new correction entry point. The combined
candidate refuses them during review, before a revision is admitted or any
invoice-related mock request occurs. This demonstrates a concrete benefit of
composing the two contributions without changing either author's implementation.

## Independent checks

The receiver uses `bridge.handle_json`, so inputs and outputs cross the same JSON
boundary as the browser worker. Expected invoice state is checked against actual
SandboxMock invoice bodies and recorded requests, not just the bridge's counters.

| Group | Qualified behavior |
| --- | --- |
| Declared currencies | Each checked total, recipient, quantity and unit price survives the actual draft, provider serialization and ledger; fractional quantities are included |
| Two currencies | Separate checked totals become separate native drafts; rejecting one and approving the other sends only the selected invoice |
| Prior payment | The deposit is inert before explicit approval; approval records exactly the reviewed amount and resulting native balance; a duplicate decision produces no request |
| JSON tampering | Later changes to caller fields and response dictionaries cannot rewrite the captured revision or original extraction |
| Draft refusal | An injected actual provider-draft refusal consumes the revision, clears the temporary human extractor and cannot leak corrected fields into the ordinary path |
| Monetary precision | Subcent prices, resulting amounts and deposits cannot mint a checked revision or start invoice effects |
| Invalid split | A bad currency part prevents the valid part from starting a draft |

`composed-candidate.log` retains all seven passes. `original-core.log` retains the
four expected failures. No model or live provider was called. All provider state
and requests are from the repository's actual in-memory implementation.

## Exact input custody

The receiving base is `d4d3802b7f5ccd78795d91159d907b08cb3e978f`, tree
`6905f7a9be35fd5287f4855485d99cc9ed50954e`.

The issue 5 author's twelve-file local snapshot was copied without modification
from `/workspace/scratch/566d51f04b31/ledgerly-work/web-demo` into an isolated clone.
Every original and copied SHA-256 matched before continuing. The resulting local
snapshot commit is `9faf023162d4825e35b1b2590ef34f3e3876ebe2`.
Only its two Python adapter files are executed by this native receiver; the
complete copied-input manifest is retained in `author-inputs.json`.

The three issue 7 core files were copied from the separate author's uncommitted
snapshot with matching source/copy hashes:

| File | SHA-256 |
| --- | --- |
| `ledgerly/extract.py` | `b064f16bbe7dbb2ce8d7362f7174c5fe712eba57664b056bb93ecf45dd4fc93c` |
| `ledgerly/paypal.py` | `61e86702ffd72eeadb680fb5bddb3e8498427852a9130b064ec7a63ce9ac4dfe` |
| `ledgerly/agent.py` | `be59a4e305ff0dc3874a7070f7b446b06fd11a5d199caa9cdc11039eb0e1c773` |

`core-candidate-inputs.json` retains the base Git blobs and source location.
`composed-candidate.patch` reconstructs the five executed changed Python files
over the exact receiving base. `review-adapter-only.patch` reconstructs the
original-core negative control. `source-custody.json` records all executed source
hashes, receiver hash and exact runtime. The test source is preserved with a
`.source` suffix so documentation does not silently add a new default test gate.

## Replay

Use a separate checkout of the exact base with Python 3.12 or later. The recorded
runtime was CPython 3.12.14 on Linux x86-64. The receiver uses `unittest` from the
standard library and needs no pytest or browser installation.

Set `packet` to this directory in the downloaded review branch. Then, from a
separate base checkout:

```sh
git checkout d4d3802b7f5ccd78795d91159d907b08cb3e978f
git apply --check "$packet/composed-candidate.patch"
git apply "$packet/composed-candidate.patch"
cp "$packet/test_review_receiving.py.source" tests/test_review_receiving.py
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover \
  -s tests -p test_review_receiving.py -v
```

The expected combined result is seven passing methods. To reproduce the retained
negative control, use another clean checkout of the same base and apply
`review-adapter-only.patch` instead. Run the same final test source; four
assertion failures across two methods are expected.

## Ownership and receiving boundary

Both authors retain implementation and publication ownership. The receiver does
not modify their checkouts or branches. Engine recovery (issue 6) and reminder
freshness (issue 8) remain separate active contributions and are not part of this
snapshot. The attempted issue 5 receiving claim comment was rejected by GitHub's
temporary secondary content-creation rate limit; the parent worker received the
scope and exact results through the existing collaboration channel.

This is **native Python composition qualification**. It does not imply Pyodide
0.29.3 acceptance, a browser build, mobile UI review, live-provider behavior or
deployment. Those states should be verified through their receiving owners.
The published review branch adds only this source/evidence packet over the
original base; the five-file candidate is archived as a replay patch rather than
published as a competing production implementation.
