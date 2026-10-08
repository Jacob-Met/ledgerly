# Browser engine recovery qualification

The receiving source was first `Jacob-Met/ledgerly` production commit
`d4d3802b7f5ccd78795d91159d907b08cb3e978f`. The final contribution composes the
bounded recovery hooks over the separately published invoice-review commit
`2528de8b66d2b6ab0bed824e3b6ad115052840e6`. The original invoice-review commit
remains the integration parent. No work was written into its author's checkout.

The final published source commit is
`537eb5d587d08641c1e96150e9c0daee172366e7`, with tree
`04bd5cd7b2fc4a384d9a9553e49e4e37c4392df2`. It is byte-identical to the locally
qualified source commit `e47aef7838cfdb40454cfa5f13603dc05e5ec5f2`. Its parent
`84ac59dbcd20b96c8baf846a03f574840ea174f8` is the first composed recovery source,
which directly retains the invoice-review author's commit as its parent. The GitHub connector published the
source after the isolated native checkout lacked a noninteractive HTTPS write
credential. Public Git fetch confirmed the complete tree equality.
`source-manifest.json` records both identities, all six changed/added source and
test hashes, every unchanged parent blob, and the retained artifact hashes.

## Reproduced failures and receiving controls

The four original source controls fail against exact production source:
terminal startup never settles; a terminal action leaves the old ledger active;
an initialization refusal is treated as success; and a rejected startup promise
prevents a later explicit retry. `baseline-hooks.txt` preserves that negative
run. `source-hooks-v1.ts` archives its exact receiver; it originally lived at
`web-demo/tests/engine-recovery.test.ts`.
The transcript omits one redundant final newline; the manifest records the
original byte hash and the exact reversible normalization. No test output or
failure value was removed.

The first recovery candidate passes those controls, 11 lifecycle/loader checks
and the two existing real Python/Pyodide workflows. `candidate-validation.txt`
records the 17 passing tests, production build and audit with zero reported
vulnerabilities. `python-core.txt` records the unchanged native core's 52 passes.
The runtime was Node 26.3.0, Python 3.13.7, Pyodide 0.29.3, TypeScript 5.9.3,
Vite 8.3.3 and Vitest 5.0.3 on macOS ARM64.

The composed candidate's `composed-validation.txt` records 26 passing tests,
including all eight original invoice-review controls and a new actual-source
case for retaining corrections, invalidating the old revision, explicitly
reopening analysis and checking a new revision before a one-use draft.
TypeScript and Vite pass. Existing Python/review modules and the lockfile match
the invoice-review parent byte for byte.

The final `composed-final-validation.txt` again records all 26 tests and the
TypeScript/Vite build passing after the later marker correction below. The
new focused expectation fails on the first composed source in
`review-marker-negative.txt` before that one-line application correction.

Both published source heads pass the existing GitHub Actions workflow. The
initial source run is
[37756919054](https://github.com/Jacob-Met/ledgerly/actions/runs/37756919054);
the final source run is
[37760130362](https://github.com/Jacob-Met/ledgerly/actions/runs/37760130362).
`hosted-source-ci.json` and `hosted-final-source-ci.json` retain the connector
results queried at the exact corresponding commits. Later evidence-only
commits are separate publication events.

## Independent browser evidence

The independent root receiver uses Chrome 154.0.8037.98, the actual Vite build
and its actual self-hosted Pyodide runtime. Failure injection occurs only in a
disposable loopback server and its worker script. Inputs are fictional; the
receipts record zero external invoice calls and no off-origin browser requests.

- `independent-browser/baseline-results.json`: all four receiving cases fail on
  the original production source.
- `independent-browser/candidate-v1-results.json`: the same four functional
  cases pass on the first recovery candidate. The associated worker/client
  source pins are retained in the manifest.
- `independent-browser/recovery-browser-v1.mjs`: the exact driver shared by
  those negative and positive runs.
- `independent-browser/candidate-v2-results.json`: the affected in-flight
  recovery case passes after the visual correction below, with the additional
  ready-message assertion in `recovery-browser-v2.mjs`.
- `independent-browser/final-general-results.json`: all four general cases
  pass on the final composed source.
- `independent-browser/final-review-results.json`: the fifth case passes with
  typed corrections retained across a terminal error and empty restart, the old
  confirmation invalidated, and only `init` sent before the visitor checks again.
  That explicit check sends fresh `analyze` and `review`; one draft is followed
  by a separate approval, and the completed recovery marker is absent.
- `independent-browser/recovery-browser-v6.mjs`: the exact driver for those final
  two runs. Both bind app asset `index-CjlcxCVy.js` with SHA-256
  `366d982ca9053e42f67162896f30d9cf0d36d8a22e25f66ae0cf4e801d811f18`
  and confirm its bytes remained unchanged during receiving.

The final screenshot is `independent-browser/final-retained-review-recovery.png`.
[The retained harness limitations](independent-browser/harness-limitations.md)
separate the v3/v5 counter bugs and v4 launch failure from product behavior;
the actual failed receipts were not rewritten as passes.

`prior-source/` retains the exact earlier main/worker snapshots used for these
standalone runs. The two helper modules are unchanged in the composed source.
Together with the original production checkout, these snapshots preserve the
prior receiving inputs rather than implying the earlier receipts qualified the
later correction-form composition.

The drivers accept a built `dist` directory and a fresh output directory. Set
`PUPPETEER_MODULE` to an installed `puppeteer-core` module and `CHROME` to the
Chrome executable. For example, from `web-demo/`:

```sh
PUPPETEER_MODULE=/absolute/path/to/puppeteer-core \
CHROME=/absolute/path/to/chrome \
node docs/qualification/engine-recovery-c945953fdeb7/independent-browser/recovery-browser-v1.mjs \
  dist /absolute/path/to/new-receipt candidate
```

Use `baseline` for the unchanged production build. The baseline mode records
failed receiving outcomes without pretending that those outcomes passed.

For the final v6 receiver, the default `all` selection runs the four general
cases. Invoke it a second time with `RECOVERY_CASE=retained-review-recovery`
for the fifth case, using another fresh output directory:

```sh
PUPPETEER_MODULE=/absolute/path/to/puppeteer-core \
CHROME=/absolute/path/to/chrome \
node docs/qualification/engine-recovery-c945953fdeb7/independent-browser/recovery-browser-v6.mjs \
  dist /absolute/path/to/general-receipt candidate

RECOVERY_CASE=retained-review-recovery \
PUPPETEER_MODULE=/absolute/path/to/puppeteer-core \
CHROME=/absolute/path/to/chrome \
node docs/qualification/engine-recovery-c945953fdeb7/independent-browser/recovery-browser-v6.mjs \
  dist /absolute/path/to/review-receipt candidate
```

## Retained corrections and limits

The first source build used a direct `NodeList` iteration that the repository's
existing TypeScript library configuration does not support. It was changed to
`NodeList.forEach`; the next build passed without changing TypeScript settings.
The composed invoice-review source independently uses its author's existing
`Array.from` traversal. Pyodide's existing browser-external module warnings
remain visible in the transcripts.

The first independent browser harness used Puppeteer request interception and
stalled nested worker resource loading. The receiver moved failure injection
into the fixture server and completed the actual paths. That initial stall is
a harness limitation, not a product failure; the preserved successful/negative
receipts identify the corrected driver's exact hash.

Visual review of the first passing candidate found that its analysis panel
still said the engine was unavailable after a successful restart. The recovery
message now has a dedicated marker that changes to ready after initialization.
`candidate-v1-in-flight-session-recovery.png` retains the earlier view;
`candidate-v2-in-flight-session-recovery.png` records the correction. The
functional 4/4 receipt was not rewritten to claim this visual check existed.

The invoice-review composition preserves its live correction form and clears
the prior checked revision and confirmation. Restart sends only `init`.
The next explicit human check performs fresh native `analyze` then `review`,
preserving typed values and the separate approval requirement. No recovery
timer or automatic invoice action replay was added.

A later visual check found that the temporary recovery instruction stayed after
retained corrections had already been validated. The final source removes only
that marker after a valid Python review. Its focused expectation fails on
`84ac59d` and passes on the final source; the independent v6 receiver also requires
the marker to be absent. The correction form and typed fields are preserved.

## Existing delivery route

The existing `.github/workflows/pages.yml` publishes `web-demo/dist` after a
matching push to `main`, with Node 22 and the repository's own build command.
The inspected `github-pages` environment permits branch `main`; its API response
contains only that branch policy, with no reviewer or timer protection rule.
No publishing configuration was changed.

`delivery/gate-readback.json` records the exact workflow source inspected and
the current environment/branch policy. It also records successful Pages run
[37757410432](https://github.com/Jacob-Met/ledgerly/actions/runs/37757410432)
for `1871942ecb19aa9756bb36b380795bc6c7bf238d`, before this PR was merged.
`delivery/before-merge.json` records HTTP 200 for
<https://jacobmetoyer.com/ledgerly/> and its observed JS, CSS, worker and Python
review assets. That served JS includes invoice review and does not yet include
this recovery change. The anonymous Pages settings API returned 404; that
visibility limit does not contradict the successful deployment and serving
readback. The source PR and its later deployment remain separate checks.

These are implementation and receiving records. They do not, by themselves,
establish a merge, Pages deployment, real PayPal effect or production outage.
