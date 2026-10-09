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

## 2026-10-09 Raider continuation — original browser failure retained

The qualified product source is unchanged at `ada2658b0291f094d4786aeec346b072fe357be4`. Actual native Vitest still gives **baseline 5 pass / 6 expected failures** and **candidate 11/11 pass**, with production typecheck/build passed. This continuation received the exact already-built candidate on a separately established Windows machine and attempted its three new status groups once. **The browser attempt failed before CDP admission: zero application groups, zero actual browser responses and no Python Worker call reached.** It adds no browser acceptance or public deployment.

### Exact alternate receiver and transport

Raider registration `edc358ed-5ad6-4036-b7aa-8667bf0e14e0` was bound to `MSI\jacob`, SID `S-1-5-21-878538442-3911721743-4092253737-1001`, UUID `3F26B307-4CE1-D64C-A7E5-349723FA9CF8`, session 1 and the 2026-09-30T22:56:56.500Z boot. The separate Spire registration `9ea77fe9-bb87-46e0-a5a8-8b3e25f6ff7e` was not treated as the same machine.

Existing Node 24.14.0, Python 3.14.3 and Chrome 154.0.8037.97 executable paths/hashes were read, then matched again under a fresh admission. At 06:14:20, available memory was **9,878,188,032 bytes**, above the unchanged 2 GiB floor. Only new `D:\hamon-autonomous-e3a41d2b3368-ledgerly-status-20261009` was created, with a protected current-SID ACL; peers' projects, caches and settings were untouched. The [coexistence notice](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6075143009) retains other Raider owners and does not reserve the host exclusively.

The ThinkPad export made **zero filesystem writes**. Its original interactive transfer hit the 190-second outer timeout (exit 124); seven chunks were retained. A short noninteractive successor emitted the remaining 20 chunks and exited 0 in 0.63s, reproducing the same frozen archive. All 27 chunks were copied through existing RDC into the new receiver, then reassembled and verified natively: **6,994,504 compressed bytes / SHA256 `8afcf54c679480e34deee5dc09b82dc8c6de2ddc44111b80c18c16d656a43733`**; **17,189,893 decoded bytes / SHA256 `1bc8d077f77a8d3e24006d2eb771267fdecec7b07724abf8644dbce58318d0b8`**. Every one of 31 built files (12,837,983 bytes), both qualified source files and the build manifest matched.

The first PowerShell preparation wrapper exited 1 before Node ran because a concatenation inside a pin array absorbed its size/hash fields into the pathname. Only explicit parentheses were corrected. The corrected wrapper 56716 exited 0 in 3.31s at 06:22:35; native preparation took 1974ms. Actual Node syntax and receiver validation-only checks passed. The original wrapper failure and both exact sources remain in `RAIDER-RECEIVING.json`.

### Single actual attempt and closure

The independently reviewed supervisor fixed an anonymous kill-on-close job, **1.5 GiB aggregate committed memory**, **16 associated processes**, a 100-second total bound, bounded pipes and exclusive receipt files. It created Node suspended, established the job limits and assignment, then resumed that exact child. The fresh pre-child memory reading was 10,299,777,024 bytes.

Outer 2884 exited 3 in 2.01s. Supervisor 74960 observed Node 61708 exit 1, exact handle signaling/closure and unchanged runtime/driver pins. The driver made 31 successful, hash-matched private-loopback GETs, then launched Chrome PID 85548 exited 0 before `DevToolsActivePort` was observed. Browser log and Node stderr were empty. The driver retained **FAIL / groups 0 / browser responses 0**, with private server closed and profile absent at its cleanup.

The job reported six total associations and three active associations (PIDs 57832, 19728, 77520) just before its handle was closed; peak committed job memory was 81,428,480 bytes. These are association observations, not a count of successfully executed consumers or proof of descendant closure. The original supervisor result remains failed.

A separate scoped read at **06:27:48.721Z**, observer 89748 exit 0 in 1.73s, queried only the seven known outer/supervisor/Node/Chrome/job IDs and their direct children. It returned **rows[]**, and the private profile was absent. No process kill, capacity probe, replay or global orphan-free claim accompanied that observation. The startup cause remains unestablished; launcher exit 0 alone does not explain why CDP readiness was not reached.

### Recoverable evidence

- `raider-native-evidence.json.gz` contains **16 exact original native files / 215,647 member bytes**, including actual preparation, driver, supervisor, raw `SUPERVISOR.json`, failed `RESULTS.json`, stdout/stderr and native index.
- Compressed **98,635 bytes**, SHA256 `56881f8685374992210a663301a96f0f8f2b7068ca8ce2da54e8a6ed6c7f0e90`; decoded **289,978 bytes**, SHA256 `faad13a633b5a105c5a0b4c8412ac287f09ea9bef4930e0b424602da65256aa6`.
- `RAIDER-ARCHIVE-MANIFEST.json` names/hashes all 16 members. Independent local in-memory Python verification exited 0 and preserved raw large-integer bytes. Gzip recompression identity is not required.
- `RAIDER-RECEIVING.json` contains exact control sources, original transport/wrapper failures, current admission, actual outer results, scoped closure and full current workflow bodies.
- The two `raider-receive-*` source copies match their native archived originals. `verify-raider-evidence.mjs` is a read-only custody utility; its source is provided without a new native execution claim.

The immutable old public PASS and its six groups remain historical and unchanged. The single LA7 low-memory refusal remains refused, with no retry. Ledgerly main remains c498; this evidence-only continuation uses the existing source branch. No PR transition, main push, merge, dispatch, skip marker, GitHub Actions or public deployment was used. Further work is source/evidence analysis; this browser failure will not be replaced by another native attempt.
