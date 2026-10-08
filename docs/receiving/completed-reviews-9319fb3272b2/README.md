# Completed-review history receiving

This packet preserves the actual source and receiving history for issue #31 and PR #36. The PR remains a draft while full browser receiving and final integration are completed.

## Product and source

The new read-only panel exposes retained APPROVED, REJECTED and FAILED actions, their original queued invoice or reminder, queued timestamp, and recorded result. An actual recorded UNKNOWN outcome is labeled prominently. It does not approve, reject, retry, pay, or refresh provider facts. The agent's existing queue and result semantics remain authoritative.

The initial published source is `838f1f5ed42b39c637fa50279c52413832ddf54d`, based on main `2ab89fdd65d200355dda381ba7bae82a22e268fc`. Current application source `2d5e275a92203332641a54c1ae164c9963786ab0`, tree `08d796a136cd597fc6be1758f90c5cf902f98fdc`, composes main `b9c24ace6b57a17215a53c50b674bd187d13f8ed`, preserving the separately owned invoice-details, CSV, overdue-scan and payment-admission changes. The latter composition has 76 declared native text inputs, each checked against its exact Git blob; the full Git tree is preserved separately.

Independent review reproduced a UI defect in the first source: closing and focusing the nested invoice disclosure was undone by an ordinary Analyze snapshot. The correction preserves both outer and nested open state and the exact focused summary, with no additional Worker or provider operation. Its unchanged independent oracle subsequently passed all seven application groups. That particular attempt remained overall failed because Chromium could not complete its final screenshot; this is retained separately from application behavior.

## Completed native gates

- Unchanged baseline: eleven healthy controls and three expected missing-history checks, including a real mock send followed by an authored lost response. Full raw state is in [native/history-baseline.json](native/history-baseline.json).
- Ten actual Demo history tests pass. The same ten run inside actual Pyodide.
- Two valid-source negative controls fail the unchanged oracle semantically: omitted FAILED results and shallow aliased nested payload/result. See [native/history-negative-controls.json](native/history-negative-controls.json).
- Current application composition: **215 Python tests plus 96 subtests; 84 Vitest/Pyodide tests; strict TypeScript and the normal production build pass**. The exact commands, source hashes, streams and statuses are in [native/current-b9-gates.json](native/current-b9-gates.json).
- [Hosted run 37794716517](https://github.com/Jacob-Met/ledgerly/actions/runs/37794716517) succeeded on exact head 2d5e275, before the new completed-history Chrome step was added.

## Preserved unsuccessful attempts

The packet retains first-attempt evidence instead of replacing it: integer payment terms supplied by a test fixture where the existing adapter requires text; two renderer expectations corrected to compare actual structured/literal data; an overescaped test-only regex; and the old receiving environment's missing Playwright executable driver. The last boundary stopped before browser launch with zero application checks and unchanged source/build bytes. The native Node receiver uses the repository's existing installed Chromium route and needs no browser-package installation.

The files under `native/` and `browser/environment-boundary/` are exact retained source/receipt bytes, including empty stderr streams. Historical absolute paths describe actual execution custody and are not installation requirements. Production build stderr contains ordinary Pyodide Node-module externalization notices; it is not described as empty.

## Maintained browser route

After the normal `web-demo` install and production build, run:

```sh
node tools/check_review_history_browser.mjs --source .. --dist dist --chrome /path/to/chromium --output /path/to/new-receiving-directory
```

A normal Git checkout supplies its own exact source binding. A declared native text hydration supplies `--source-manifest` explicitly. The receiver uses real Worker construction, requests and Python replies. The separate lost-response context serves the exact bridge plus a recorded receiving-only suffix that performs the real SandboxMock send before throwing TimeoutError. The accepted production files are checked before and after; no live provider is involved.

Final full-browser, visual, delivery and integration receipts will be added before this PR is made ready. No deployed Pages acceptance is claimed by this interim packet.
