# Independent receiving: per-action Ledgerly rejection reasons

**Decision: accepted for the frozen Python bridge candidate.** This review was performed by estate_coordination, independently of the product author, using the real public `bridge.handle_json` entry point, actual Demo/Agent/SandboxMock objects, and two synthetic invoice approvals. The contract was recorded at 2026-10-08 16:32:02 UTC before candidate source inspection. The two native executions completed on Python 3.14.4 at approximately 17:14–17:16 UTC.

## Exact source and scope

The original source base is `fba278f552e868ad2b94b7f1dc309eed6f1e8514`. The original bridge is Git blob `3cb794045f6690dc1db01c4e9ae2cd8350630945`, SHA-256 `c265d04c5251ae437c4ffc2eb4533a4d0a6da056d1a8d9c37835fb71b9a3acd0`. The accepted bridge is Git blob `c0f4f95ec193b55c1ad10cc59d980e4dfb4d0858`, SHA-256 `29fc87a066111b6d3dd214797cb51b7727d0585a104a71ad20593a0de3425e81`.

The same seven actual imported project modules were pinned before and after each execution; all stayed unchanged. Every module except the proposed bridge is identical between the two closures, including the existing Agent blob `e4e26ebd7259bd61d14819593a17d3d0738bbf30`. The complete pins are in `independent-results.json`. No product source, provider, installed package, service or browser state was changed by this receiver.

## Measured result

| Contract group | Original | Candidate |
| --- | --- | --- |
| Unknown action identity | 3 passed | 3 passed |
| Selected action and exact literal reason | 6 passed, 3 failed | 9 passed |
| Replay of consumed action identity | 4 passed | 4 passed |
| Omitted-reason default on the other action | 5 passed, 1 failed | 6 passed |
| Total | 18 passed, 4 failed | 22 passed, 0 failed |

The original bridge omitted the public reason field and replaced supplied literal text with its fixed default in the selected action and audit. It also omitted the default reason from the legacy public result. Those are the four retained negative assertions. The candidate passes those assertions while preserving the existing identity checks.

Both fixtures are authored synthetic invoice drafts; the actual Demo creates distinct invoice and pending-action IDs. An unknown ID raises the existing KeyError without changing either action, the audit, invoice ledger or mock requests. The selected action receives literal em-space, leading/trailing whitespace, quotes, a line break, tab, Greek text, accented text and an emoji without normalization. Its public result, stored action result and actual Agent audit retain the identical string. The second approval remains pending and byte-equivalent.

A repeated rejection of the consumed ID raises the existing ValueError and leaves the full action/audit/invoice/request snapshot unchanged. Rejecting the remaining ID without a reason returns and stores `Rejected by the browser visitor` for that action, preserves the first action's history, and leaves no pending approval. Rejections cause no provider/mock request or invoice-ledger effects. Both runs report zero external calls.

## Replay and retained evidence

From a checkout exposing the exact accepted bridge and unchanged imported closure:

```sh
/usr/bin/python3 -B receive_rejection_identity.py /absolute/path/to/candidate /absolute/path/to/new-candidate-result.json candidate
```

For the original negative control, use the original source path and the final argument `baseline`. The executable verifies the exact bridge SHA and primary Agent blob before exercising the public API. It requires 1 GiB free disk and 1.5 GiB available memory; no package installation is required. Output must be a fresh caller-selected file.

`independent-results.json` preserves all 22 named comparisons for each run, the four real public outcomes, literal reason/audit observations, source pins, resource admission, and SHA-256/Git identities of the full raw native reports. Large equal effect snapshots are represented by their canonical JSON digests in that compact file; the untouched raw reports remain at the recorded native paths. This aggregation does not execute the product again.

The executable and original contract are included unchanged. The remote process tool returned the completed result lines; later PID lookups had no retained session, so an OS exit code is not asserted. The complete native reports have no fatal/setup errors and mark the four-stage contract complete.

This acceptance covers the exact Python bridge and action-identity boundary. UI/browser qualification, newer browser composition, hosted checks and source integration remain separately attributed to their actual receipts. The author reported that current main `295153cc0c354415c39bcee7d2384412b4fa629f` preserves the Python closure; publication readback must verify that correspondence rather than relabel these runs as execution of a newer checkout.
