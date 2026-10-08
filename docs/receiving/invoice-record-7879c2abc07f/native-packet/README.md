# Native standalone invoice record receiving

This evidence branch preserves the actual font-limited current-payment composition of [Ledgerly PR35](https://github.com/Jacob-Met/ledgerly/pull/35). It is not a claim that every Japanese glyph printed correctly in the original Ubuntu font environment.

The complete source checkout was 01fc8a6b9677160ec9417845c492af74d741640d, tree f1b25a10d4db0c651a798c79346f0705deae25dc, composing head 43bc2a7d7614dd61d0197835d454487769e9cd1b onto main b9c24ace6b57a17215a53c50b674bd187d13f8ed. [Run 37792087248](https://github.com/Jacob-Met/ledgerly/actions/runs/37792087248/job/113361851887) passed all eight actual browser groups and emitted the bounded fixture packet. The paired maintained run passed 205 Python tests plus 96 subtests, 88 frontend tests, audit/build, and the existing CSV receiving.

All 224 numbered native chunks, the 686960-byte payload SHA256, all twelve member sizes/SHA256 values, and their native Git blob identities were independently checked. The exact files below were decoded from that actual log. They were not reconstructed from source or generated again for this branch.

- [Index and complete source/file identities](index.json)
- [Independent PDF receiving and complete extracted texts](independent-print-receiving.json)
- [Paid USD standalone HTML](fixtures/font-limited-current-base/paid-usd-record.html)
- [Paid USD actual two-page PDF](fixtures/font-limited-current-base/paid-usd-record-1280.pdf)
- [Literal JPY standalone HTML](fixtures/font-limited-current-base/literal-jpy-record.html)
- [Literal JPY actual font-limited two-page PDF](fixtures/font-limited-current-base/literal-jpy-record-390.pdf)
- [Actual receiving report](fixtures/font-limited-current-base/receiving-report.json)

The original missing-action run, first print-visibility probe failure, corrected passing prior-base run, and current-payment run retain all twelve complete browser/engine/Python logs under logs/. The original phase boundaries remain in the parent receiving directory and source history.

Direct receiving found a concrete environment limitation. The four actual viewport PNGs have clear sandbox wording, timestamps, print controls and summary layout, but the installed Linux font displays Japanese as missing-glyph boxes. PyMuPDF 1.26.6 and pypdf 6.10.0 both find missing CJK mappings in the actual JPY PDF. The downloaded HTML and real browser DOM preserve the exact original Unicode. The independent reviewer received both USD A4 page images and all 79 expected USD text parts. The full findings and both readers' extracted text are retained without alteration.

The next receiving boundary installs only Ubuntu's standard fonts-noto-cjk in the owned hosted workflow, records the actual package version and selected Japanese font family/path/hash, and repeats the exact production and behavioral checks. No product font embedding, source string replacement or weakened assertion is used. That successor outcome is separate from this preserved packet.

The twelve fixture/report files here exclude browser profiles, download caches, raw session-snapshot JSON and arbitrary environment/source files. The ordinary GitHub artifact retains the other three authored native snapshots; this bounded log packet deliberately contains only the fixed rendered fixtures and report. This branch adds evidence only and preserves every source leaf of the actual head above.
