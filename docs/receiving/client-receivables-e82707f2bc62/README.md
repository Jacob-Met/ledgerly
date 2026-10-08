# Client receivables receiving — Ledgerly #39

This change answers a concrete sandbox question: which client still owes money,
in which currency, and is each invoice overdue, due today, due later or undated?
The board reads the same accepted native snapshot already displayed by the
ledger. It adds no Python, provider, send, payment, refresh or approval operation.

## Source and ownership

- Claim: https://github.com/Jacob-Met/ledgerly/issues/39
- Original native reproduction: commit
  `b9c24ace6b57a17215a53c50b674bd187d13f8ed`.
- First browser composition: `8a122cf637610880e23716823a5eb71d78187391`,
  including the completed standalone invoice-record contribution.
- Independently received native dependency:
  `1ebfaf093b4d992799901efec0ab05957be35eb1`,
  tree `d1d6039a649aee46e459a3502cb2058013cbda4f`.
  Its invoice-value admission changes remain untouched.
- Publication base: `fba278f552e868ad2b94b7f1dc309eed6f1e8514`,
  tree `ddb2360a65b646a281969fea1abbb3238c154340`. The later send-approval
  freshness contribution is also preserved. The actual composed PR gates
  qualify this last dependency update; the earlier independent receipt keeps
  its original 1eb source identity.
- Frozen projector/controller: Git blob
  `c2d4f6bd9206d7199fe053bd45e2e8df2ad96ad9`, SHA-256
  `e40648104202ad83682a4e5d76f4c6332d37e5d50e3c834d15dd40e3aa826e68`.

The maintained entrypoint gains five additive lines: two imports, one explicit
DOM-controller binding, one availability update and one snapshot update. The
HTML gains one independent section. The existing recovery test only imports and
binds that real controller in its existing VM context; its assertions and fake
Worker remain unchanged. Reverse-addition proofs recover every prior byte of
the entrypoint, HTML, README and test harness.

## Money, identity and time contract

Only positive balances with native status SENT, UNPAID, PARTIALLY_PAID or
PAYMENT_PENDING enter the view. Other statuses keep their literal exclusion
reason. An open zero balance has the distinct ZERO_BALANCE reason. The original
ledger retains every invoice.

Exact recorded billing emails identify clients; case and whitespace are not
normalized and display names do not merge identities. Decimal strings are
summed with integer coefficients and scales. There is no floating-point money
arithmetic, currency conversion, currency rounding or inferred two-decimal
format. Invoice rows retain their original strings; totals preserve the
greatest fractional scale among included values.

Dates are validated ISO calendar dates. Classification uses the native sandbox
clock and a UTC calendar-day difference. A null due date is undated. Duplicated
invoice identities, malformed rows, negative/nonfinite balances or invalid
dates refuse the complete projection rather than exposing partial totals.

## Original and author evidence

`author-receiving.zip` contains the exact 16-command native reproduction,
six-invoice snapshot, source capsule/pins, frozen source and tests, all author
case results and the genuine local Chrome preflight refusal. Its member
manifest gives the size and SHA-256 of each preserved file.

The original source completes the native workflow but has no receivables
module; the original module-import absence is recorded as such, not as twelve
executed assertion failures. The final author test has 12 passing cases on the
unchanged frozen projector/controller.

The first candidate run passed 11 cases and exposed an overconstrained expected
display scale. A second attempted fixture correction incorrectly inferred the
partial-payment scale and also passed 11 cases. Both sources and raw failures
are retained. Inspection of the literal native snapshot established North USD
strings `0.1`/`0.2`, North EUR `12.3`, and South USD
`100.50`. The final author test differs from the original only in the
North expected totals `0.30` → `0.3` and `12.30` → `12.3`;
the original South and all-client assertions were restored. No production
change was made to satisfy those formatting assumptions.

Independent receiving uses its own real command pipeline, data and assertions.
Its portable Node test and Python fixture are in `web-demo/tests`; the
separate peer packet preserves its original baseline, expectation corrections
and exact current-source verdict.

The final independent replay passed all five cases with zero failures or skips
against the separate current composition containing all three newly integrated
monetary-core files. Its distinct native fixture executes 18 real commands and
retains seven invoices across clients, currencies, leap day and payment states.
The original source had passed that native setup but lacked the new projection.
The peer archive preserves all four receiving phases and its two explicitly
recorded expectation corrections; no production change was requested.

## Real browser gate

The existing unit, Python, CSV, invoice-record and Pages workflows are preserved.
The separate `receivables-browser.yml` gate runs the independent native
receiver and builds the actual app with the existing locked dependencies. It
requires the installed system Chrome and Node's built-in WebSocket; it downloads
no browser and adds no product dependency.

The upstream [Ubuntu 24.04 runner manifest](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)
lists Chrome and Node. [Node 22 documentation](https://nodejs.org/download/release/v22.23.3/docs/api/globals.html#class-websocket)
documents the built-in WebSocket. The gate checks actual available binaries and
records their versions, actual checkout commit/tree, source hashes and complete
build hashes rather than assuming those manifest versions.

From the repository root, with the declared app dependencies installed and the
production build prepared:

```bash
node --experimental-strip-types --test web-demo/tests/receivables-peer.mjs
node web-demo/tools/check_receivables_browser.mjs \
  --project . --build web-demo/dist --browser /path/to/chrome \
  --output /path/to/new-receivables-evidence
```

The browser receiver drives the actual page and native Pyodide Worker through
drafts, explicit approvals, partial/full payments and a clock change. It checks
visible client/currency totals, literal corrected names, keyboard-only client
and due-state filters, unchanged original panels and Worker requests, 390px
overflow, a held genuine reply, an explicitly corrupted copy of one transport
balance, terminal session loss, restart and a populated reset. The latter three
are authored failure controls, not observed provider failures.

The driver records real DOM projections, exact native snapshots and actual
Chrome screenshots. CI retains a bounded, checksummed evidence bundle and raw
artifacts. Local preflight reported Chrome ENOENT with zero executed browser
checks; that receipt remains a refusal. Hosted execution is required before
integration. Screenshot generation alone is not a claim of direct visual
inspection.

