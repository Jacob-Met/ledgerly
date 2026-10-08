# Current receivables composition

The original author packet remains frozen on `fba278f552e868ad2b94b7f1dc309eed6f1e8514`. Main then integrated the client receivables board at `295153cc0c354415c39bcee7d2384412b4fa629f`. This contribution inherits all of that owner's HTML, controller, style and workflow, and preserves the owner's five entry-point additions and README section. Removing those additions from the composed entry point and README reconstructs the accepted original reason source exactly.

The existing engine-recovery test runs the actual main source inside a VM after stripping imports. Its unadapted current fixture failed four of five tests because `createRejectionReasons` was absent from the VM binding; the independent Worker-loader test passed. Adding only the real controller import and VM binding makes all five tests pass. No assertion, fixture behavior or product controller changed.

One normal build and one replay of the unchanged public browser receiver then passed on the composed source. All eight groups passed through the actual Pyodide Worker and Python Agent, with 16 Worker requests/replies, no observed external HTTP or page exception, and all 50 staged inputs unchanged. This receiving includes the newly integrated board's render and availability hooks. The original source/tests/browser results and failed receiver attempts are not relabeled.

`current-source.json` preserves the exact source composition, reversible owner additions, two-line fixture transition, current source hashes, commands, negative control and accepted results. The full current raw receipt and four command logs remain in the native directory named there. The original `files-manifest.json`, author capture and author receipts intentionally retain their original source identities; this current record is their explicit continuation.

Replay from the submitted repository with its unchanged lock:

```sh
cd web-demo
npm ci
npm test -- tests/engine-recovery.test.ts
npm run build
cd ..
node web-demo/tools/check_rejection_reason_browser.mjs \
  --project . --browser /absolute/path/to/installed/chrome \
  --output /absolute/path/to/new/rejection-reason-receiving
```

The browser receiver requires a normal functioning browser sandbox, Node 22 or later, and its documented resource reserve. It exercises an isolated in-memory sandbox through the actual project runtime. Final-head hosted CI and final integration are separately recorded in the pull request.
