# Independent receiving review: Ledgerly completed reviews

**Decision: the focused disclosure and focus correction is accepted at the exact application source below.** The independent successor run passed all seven application checks it executed. Its final screenshot failed, so its actual overall process exit remains **1**. This packet does not claim a complete browser pass or a successful successor image.

## Transport and archive status

The final native freeze/archive command returned an MCP timeout, and a subsequent read of its freeze record also timed out during a service-wide outage. Its execution status remains unknown. The three receiving results and the 13-file native custody copy were verified before that interruption. This independently authored review is available now; no completed archive or manifest is claimed until the native freeze record can be read.

## Source and runtime

The original candidate was PR 36 head `838f1f5ed42b39c637fa50279c52413832ddf54d`, tree `d31987b60ee0f27a8d1942d7cea23f6fff08e510`. The corrected application was head `2d5e275a92203332641a54c1ae164c9963786ab0`, tree `08d796a136cd597fc6be1758f90c5cf902f98fdc`, incorporating incoming main `b9c24ace6b57a17215a53c50b674bd187d13f8ed` (tree `0f457eb8ded2b462bd1be4d335c3a257cd19c630`).

All three attempts used the **same unchanged independent receiver**, `ram-witness/check-disclosures.mjs`, SHA256 `e60bdef351a11e58b3f4fdf4f0277332fa4d6f889d4bc3361db7a89add681f95`. It ran on the actual ThinkPad with Node `v22.22.1` and Chromium `153.0.8010.47`. The source and existing production distribution were read only.

The original binding covers 68 declared source/test inputs and has SHA256 `d0fd7dc5880d9f83b6961711fdeb35c8738fcbd73f22b513565c868257da09bb`. The corrected binding covers 76 inputs and has SHA256 `c1c7cebc4365c3825b8f5017fe3b0cbfdd75dc38000dbb73b11d71cc8f17bc49`. Every row was checked against its published Git blob independently of the author.

The corrected renderer SHA256 is `657ed1ebdcccad9eb20abecbb5f2dc755e18a3ad993e3710894bb8cd8ea17b86`. Both raw receipts retain the complete per-file SHA256 maps for all 30 distribution files. Their canonical sorted-map digests are:

- Original distribution index: `c90e9cf435840f84d235cfb3bd0848cb648cd7c57f97dabcdfd03bb4e87d67fc`.
- Corrected distribution index: `46bdb1b438897261119c33822a81b8a3591df29d28d278bc84a760b7f61c777b`.

These digests bind relative names to their actual byte hashes using compact, sorted-key JSON. They are not performance or deployment measurements.

## Actual runs and conclusions

| Attempt | Executed checks | Actual process result | Meaning |
| --- | --- | --- | --- |
| Original RAM-profile run, PID 3219780 | 7 passed, 1 failed | Exit 1 | Reproduced nested disclosure reopening and lost summary focus after an actual Worker snapshot. |
| Corrected RAM-profile run, PID 3297434 | 0 checks | Exit 1 | Chromium exited before DevTools startup; the receiver timed out. No application result was reached. |
| Corrected home-profile run, PID 3335177 | All 7 application checks passed; eighth check was not reached | Exit 1 | The corrected interaction passed. Final screenshot capture failed with an actual Chromium GPU/Viz error. |

Every attempt preserved all declared source and distribution hashes. Each main browser process exited with code 0 and no signal; its exclusive profile was removed. Those normal browser exits do not convert either failed receiving process into a success.

The first corrected attempt retains `HistoryService::Init()` failure in stderr. A separate tiny RDC evidence write returned quota error `-122` and left a zero-byte placeholder; that placeholder and the observed response are preserved. Subsequent native capacity inspection showed 42.1 GB available in home. An exclusive native file write/fsync and SQLite commit/readback succeeded in a new owned home directory before the home-profile attempt. The earlier startup cause remains unproven.

The home-profile run reached the actual application and passed the desired behavior, then `Page.captureScreenshot` returned `Unable to capture screenshot`. Its native browser stderr records Viz `CopyOutputResultSender` deserialization errors and a GPU process exit code of 9. There is no successor screenshot in this packet. The original 104,619-byte image is retained with SHA256 `88e4901f783cb65b0fa5073618720ee98ad8bd9f7cef9cd33ce623e95f296814`.

## What the unchanged oracle proved

The receiver loaded the repository's fictional fixture, ran real Python analysis and draft actions, and approved the original queued sandbox send. It delegated native Worker construction and `postMessage`; no reply was fabricated.

It then tested outer and nested disclosures separately. Each test retained summary focus while DOM-activating the application's existing Analyze button and waiting for the next actual Worker reply. This deliberately gives the renderer an ordinary asynchronous snapshot while keeping focus on the history control under review. It does not claim that a pointer click on Analyze normally keeps focus on another element.

On the original candidate, the nested disclosure was closed and focused before the reply, then reopened and left `BODY` focused. On the corrected candidate it remained closed, visible and focused. The outer disclosure stayed open and focused on both candidates. The corrected source stores explicit outer and nested open states per retained action ID, then restores the corresponding summary using `preventScroll`. It also preserves the false/closed nested state rather than restoring only open panels.

The remaining application controls passed: a real empty Python session; the retained original approved proposal; keyboard opening with no action controls or Worker messages; and exactly one requested Analyze message per snapshot with no state/provider change. Mock requests remained 4 through both snapshot checks. In the corrected run, `page_errors` was empty, but the receiver's final named no-uncaught-errors check occurs after capture and was **not executed**. The corrected raw full Worker-observation field likewise was not reached after capture; the seven semantic check records remain the evidence for those actual observations. The original complete outgoing sequence is retained as `init, analyze, draft, approve, analyze, analyze`.

## Independent source and concurrent-work preservation

The initial review inspected the additive Python projection, Worker/source-copy seam, shared proposal-only markup, escaped values, explicit `UNKNOWN` label and read-only history renderer. No agent, provider, extraction or payment algorithm was modified by the history feature.

At corrected head `2d5e275`, independent Git-tree comparison against incoming `b9c24ace` found 604 base leaves and 610 candidate leaves: all 591 unrelated leaves and modes were unchanged, with 13 expected modifications, six additions and no removal or unexpected path. The shared `main.ts` and `bridge.py` hunks add history rendering and snapshot data while retaining the concurrently landed CSV and payment changes. The exact comparison is retained in `successor-publication-preservation.json`.

Later recipe head `17cc8a7ae3eb10083a037f7881c25af0510f6399` changes only `.github/workflows/ci.yml` and `web-demo/tools/check_review_history_browser.mjs` relative to `2d5e275`; an independent Git compare confirmed this. The tested 76-file binding belongs to `2d5e275`, including its then-current workflow. This packet does not mislabel it as a full 76-file execution of `17cc8a7`.

## Scope of this acceptance

This is an independent approved-history interaction witness and a production source review. The feature owner's maintained broader receiver separately owns failed `UNKNOWN` outcomes after a real mock send, literal reviewed fields, reminders, automatic rejection, restart/reset, visual capture and mobile presentation. This packet does not duplicate or claim those results.

The original and corrected complete Python/Vitest suites were reviewed as author evidence and were not rerun here. No live provider, real customer data, payment, camera or participant record was used. Page-domain network observations are recorded by this witness; it does not claim complete independent Worker-network interception.

## Packet layout and integrity

- `ram-witness/original/`: original semantic failure, source binding, renderer text, browser log, receipt and screenshot.
- `ram-witness/corrected/`: corrected prelaunch failure, exact input binding, renderer and raw browser log.
- `corrected-home/`: seven successful application-check records and the failed screenshot/GPU trace.
- `process-observations.json`: actual RDC launch and completion responses for the three receiving attempts.
- `ram-custody.json`: byte-verified preservation of all 13 own RAM witness files; original RAM files were left unchanged.
- `capacity.json` and its small synthetic files: the measured native home-write control.
- `files.json`: planned native final per-file manifest; freeze execution remains unconfirmed.
- `independent-review.tar.gz`: planned native archive whose writer includes full member rehashing; creation and verification remain unconfirmed after the transport timeout.

Original receipt SHA256: `225eb7b97e6e81227a8e3a39ee5b13eaf471b2fc15e26f51e42ad318be283a71`.
Corrected prelaunch receipt SHA256: `da349ccad18302f54673c57fc05235571c64a7afe6db276fb555b94175937ec2`.
Corrected seven-check/capture-failure receipt SHA256: `9ad18e113d5b1579d85118863671485a258fb7d15872aa7d35c40cfb8f7c8bac`.
