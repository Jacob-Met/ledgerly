# Independent invoice-details receiving

Disposition: **accept the corrected source within this review's scope**. The owner still supplies final native application receiving and normal source integration. No production source was edited by this reviewer.

## Source boundary

The complete projection, renderer, CSS, bridge snapshot hook, browser staging/Worker admission and main-page integration were read. The owner's selected 38-file native capture at `bf045d48b556443ca93516f00fcd00740b571d47` / tree `f5921f24bb1a07f17eca28db8d811653c386b4a1` was independently checked byte-for-byte against its SHA-256 and Git-blob manifest. That capture composes actual upstream `5493205cd69a32be75ed2f7dfc669b122efe5563`; it is a selected-source capture, not a complete clone.

The accepted final renderer is SHA-256 `db7a572da2d00bbddb230efd66931f5732160c67ab4cd1b5ae1262e39e8755ff`, Git blob `3de02706a97eab7c1310f520a26e40e3066f1bfd`. It is a narrow owner-authored correction layered on the frozen native capture. A later native/public commit pin must be mapped separately; this review does not invent one.

The initial manifest deliberately remains unchanged. It records the first source actually read: the f044-era Agent with the already-applied owner mobile class/CSS correction. It is not evidence of reviewing the earlier failing mobile layout. The actual authenticated current-parent `main.ts` blob `866edc4498ebd933819076a42846c1ad7c85e13f` was separately compared to the capture. `actual-parent-main.diff` shows only the new inspector import/instance, availability hooks, card class and rendering hooks; all existing approval, correction, payment, reset and unavailable-session handlers remain intact.

## Static findings

- `snapshot_invoice_details` visits only the displayed ledger identities. It requires matching retained-record identity and deep-copies an explicit field list; it adds no provider operation or mutation. Nested original monetary strings and the provider's own currencies remain unchanged.
- The renderer requires one exact matching row and matching record ID. Missing, malformed or duplicate identity does not fall back to another invoice, pending approval or later analysis. Missing values remain visibly unavailable rather than invented zeroes.
- All imported text, identifiers and monetary representations pass through escaping before HTML insertion. Literal records create no action controls. Native table captions, column headings and focusable scroll regions retain the read-only interpretation.
- Busy and inactive snapshots are explicitly labeled. Restart/reset remain under existing handlers. Inspector markup adds no storage, upload, network request, account operation or payable invoice semantics.
- The current owner's Agent webhook delta was read in full. It refreshes the current invoice before recording accepted event identity; the new projection remains a synchronous read of the already-retained mock after dispatch. The owner separately qualifies its real payment/replay composition.
- The scoped mobile class/min-width correction and final `aria-disabled="false"` on the read-only disclosure were reviewed. The latter contains no payment/approval buttons and does not change their disabled state. Actual mobile and AX verification remains attributed to the owner's native browser work.

## Reproduced defect and exact correction

`createInvoiceDetailsView` initially tracked open IDs only through `toggle` events. Browsers update `details.open` immediately and deliver `toggle` later. A snapshot render in between used the old set: a just-opened panel closed again, while a just-closed panel reopened.

The independent receiver uses actual Chromium 153.0.8010.0, the exact production renderer with TypeScript types stripped by Node 24.19.0, native disclosure clicks and the same before-render/markup/after-render/availability order as the page. Synthetic invoice data is confined to an isolated DOM. No Pyodide, full app, native-host, provider or layout execution is claimed here.

| Control | Original 5c579 renderer | Corrected db7a renderer |
|---|---|---|
| Open, redraw before queued toggle | Failed: open became closed | Passed: stayed open |
| Close, redraw before queued toggle | Failed: closed became open | Passed: stayed closed |
| Settled toggle; remove and reintroduce identity | Passed | Passed |

Focus restoration and the updated snapshot text passed in both failing cases, distinguishing the state defect from startup or redraw failure. There were no page errors or external request attempts. Node's type-stripping warning is retained in stderr and did not affect either result.

The owner now reads the attached DOM's current open states in `beforeRender`, then prunes removed identities. The exact original receiver was rerun unchanged: **1 pass / 2 fail before, 3 pass / 0 fail after**. The original source, reports and logs are immutable. `renderer-correction.diff` contains the complete accepted correction, including the separately owner-verified accessibility override.

## Reproduction

With Node 24, the existing Playwright dependency located by `CODEX_PRIMARY_RUNTIME_NODE_MODULES`, and Chromium available:

```sh
node check_disclosure_refresh.mjs invoice-details-reviewed.ts NEW-negative-report.json /path/to/chromium
node check_disclosure_refresh.mjs invoice-details-corrected.ts NEW-positive-report.json /path/to/chromium
```

Each command refuses to overwrite its report. The first returns 1 for the known two failures; the second returns 0. Original exact commands, hashes, browser executable pin and all case observations are retained beside this review. No screenshots, synthetic database, browser profile, dependency copy or whole repository are required.

## Handoff

Preserve this packet unchanged in the native/source receiving evidence. Pin the final source/public head with a separate small mapping once available. If later work changes these reviewed production bytes, qualify that concrete delta rather than relabeling this source or repeating the owner's whole suites. The reviewer is available for an exact-head COMMENT; this is not a separate-account approval or an independent claim of the owner's native browser results.
