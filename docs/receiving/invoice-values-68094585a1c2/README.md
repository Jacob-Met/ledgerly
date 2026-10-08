# Invoice values: PR19 receiving

This receives the original invoice-value contribution at `f67e2c4034804f657eccad38887f377f28011e98`, preserving it as an explicit parent alongside main `2ab89fdd65d200355dda381ba7bae82a22e268fc`. All 54 original added paths and all 464 current leaves outside its three production paths remain exact. The owner's branch and original evidence are unchanged.

## Why the receiver correction is needed

The original value-admission change correctly rejects unsupported arithmetic, but `parse_qty` lets that `ValueError` escape for oversized quantities. Real bullet and table input therefore raises instead of producing a reviewable extraction. The receiver catches only the two existing `_dec` calls in that function and returns the existing unknown-quantity result. Unsupported jobs then reach review before any invoice number, mock request, ledger entry or approval is allocated.

The full original extractor is preserved outside `parse_qty`. Current Agent and PayPal source are restored byte for byte when the original PR19 create/build functions and their imports are removed. Current webhook admission, approval-outcome handling, receipt terms, queued previews and the browser overdue-scan change and the newer retained invoice-details contribution remain present.

Owner coordination and original negative controls are recorded on [PR19's receiving finding](https://github.com/Jacob-Met/ledgerly/pull/19#issuecomment-6060078538) and [the exact receiver patch](https://github.com/Jacob-Met/ledgerly/pull/19#issuecomment-6060630820). This receiving route preserves authorship and does not infer that the owner abandoned the contribution.

## Local qualification on the recorded 2d composition

The following results apply to main `2d3a90a9aa794d849ec54ca9d32a720959ddc5db` plus the original contribution and receiver correction. Current main has since added the invoice-details consumer without changing any of the three core source inputs. Those new source paths are preserved exactly and require the actual receiving PR hosted gate. See [publication-current.json](publication-current.json) for the current source comparison and limits.

- Complete recorded native suite: **276 passed; 85 subtests passed**.
- Recorded unchanged Node/Vitest suite with real Pyodide 0.29.3: **34 tests in six files passed**, including the six current native overdue-scan controls inside Pyodide.
- Final maintained receiver modules: **13 tests and 22 subtests passed**; the preserved standalone quantity entrypoint also passes all 10 methods.
- All 72 selected runtime files are pinned; all 18 staged Python/fixture copies match their sources; nine package/runtime input hashes remain unchanged.

The quantity receiver becomes `tests/test_invoice_quantity_receiving.py`; the webhook/approval lifecycle receiver becomes `tests/test_webhook_approval_composition.py`. Their original control bodies are unchanged. Only source discovery and module context text are adapted for maintained pytest discovery. The two final module-docstring corrections have identical executable AST to the complete native run and a separate focused final pass.

`qualification.json` retains exact commands, raw current outputs, source-tree attribution and limits. `source-pins.json` identifies every selected current input and the exact three production outputs. This receiving documentation has separate new paths, preserving the original author's evidence. The complete immutable [receiving-packet.tar.gz](receiving-packet.tar.gz) (379,886 bytes; SHA-256 `3606a1c13e5ecad7c5af56dbca4482b390dc4496c921d602a0531b6ec3a67f25`) preserves the exact 106-member source, raw logs, commands and historical qualification packet. Its original README and timestamps remain unchanged inside the archive.

## Receiving commands and limits

From a complete receiving checkout, use the existing native CI command `python -m pytest -q` and browser `npm test` / `npm run build` commands. The standalone native quantity receiver remains available with `python -B tests/test_invoice_quantity_receiving.py --source-root /absolute/path/to/checkout`.

This local Node qualification used exact small Python/fixture staging and invoked the existing Vitest runner directly. Node loaded the verified npm Pyodide runtime in place because temporary storage could not hold another browser-runtime copy. It does not claim standard npm staging, audit, production build or a new rendered-browser run. The receiving PR's hosted gates must qualify those standard commands on its actual final tree. All provider effects here use SandboxMock. A normal merge may activate the existing Pages demo deployment; this receiving contribution adds no live provider configuration.
