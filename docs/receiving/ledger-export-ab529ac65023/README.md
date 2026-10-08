# Sandbox ledger CSV receiving

This packet preserves the current state of Ledgerly PR27. The source is qualified; the actual native browser download workflow remains pending because observed Mac capacity crossed the 1 GiB guard.

The export controller and 30 CSV tests are frozen from native commit 268155f6e1af8b41f47732c734d153f78f8a2ddd. The complete published source tree matches the clean native source through 3cef644049254c1fa0fc1798ae6cac418e934141. The maintained real-Chrome receiver is in web-demo/tools/check_ledger_export_browser.py.

## Evidence

- Original production build and candidate TypeScript check passed.
- The initial native suite had 52 passes and four missing-controller VM binding failures. The exact log and the stopped native replay are retained in native/. No assertion was removed.
- [Existing hosted CI](https://github.com/Jacob-Met/ledgerly/actions/runs/37778011219) then checked the real current-main composition: all 56 browser tests, the production build, and 141 Python tests plus 60 subtests passed.
- Full Git tree comparison preserves all 219 unowned current-main leaves and all eight exact contribution file blobs, with no mismatch. The source change includes current main 350868091702d60f3dc340be4a017ba49d99f8a0 and the original contribution as parents.
- [Independent production source review](https://github.com/Jacob-Met/ledgerly/pull/27#issuecomment-6060220272) accepts the actual snapshot/Decimal-string provenance and narrow controller boundary; actual browser acceptance remains separate.

See receiving.json for source pins, command/CI receipts, limitations, and the next acceptance gate. No native browser result, Pages deployment, provider effect, or runtime adoption is claimed here.

## Hosted browser continuation

The next checkpoint composes actual main5493205cd69a32be75ed2f7dfc669b122efe5563, retaining PR26 preview and PR21 webhook source. It runs the maintained receiver in the existing Ubuntu browser-engine job after its normal build. The prior native storage stop and prior qualified composition above remain historical evidence. See browser_ci_plan in receiving.json; no browser pass is claimed until the actual resulting CSV/JSON/screenshots and job status are received.
