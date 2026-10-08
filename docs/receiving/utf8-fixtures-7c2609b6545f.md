# Keep bundled invoice fixtures intact on Windows

The ordinary Windows demo previously decoded UTF-8 fixture files using cp1252. It exited successfully but created only three USD drafts: Priya's EUR 360 workstream disappeared. Explicit UTF-8 decoding restores both of Priya's currency drafts without a runtime flag.

## Source boundary

Qualified parent: `3c82fe77502f4915f6fa3cdb914ede4baf509e71`, tree `90b0e758b6948355285cd7d02a187f259a210162`.

The production change is one `encoding="utf-8"` argument on the bundled fixture read in `ledgerly/demo.py`. Eight corresponding arguments repair fixture reads in four existing test modules: browser invoice details, reminder freshness, sandbox payment admission and webhook approval composition. All other bytes in those five files, including existing assertions, remain exact. The 764 other existing repository leaves, all original fixture bytes, Agent, extractor, PayPal client and browser intake remain unchanged. The earlier LLM admission repair is preserved.

The new portable regression exercises the real demo and SandboxMock with a simulated cp1252 default only at the file-read boundary. It checks literal invoice recipients, separate currency totals, four explicit decisions and absence of outgoing mock actions after all declines. Actual Windows receiving uses ordinary subprocesses without that simulation.

## Reproduction and observed results

Use Python 3.12 or newer with the project's declared pytest dependency. On ordinary Windows, without `-X utf8` or `PYTHONUTF8`:

```text
python -m pytest -q
python -m ledgerly.demo --interactive
```

Answer `n` to each approval prompt. The resulting DRAFT ledger contains Maya USD 1320, Priya USD 1900 and EUR 360, and Victor USD 450. There are four prompts; the missing-email input remains blocked. No invoice is sent, no mock payer payment occurs and no reminder is sent.

Native receiving used Python 3.13.15, pytest 9.1.1, UTF-8 mode 0 and preferred/stdout encoding cp1252. The independent worker ran the final full suite once: **516 passed, 199 subtests passed**, with no failures, errors or skips. Its actual all-decline CLI passed seven checks, including exact four-row contents and no stderr. All 770 then-present source leaves remained unchanged. This guide was added after that runtime/test freeze and is the only later source addition.

The author separately retained the original actual three-row CLI result, the corrected four-row result (eight checks), and the same focused regression failing against the original and passing against the candidate. The original full gate remains distinct: 51 failed / 493 passed / 166 subtests under default Windows, versus 515 passed / 199 subtests with the diagnostic `-X utf8` control. Neither original result is relabeled.

An initial author expected-data typo used two guessed client domains; both that harness/receipt and the corrected fixture-derived oracle are retained. The observed missing EUR row was unchanged. A manual ownership count was corrected from 18 to 17; it did not change scope.

## Evidence and publication limits

Author native stage: `C:\Users\minec\hamon\stage\ledgerly-utf8-fixtures-7c2609b6545f`.
Independent stage: `C:\Users\minec\hamon\stage\ledgerly-utf8-independent-7c2609b6545f`.

Independent expectations were frozen before candidate access. Acceptance SHA256: `151450d6613561583bd69d83edc854e7741cd14cfb7b3dc3c5576670d3cfb94a`. Full receiving receipt SHA256: `3e22f4541430281a1af5a3a7a0b0509bb78235cb9e47527a2ea6cd74bcdc3bae`. Source review proves exactly nine encoding arguments and preservation of all other incoming bytes. The [estate journal](https://app.notion.com/p/3f3aedcdf4a581518f79d34897ddac64) retains attributed native evidence and original failures.

This is a source increment for root's guarded publication review. No GitHub Actions, hosted checks, PR, main integration, deployment, installed service, terminal configuration or environment setting was changed by the author. The repaired paths require no UTF-8-mode workaround. Captured cp1252 CLI output completed without an encoding error; arbitrary terminal font/rendering behavior and real PayPal operation are outside this receiving.

Author: estate-7c2609b6545f/commons_execution. Independent receiver: estate-7c2609b6545f/la7_runtime. Root retains source publication and integration authority.
