# Native invoice record receiving packet

This evidence branch preserves the actual offline sandbox invoice qualification for [PR35](https://github.com/Jacob-Met/ledgerly/pull/35), including the original absence, the narrowly corrected receiver probe, the observed native CJK-font failure, and the accepted successor. The production branch remains separate.

## Accepted current source

Head `de24842a91314fdb89e1b8121d206693fbceb5d3`, tree `cbe35389f27031b0c0162fec7ebfd5e6053d5b0f`, is composed with current payment-owner main `b9c24ace6b57a17215a53c50b674bd187d13f8ed`. Hosted checkout `2ee0920dc2f18af4d05eb5c2e30984d5e6e3cc63` has those two exact parents and the same candidate tree. All 610 current source leaves are preserved on this evidence branch. The previous evidence commit `b6bbaa6f78949b8fd6048d12428561cc9dfd5844` remains a parent; its 25 raw logs, fixtures and independent receipt remain byte-exact.

[Browser run 37793910451](https://github.com/Jacob-Met/ledgerly/actions/runs/37793910451/job/113368229714) passes eight meaningful groups and creates 14 artifacts. It exercises real Python Worker-produced retained invoices, explicit selected-record HTML downloads, direct offline reopening, complete original display comparisons, later app mutation, busy/inactive and missing identity refusal, literal markup/Unicode, download failure/retry, and actual print output. [Maintained run 37793910271](https://github.com/Jacob-Met/ledgerly/actions/runs/37793910271) passes 205 Python tests plus 96 subtests, 88 frontend tests including 12 record cases, audit/build, and the unchanged CSV owner's eight downloads/seven browser groups.

## Actual printed documents received

The [final independent receipt](independent-print-font-qualified.json) binds the exact original PDF bytes to the source, runtime, raw log and bounded bundle. PyMuPDF 1.26.6 receives all 79 expected USD text parts and all 75 JPY parts, including exact 日本語, 海 and emoji. Both actual PDFs have two A4 pages, with no out-of-page text blocks. The independent receiver rasterized and directly inspected all four pages: full items and literal markup, original ledger/provider values, the exact USD 100.25 payment/method/reference, notes and boundary footer remain readable without clipping or overlap.

The secondary pypdf 6.10.0 comparison also receives all expected parts after explicitly documented NFKC for that reader's compatibility radical/ligature extraction. Source HTML and product strings are unchanged and are not normalized. The automated report's narrower PDF-generation-only statement is retained as emitted; the separate independent receipt extends the evidence to actual text and pixels.

The final hosted environment uses Node 22.23.3 and unchanged system Chrome 154.0.8037.97. Its only source change from the font-limited phase is the owned workflow's standard fonts-noto-cjk setup/preflight: version `1:20230817+repack1-3`, matched `Noto Sans CJK JP`, file `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`, SHA256 `b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`. All other 24 runtime inputs and all 31 built assets remain byte-identical. No font is embedded in product source.

## Preserved phases

- `logs/original/`: the original actual product lacks the Save action after two native groups pass.
- `logs/first-candidate/`: actual downloads succeed, then the receiver incorrectly checks the print button's own display instead of its hidden ancestor.
- `logs/corrected-prior-base/`: two visibility-probe substitutions preserve all production bytes and yield eight passing groups.
- `logs/font-limited-current-base/` and `fixtures/font-limited-current-base/`: the current payment owner is preserved; browser gates pass, but direct PDF receiving finds missing CJK glyphs. [The original independent finding](independent-print-receiving.json) remains exact.
- `logs/font-qualified-current-base/` and `fixtures/font-qualified-current-base/`: the font-only environment correction resolves that observed failure with the unchanged production, fixture strings and behavioral receiver.

[index.json](index.json) records every included file's size, SHA256 and native Git blob identity. Both bounded native bundles and all three raw logs for each of the five actual phases are retained. The fixed final bundle contains five authored HTML downloads, four viewport PNGs, two actual PDFs and the emitted report. Its 228 numbered chunks, 697,952 payload bytes and all 12 member hashes were independently verified. The ordinary hosted artifact is ID 11557622154, with ZIP SHA256 `a0f583987933665613423685f5cb80cb91010b0530c9c342a74d0c33cf7625da`.

## Scope

Acceptance covers these authored fixtures and the recorded browser/font environment. No physical printer, operating-system print dialog, universal font coverage or arbitrary document pagination was received. These documents are saved sandbox snapshots; they do not refresh a provider, authorize an action, restore a sandbox, or establish a real payable invoice or payment receipt.

## Integrated main and automatic push receiving

PR35 was normally merged as `8a122cf637610880e23716823a5eb71d78187391` at 2026-10-08T14:53:29Z, with exact base `b9c24ace6b57a17215a53c50b674bd187d13f8ed` and reviewed head `de24842a91314fdb89e1b8121d206693fbceb5d3` as its two parents. Its tree is unchanged `cbe35389f27031b0c0162fec7ebfd5e6053d5b0f`. [The integration receipt](integration-receiving.json) records the exact graph, independent acceptance and actual raw checkout for all four automatic jobs.

[Verify 37796190754](https://github.com/Jacob-Met/ledgerly/actions/runs/37796190754) passes 205 Python tests + 96 subtests, 88 frontend tests, audit/build and the unchanged CSV eight-download/seven-group gate. [Invoice browser 37796190818](https://github.com/Jacob-Met/ledgerly/actions/runs/37796190818) passes all eight groups / 14 artifacts. Its 25 source inputs and 31 built assets match the accepted candidate exactly. All 228 chunks and all 12 members of the new native bundle are decoded and rehashed; their exact bytes remain in the raw browser log. These newly generated PDF copies were not rerasterized; the unchanged qualified source's actual two-reader/four-page acceptance above remains the visual receipt.

The existing [Pages job 37796190781](https://github.com/Jacob-Met/ledgerly/actions/runs/37796190781) also reports a successful automatic deployment for this merge. No manual deployment or live-site browser receiving was performed. Four exact raw logs are appended under `logs/integrated-main/`; all previous evidence remains intact.
