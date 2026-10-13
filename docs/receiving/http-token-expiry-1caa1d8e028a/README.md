# Refresh expired HTTP access tokens

This increment lets a long-lived `HttpPayPalClient` acquire a new access token
before its next requested operation when the cached token's declared lifetime
has elapsed. The public client methods and constructor arguments stay the same.
It belongs to [Ledgerly issue 79](https://github.com/Jacob-Met/ledgerly/issues/79).

## Behavior

The client retains a token while its measured deadline is in the future. At the
deadline it clears the expired cache and makes one ordinary OAuth request before
continuing the caller's requested operation. The lifetime starts at the beginning
of that OAuth request, so time spent receiving the response does not extend it.
The cache uses Python's monotonic clock rather than the adjustable system clock.

A token response must be a JSON object containing a nonempty printable ASCII
`access_token` without spaces and a positive, finite numeric `expires_in` in
seconds. Booleans, missing lifetimes, strings, nonfinite or overflowing values,
and tokens already expired when the response finishes are refused with
`ValueError`. A malformed JSON response keeps its `JSONDecodeError`. The response
stream closes before these validation errors escape.

If refresh fails, that error reaches the caller and the expired credential is
not restored. A later explicit client operation can try authentication again.
The client does not retry or replay an invoice operation after an authentication
failure. Token revocation and expiry during an in-flight operation can still
produce the existing provider error. There is no background refresh, persistent
credential cache, new dependency, or new concurrency guarantee.

The existing `LEDGERLY_ALLOW_NETWORK` constructor gate remains in place. This
change grants no permission to send an invoice, reminder or payment, and changes
no Agent approval behavior. The browser demo continues to use its existing
in-memory sandbox. Qualification is limited to the cloud Python source and
isolated regular-wheel receiving described below.

## Run the maintained controls

From the repository root, using Python 3.12 or later:

```sh
python -m unittest discover -s tests -p test_http_paypal_token_expiry.py -v
```

The focused tests need only the Python standard library. They invoke the actual
client with authored responses, credentials and clock values through an
in-memory `urlopen` replacement. No socket or PayPal request is made.

The existing complete Python suite can be run after the project's normal
development installation:

```sh
python -m pytest -q
```

Transport-only fixtures should stub `_auth` when authentication is outside their
scope. Manually assigning the private `_token` field alone no longer establishes
a valid cached credential; its measured lifetime is also required.

## Source and receiving

Original source is main `79c16c51e5766c5091ba5b5b06b23b24c3ffc1f0`, complete tree
`1f2125102c19b3b89ae56ca7b6590a0fd7afb7fb`. Only cache initialization and `_auth`
change in `ledgerly/paypal.py`. The original and candidate are byte-identical
outside that span. The separate issue 77 `_call` response-closure work retains
its owner and method boundary. All extraction, invoice, approval, browser and
workflow source remains outside this change.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Original `ledgerly/paypal.py` | 26,243 | `de61591ef00eb77ea6efb76fc100a9b6c72b38b10361a1e64a13d811a76ddbb3` |
| Candidate `ledgerly/paypal.py` | 27,725 | `e519d1e1d63f2534b9e9d5574b779a6b7d42ee2e5f18b54b70fa8737522cd451` |
| Maintained test module | 9,581 | `38264bc4bba6bf8c5c083372e37161ebea6efc015f00b825f7603c4786f62143` |

The retained original consumer trace requested one synthetic token valid for ten
seconds. Actual `get_invoice` calls at clock values 100.0 and 109.999 succeeded;
the call at 110.0 reused that expired token and raised the authored HTTP 401
`PayPalError`. With the candidate, the same trace requests a second token before
the third GET. All three GETs succeed and none is replayed.

The 11 focused unittest methods pass. The complete selected Python test closure
passes **514 tests and 153 subtests** under cloud Linux CPython 3.12.14 and pytest
9.1.1, with unchanged candidate bytes. Its 46 inherited source/test/fixture inputs
were matched to current-main Git blob identities before use. The first broader
attempt could not start because the default Python environment lacked pytest;
that failed receipt is retained. The passing attempt used an existing pytest
runtime read-only, with plugin autoload, bytecode writes and pytest caching
disabled. It did not install or modify that runtime.

The regular Python wheel was also built using the unchanged current-main package
configuration, with dependency downloads disabled. Its five packaged Python
modules match the candidate source byte for byte; all ten wheel RECORD entries
were verified. A fresh isolated Python environment then installed that wheel
without dependencies. Outside the checkout, its actual installed client passed
the same three-GET expiry scenario under `python -I`; every installed module hash
matched. This is a temporary cloud consumer, not an estate machine installation.

The wheel is `ledgerly-0.1.0-py3-none-any.whl`, 34,254 bytes, SHA-256
`de7904f06e837834b11d55786027629370e5db1777440dc41bc0fc1729ac5a06`.
It keeps the existing project version, so use the exact artifact hash and source
link to distinguish this reviewed increment. The delivered source and wheel are
for explicit receiving; main/adoption status is stated in the linked PR/handoff.
The standalone demo's missing bundled fixtures remain with issue 74 and are not
fixed by this authentication change.

An independent receiver froze its own oracle and ran the original before reading
the candidate or the authored tests. The original passed 3 of 13 controls and
failed the ten expected token-lifetime contracts; the same oracle passed all
13 controls on the candidate. It checked the exact request-start deadline after
three seconds of response latency, malformed-response recovery, identical
refresh HTTP 503 propagation without fallback, and one attempted invoice POST
without replay. Source bytes, modification times, modes and inodes stayed exact
during both runs. The source review also found all 35 other class methods,
including issue 77's `_call`, text-identical.

The independent receiver SHA-256 is
`593035663ae51ccf2db8c0e246a9f180ef25cd89c3a8a7871f98750ab5ab8583`;
its candidate receipt SHA-256 is
`72b9be54cdce7f3a1f1b555dc66b0d41ba0baabb775a0356a02f6f99deb5eea5`.
See `independent/review.json` for the exact verdict and original receipt binding.

At final intake, draft PR80 contains issue 77's separate HTTP response repair and
draft PR78 contains the installed-demo fixture proposal. Neither is included in
this source or wheel. The PR80 fixture currently seeds `_token` alone; its owner
must compose that fixture with the measured-cache contract (or stub `_auth` for
the transport-only test) before the two contributions are tested together.

Raw original/candidate traces, exact source intake, test output, and independent
receiving belong beside this guide. These controlled results establish the
specified cache behavior, isolated wheel operation and regression outcomes. They
do not establish live PayPal acceptance, browser behavior, installed estate
application adoption or native
Windows/Mac operation. No Actions run or deployment is part of the receiving.

## Primary references

- [PayPal authentication](https://developer.paypal.com/api/rest/authentication/)
  describes the returned token lifetime and requesting a replacement after expiry.
- [Python monotonic clock](https://docs.python.org/3/library/time.html#time.monotonic)
  documents its elapsed-time basis and independence from system-clock adjustments.

Both references were read on 2026-10-13. The implementation does not assume that
a locally unexpired token is still accepted by the provider.
