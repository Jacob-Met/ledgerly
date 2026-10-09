# Retire stale checked-field status after intake changes

This source-only candidate fixes an inherited browser status lifecycle gap. Actual native Vitest, TypeScript and the production build pass. The attempted native Chromium run stopped before opening the app, so this packet does **not** claim a browser acceptance or public deployment of the correction.

## Problem and behavior

At `c498f55883c755553b59921199d54689d99c9730`, a valid Python review publishes “Fields checked” to the global `#status-message` beside Event Trace. Editing fields, removing confirmation, or reopening an intake correctly retires review authority, but those paths previously updated only the local review message. A fresh `analyze` result carries no replacement status message, leaving the old checked hint visible while the restored fields are unchecked.

The omission already existed before PR48, in parent `da2e47043d7f18aa231d80b568dd30e31ed8b77c`. The Python bridge message is unchanged. The issue concerns the global status hint, not the audit list, validation rules or permission to draft.

The candidate updates that hint at field/confirmation/source invalidation, while checking replacement input, after source-only restoration, and when submitting a new explicit review. It preserves meaningful request errors on failed replacement. It does not change `runAction`, authority state or guards, Python/core/provider behavior, draft/send handlers, or event history.

## Qualified source

| File | SHA-256 |
|---|---|
| `web-demo/src/main.ts` | `f478fa3ccbf8d0f75e4a150a23e13fcb6acf8656608944e9584fb3bdd6e5d34c` |
| `web-demo/tests/engine-recovery.test.ts` | `03a250b265a1b570fb04ad662e689fe196551053033a02cc92592393c0198339` |

The commit has the real current main parent `c498f55883c755553b59921199d54689d99c9730`, tree `efb9d2f50f79336588f7b14beca29a889899e1a9`. All other parent source leaves and modes are preserved. A separate root-agent source review inspected the complete patch and accepted the status/error boundaries; it did not rerun the candidate tests or claim browser review.

## Actual native gates

The new isolated project is `/home/jacob/hamon-universal-e3a41d2b3368-ledgerly-intake/candidate-status-20261009` on `hamon-thinkpad`. Existing `candidate` and `candidate-a4` trees were preserved. All126 selected source/config/test/tool leaves were materialized from exact c498 content. The candidate changes only the two files above.

| Gate | Actual result |
|---|---|
| Native baseline Vitest 5.0.3, one suite | 5 existing cases pass; all 6 new status regressions fail as expected |
| Native candidate Vitest 5.0.3, one suite | 11/11 pass, exit 0 |
| TypeScript 5.9.3 production `tsc --noEmit` | exit 0 |
| Existing stage-Python step and Vite 8.3.3 production build | exit 0 |
| Borrowed locked dependency tree | 894-entry before/after guard unchanged |
| Unmodified selected source files | all 124 preserved |
| Production output | 31 files, 12,837,983 bytes, manifest included |
| Owned native footprint at gate completion | 28,964,362 bytes |

The corrected gate completed in 4.71 seconds. Before it, available disk was 1,122,045,952 bytes; afterward 1,106,477,056 bytes, with 4,726,685,696 bytes available memory. Temporary/cache/output paths belonged to this isolated candidate; no package install or shared cache mutation occurred. Vite emitted its Pyodide Node-module externalization warnings, retained in the raw stderr.

The 6 regressions cover field edits, removed confirmation, source edits, replacement with unfinished fields, source-only replacement, and replacement failure preserving the request error and recoverable input. They assert existing draft authority constraints and no accidental draft request.

## Preserved attempts and limits

The first real Vitest attempt also discovered an evidence backup named `engine-recovery.test.ts`. The actual baseline cases produced5 pass / 6 expected failures and the candidate cases 11 pass, but an extra backup suite failed import collection. The gate correctly stopped before typecheck/build. The original attempt is retained under `attempt-1/`; the byte-identical backup now ends in `.test.ts.txt`. The corrected gate requires exactly one collected suite and succeeds.

Earlier in-memory Node/TypeScript adapter checks remain labeled as adapter checks, **not Vitest**. The first native type overlay had a wrong working-directory environment failure; its corrected production overlay passed. Both attempts remain in the archive.

A separate narrow native browser attempt used the already-built candidate, Node 22 built-in CDP tooling and existing `/snap/bin/chromium` (Snap 3537). Fresh launch admission observed 4,678,905,856 bytes available memory and 958,742,528 bytes available disk. Chromium exited before its CDP endpoint with DBus-address and crashpad ptrace diagnostics. The attempt completed in 1.039 seconds, performed **zero application checks or Worker actions**, confirmed browser/server cleanup, and preserved source and all 31 built files. Its receipt, script and logs remain in the archive. No sandbox-disabling flags, install, repeat launch, public browser receiving, financial record or provider action followed. The selected session/display variables were absent, so no evidence supported an environment-value correction.

## Existing public evidence remains historical

The already-qualified public intake packet was successfully published before this recovery:

- [Immutable original public packet](https://github.com/Jacob-Met/ledgerly/blob/ac4ee6a5c3c7a20e28c44a7a6f973ea62da50c06/docs/receiving/public-intake-e3a41d2b3368-20261008/README.md)
- [Original publication comment](https://github.com/Jacob-Met/ledgerly/issues/41#issuecomment-6071491523)

Recovery verified its complete Git tree (all 767 parent leaves preserved, 7 evidence additions), all 7 published blobs, archive/member digests and all 45 member contents. Its original Oct8 public PASS, screenshots and 3 prior failed runs were not rewritten. Linux gzip recompression is not byte-identical to its Windows-produced gzip; recovery therefore records portable content custody, not a cross-platform recompression pass.

The public Ledgerly site remains associated with c498. Its known deployment route is GitHub Pages through `push main` or `workflow_dispatch`, both covered by the active Actions hold. This new source-only branch is not a live deployment.

## Reproduce evidence verification

From this repository checkout:

```sh
node docs/receiving/status-hint-e3a41d2b3368-20261009/verify-evidence.mjs
```

The verifier reads only. It verifies the exact stored gzip hash, decompressed content hash, unique bounded member paths, every member length/SHA-256, source-file hashes, raw Vitest counts and successful native gate receipt. It does not recompress the archive, rerun tests, launch a browser or deploy.

`SOURCE-TRIGGER-ADMISSION.json` contains every current workflow body, ruleset result and open-PR path assessment. PR36 overlaps the same two file paths for completed-review history; its branch is untouched and this candidate makes no integration claim. Source publication uses a unique branch only, with no PR/main/workflow/dispatch operation or skip marker.

## Windows admission follow-up: October 9, 05:35 UTC

The existing strict SSH route recovered the original Windows driver and runtime pins without writes. Original driver `ddb7673c…`, acceptance `731ec7f8…`, Node 24.21.0 and Chrome 154.0.8037.98 matched their known bytes on the same account, UUID and boot generation.

After the separately coordinated native workload’s scoped process closure, the single fresh browser admission observed **1,132,441,600 bytes available RAM**, below its **2,147,483,648-byte (2 GiB) floor**. Disk had 573,084,852,224 bytes available. The wrapper exited 3 and closed normally. The refusal occurred before the proposed new root was inspected or created, before any of the 31 built assets were transferred, and before any browser or Worker action. No capacity poll or retry followed. This uses the browser’s own 2 GiB admission, not the compiler lane’s 4 GiB floor.

[WINDOWS-ADMISSION.json](WINDOWS-ADMISSION.json) preserves the primary source read, exact admission script/output, runtime pins and the prior ThinkPad write refusal. [windows-prepared-driver.mjs](windows-prepared-driver.mjs) preserves the prepared 28,492-byte receiver (SHA-256 `dd6c23cf9eb23dd774f9cfe42efa59d9ab18c81360afec9b4f89a4827c4a662d`). It passed a read-only Node syntax check and was **not executed on Windows**. It derives from the original native driver, verifies the new 31-asset manifest and actual browser responses, and contains three new status groups with intended init/analyze/review actions only. Its paths are for a new owned Windows receiving root; it is an evidence artifact, not a command to run directly from this docs folder.

The qualified source commit remains `ada2658b0291f094d4786aeec346b072fe357be4`; the evidence continuation changes only documentation. The original public PASS, native Vitest/build results, 45-member archive and product source hashes are unchanged. Actual browser receiving of this correction and public deployment remain pending a newly admitted route.
