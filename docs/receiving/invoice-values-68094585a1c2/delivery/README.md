# Ledgerly invoice-value receiving: delivered merge evidence

This evidence-only branch preserves the sealed postmerge packet for [receiving PR #38](https://github.com/Jacob-Met/ledgerly/pull/38), which integrates the original author's [PR #19](https://github.com/Jacob-Met/ledgerly/pull/19) through its unchanged f67e2c4034804f657eccad38887f377f28011e98 ancestry.

The source being received is merge **1ebfaf093b4d992799901efec0ab05957be35eb1**, tree **d1d6039a649aee46e459a3502cb2058013cbda4f** (675 verified leaves). This branch adds only this index, the exact manifest, and the sealed archive; it changes no source and opens no pull request.

## Sealed packet

- [postmerge-evidence.tar.gz](postmerge-evidence.tar.gz): 839,776 bytes; SHA-256 `2b7e3b239deee04f7e02c62f42394c7bab252d576409657072d534cfee5b8607`; Git blob `0aec6f593486ec87470a4a3d852a46f6113a1ec6`.
- [artifact-manifest.json](artifact-manifest.json): exact member byte counts and SHA-256/Git identities; 2,222 bytes; SHA-256 `f3cc384aead44c601c1ddac53c23344e37ffe83c4f3e43d52584d01db27203fc`.

The archive contains the full source map, receiving receipt, test-only composition record, raw postmerge Python/browser/invoice-record/Pages logs, the anonymous public delivery receipt, its verification script, and this exact manifest. Historical qualification and the original failing setup remain explicitly distinguished from the final current-source gates.

## Actual delivery

Postmerge runs [37797293486](https://github.com/Jacob-Met/ledgerly/actions/runs/37797293486), [37797293732](https://github.com/Jacob-Met/ledgerly/actions/runs/37797293732), and [37797293418](https://github.com/Jacob-Met/ledgerly/actions/runs/37797293418) checked out that exact merge. They passed 297 native tests with 118 subtests, 88 browser-engine tests, dependency audit/build, 7 CSV browser controls with 8 downloads, and 8 invoice-record browser controls with 14 artifacts. The Pages job reported successful deployment of the same commit at 2026-10-08T15:02:10.3985126Z.

Anonymous HTTP receiving at [the public application](https://jacobmetoyer.com/ledgerly/) from 15:04:50.032Z to 15:04:52.399Z on 2026-10-08 verified HTTP 200 and exact postmerge-build hashes for all 16 requested index, compiled, Pyodide, and native Python assets. Detailed URLs, hashes, controls, and limitations are in the packet and [existing receiving receipt](https://github.com/Jacob-Met/ledgerly/pull/38#issuecomment-6062942962).
