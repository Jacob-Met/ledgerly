# HTTP error response lifetime receiving

## Problem and source change

A stalled error-body read in `HttpPayPalClient._call` raises its existing
`TimeoutError` while leaving the HTTPError wrapper, HTTPResponse and socket-backed
file open in the retained exception context. The original loopback witness
records this before its fixture cleanup closes anything.

The source change closes the HTTPError response in a `finally` around the existing
body read and JSON parse. Existing error translation runs after that cleanup.
The two documentation updates distinguish synthetic loopback tests from real
PayPal sandbox receiving, which remains unverified. No invoice, approval,
extraction, authentication, timeout or retry behavior changes.

Base: `79c16c51e5766c5091ba5b5b06b23b24c3ffc1f0`.
Original `ledgerly/paypal.py`: 26,243 bytes; SHA256
`de61591ef00eb77ea6efb76fc100a9b6c72b38b10361a1e64a13d811a76ddbb3`;
Git blob `66f067204d357499b3f7010a946563a431d50aea`.
Candidate: 26,449 bytes; SHA256
`1dd14b0612f2806855213478d9ccc2bb63afe3edc5d98f25d554b00379ad4310`;
Git blob `a1194a0b5577b10f5e81378c0ec222e8bea4d6a5`.

The single new maintained test is
`tests/test_http_paypal_error_response.py`: 7,862 bytes; SHA256
`5071233b7174df4c0a70835fa92bd7f180d0513b9a667b861c9c2371dbacd935`.
[Issue 77](https://github.com/Jacob-Met/ledgerly/issues/77) is the scoped
ownership and receiving record. Existing owners and all unrelated source remain
intact.

## Completed execution

| Course | Result | Scope |
| --- | --- | --- |
| Original focused test | 3 passed, 9 failed | Same maintained test against original source; failures require response closure |
| Candidate focused test | 12 passed | Stalled, complete, malformed, wrong-shape, empty, truncated and interrupted errors; success and constructor controls |
| Candidate maintained Python suite | 515 passed and 126 subtests passed; no failures or skips | All maintained Python tests, current Python browser-bridge modules and 12 synthetic fixtures; 49 input files unchanged |
| Independent original receiving | 3 of 6 cases; 84 of 93 checks passed | Own contract and server, frozen before candidate or author-test exposure |
| Independent candidate receiving | 6 of 6 cases; all 93 checks passed | Same frozen cases once; all three product/support files unchanged |

Python was 3.12.14 with pytest 9.1.1. Plugin autoload was disabled. No dependency
installation, provider request, model call, browser launch or native-device
operation was performed in these courses. The complete suite is Python source
receiving, not browser UI or real PayPal qualification.

Each focused transport fixture permits only its own localhost GET URL, uses a
cached synthetic token and bypasses proxies. It records the existing product
`timeout=30` before reducing only the fixture socket timeout to 0.15 seconds.
The interruption case injects a retained KeyboardInterrupt into the read method
of a real HTTPError response; it is not an operating-system interruption test.
Error type, message, exception context, fields, request headers and timeout
arguments are checked before cleanup. Every fixture closes its owned responses
and server at teardown.

The complete-body controls already close their socket-backed file through
Python's normal read completion. Their unclosed wrapper is not presented as an
ordinary complete-body connection leak. The stalled-body witness is the direct
underlying-resource failure.

## Reproduce with an existing test environment

From the repository root, with Python 3.12+ and pytest already available:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \\
  python -B -m pytest -q -p no:cacheprovider tests/test_http_paypal_error_response.py

PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \\
  python -B -m pytest -q -p no:cacheprovider
```

No PayPal settings or credentials are required. The tests scope their synthetic
localhost opt-in and restore the caller environment. To inspect the original
boundary, run the retained `probe_original.py` with an unchanged checkout of the
base commit as its positional source-directory argument. The probe itself uses
only that local fixture and records its shortened socket timeout explicitly.

## Evidence and persistence

- `candidate.patch`: complete product diff.
- `original-witness.json` and `probe_original.py`: initial actual HTTP failure
  observation and its exact author probe.
- `focused-receipt-recovered.json` and the two focused stdout files: both completed
  courses with complete raw outputs and source digests.
- `maintained-receipt.json`, `maintained.stdout.txt` and `maintained-junit.xml`:
  full maintained course, exact command and all 49 source/input hashes.

Both filesystems filled while the original focused stdout files and process
receipt were being saved. Their partial original files are preserved outside
this packet. The completed process output remained in the tool result and was
published recoverably in
[the issue checkpoint](https://github.com/Jacob-Met/ledgerly/issues/77#issuecomment-6135327293).
The recovered evidence here copies that retained output after capacity returned;
the historical save errors remain in its JSON. No focused command was replayed.
The later full-suite run and all its receipt files saved successfully.

## Independent receiving

The exact seven independent files are retained unchanged under `independent/`.
The receiver froze its contract and completed its original run before reading
the candidate. It never read the authored tests. Its own real localhost course
covers OAuth caching and request bodies/headers, the unchanged declared 20/30
second timeouts, stalled and truncated 503 bodies, Unicode 422 error details,
JSON 201, empty 204 and the constructor guard. The stall alone shortens its
fixture transport timeout to 0.20 seconds. No PayPal service request occurs.

All nine original closure failures resolve on the exact candidate. The original
TimeoutError, IncompleteRead partial bytes and missing-byte count, first-detail
PayPalError, and exception contexts remain unchanged. The source review found
the entire module AST equal after removing docstrings and unwrapping exactly
the added cleanup block. No other executable behavior changed.

The independent source-review receipt is 5,874 bytes, SHA256
`1f6a1fcaa500d71309d6eb59701850a6758af947d798ac00369f34cb5562a8c4`.
It accepts this bounded source publication; it grants no deployment,
provider/financial acceptance or workflow waiver.

`source-publication-gate.json` records the source branch and merge boundary.
The repository has Pages enabled; the connected tool does not expose its
current publishing mode. The unique new branch and declared push/PR skip
markers support a reviewed draft PR. A main merge remains held until current
implicit Pages-trigger safety is established, with all ordinary owner/head
gates preserved. Do not infer a merge, Pages publication or provider
qualification from a source commit or these local results.
