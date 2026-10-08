# Invoice correction verification — 2026-10-08

Contribution `chatgpt-566d51f04b31-production`, coordinated at [Ledgerly issue #5](https://github.com/Jacob-Met/ledgerly/issues/5). The receiving base is `main` commit `d4d3802b7f5ccd78795d91159d907b08cb3e978f`, tree `6905f7a9be35fd5287f4855485d99cc9ed50954e`.

## Result and boundary

A visitor can correct an otherwise blocked invoice, check the revised values with the real Python validator, then create a source-bound, single-use sandbox draft. Original extraction values and issues remain visible. Every resulting send still requires a separate visitor approval. The core `ledgerly/` files, fixtures, dependencies, provider client and workflows are unchanged.

This verification exercised the built local demo using fictional fixtures. It made no PayPal request, sent no client message and moved no money. Source publication, CI, integration and any subsequent Pages deployment are distinct states recorded on the receiving pull request and issue; these local results do not establish them.

## Checks completed

| Receiving boundary | Evidence |
| --- | --- |
| Original Python core | 52 tests passed before and after the browser changes, using Python 3.13.7 and pytest 9.1.1. |
| Original Pyodide workflow | Both existing tests passed on the base and candidate, including approval, payment, webhook replay and overdue reminders. |
| New correction workflow | Eight tests ran through the actual Pyodide 0.29.3 interpreter. All passed on the candidate: missing recipient; explicit confirmation; invalid values; numeric refusal; one-use/source-bound revision; invalidation after analysis, failed correction or reset; separate currency totals; and zero-decimal currency/ambiguous-quantity controls. |
| Build | TypeScript and Vite 8.3.3 production build passed with Node 26.3.0. The existing Pyodide Node-module externalization warnings were also present on the unmodified base. |
| Actual browser | Chrome 154.0.8037.98 passed `tools/check_review_browser.py` at desktop 1440×1000 and phone 390×844. The check uses the production `dist/` build and actual Pyodide worker. |
| Browser effects | Both viewports corrected the missing recipient; refused quantity 0; retained original extraction issues; rendered literal edited text; invalidated checked values after edits; added/removed a line without losing other edits; produced one reviewed draft; required separate approval; invalidated on source changes; and retained the ordinary draft button's one-use behavior. |
| Browser network/rendering | No off-origin request was attempted, no page error occurred and neither viewport had horizontal overflow. The check blocked every off-origin request. |

## Retained negative evidence

The new eight-test correction suite was first run against the unchanged base bridge. Six tests failed because the correction action did not exist; two rejection controls passed. Both original Pyodide tests stayed green. Raw baseline log SHA-256: `2e9ebcda792665e87cddbd4ab45d0dd1f0827504d7fe085a911745c78934e91b`.

The first candidate run exposed an incorrect test expectation: the existing public ledger snapshot does not export `due_days`. The test now checks the actual sent invoice's `due_on` against the demo date after selecting 0 days. Initial candidate log SHA-256: `4a6b452fe0649e8910afcf2c492006438dfabc9181785e677e71971e8c5feb47`.

The first build rejected direct iteration over `NodeList` under the repository's TypeScript library settings. `Array.from` now preserves the current configuration. Initial build log SHA-256: `cb8fa6d0f44f210a54f4decd5d2408cfb94ec18c0a2950cc79be3ec364e987b1`.

The first Chrome walkthrough found that the payment-term hint became part of the input's accessible name. The form now exposes a concise name and a separate description through `aria-labelledby` and `aria-describedby`; the exact-label interaction passes. Initial browser log SHA-256: `c197c1e8235c6d4f8a43810b4e6fed259def9badb99dd6ed7489a66e5e24fd35`.

Raw logs and final screenshots remain in the author's native evidence directory `hamon-work-ledgerly-566d51f04b31-evidence`. The final browser JSON SHA-256 is `842644d1066b2fde995ef15a184537ba18caf4668fdf9d0b2c7b8f08a6bad684`. Final screenshots: desktop `128f3124996e4a620c09bbfb66d1d7f2ae07ee1b1a9f6717b28a1e78e947029d`, phone `daf6d9bc9fc88d1e85608abd92c9bd7e0e9ca9131801b4f6d7b40b4bb98e16e3`.

## Independent receiving

An independent worker reconstructed the twelve application/documentation/test files over the pinned base in `hamon-ledgerly-receive-20261008-566d51f04b31`, verified every original core blob was unchanged, reran the ten Pyodide cases and production build, and ran three separate native Python checks. Those checks covered caller-field mutation after validation, exact original issue retention, corrected draft custody with the send still blocked, bad-token admission with zero effects, and extractor/revision cleanup after an injected draft exception. No blocking source finding was reported. The receiving manifest pins the twelve files; publication must match those pins before this acceptance is applied to a commit.

## Replay

Run `npm ci`, `npm test` and `npm run build` in `web-demo/`. Serve `web-demo/dist/` on a loopback HTTP origin, then run the browser checker as described in `web-demo/README.md`. It writes a fresh receipt and screenshots to an explicit output directory. All test input is fictional and no production account is needed.
