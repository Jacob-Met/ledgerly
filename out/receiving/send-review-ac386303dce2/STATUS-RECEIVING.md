# Author receiving: unrecognized provider status

This packet records a narrow successor to the frozen invoice-send preflight
source. It is authored receiving, not an independent approval or a deployment
receipt. Claim: https://github.com/Jacob-Met/ledgerly/issues/32.

The prior source is SHA-256
`f2bc79188eb9b4933f969ba3c6a08397fec5b6b3f4678add22c396fb5d0584eb`.
It treated any nonempty status string other than DRAFT as a known changed
invoice state. The documented pre-send contract instead holds an unusable
read for explicit retry.

The unchanged public Agent/SandboxMock probe
`test_send_status_receiving.py`, SHA-256
`78e61a77156ac0b000a74a976f41e20e427d51aec924f721b59fa5f9244e5975`,
shows that UNAVAILABLE, whitespace and padded DRAFT all incorrectly consumed
the review as REJECTED. Its known-SENT no-POST control passes. All three
negative subcases and the exact source pin are retained in the raw logs.

The prepared successor, SHA-256
`969b6f62ed0958705b3041831cfc0624951cd49893419f3ac2b1d5232d56dd97`,
imports the existing `paypal.STATUSES` and requires membership in that enum
at the existing invoice identity/status read guard. This is the only source
delta. The original helper comparison and outgoing exception/permit behavior
are unchanged. On this source the identical four-case probe passes, including
a fresh successful GET followed by one send after the unusable response is
removed, and refusal without POST for known SENT.

The production regression matrix gains exactly the same three unusable
status inputs; its prior cases and assertions are unchanged.
Old matrix SHA-256:
`d922bb8e2af7f110f3460fe1e82de7c2d1d573a94fc45e1d57092103cfcc4f2d`.
Extended matrix SHA-256:
`e522faa100de6443978505e00c3ba504c40cd3a866954a0bacb4b694252dad50`.

The successor and extended matrix were received with actual native source
from main `b9c24ace6b57a17215a53c50b674bd187d13f8ed`, tree
`0f457eb8ded2b462bd1be4d335c3a257cd19c630`. All current provider,
browser-Python consumer and payment-admission test bytes were verified by
Git blob before use. The full native run passes **245 tests and 96 subtests,
with no skips** on Python 3.12.14 and pytest 9.1.1. Complete output and
each input identity are retained in `status-successor-current-native.json`.

The previous f2bc source capsule, all preflight-policy adapters, initial
negative evidence and original author archive remain unchanged. Source
and test files in this packet are complete independent copies for byte
custody; the native receiver source remains identified by the published Git
base and the original complete author source capsule.

Each executable test used an authored local SandboxMock. No provider network
call, payment or real invoice send occurred. Per-exec fixtures lived in one
private temporary directory and were removed on completion.

To replay the unchanged probe against a complete source capsule:

```sh
LEDGERLY_SOURCE_ROOT=/absolute/source-capsule \
  python -B test_send_status_receiving.py
```

For the successor, overlay `status-successor-agent.py` as
`ledgerly/agent.py` in an isolated copy. For the full native regression run,
also overlay `status-successor-test_send_review_boundary.py` as
`tests/test_send_review_boundary.py` and receive the exact current native
input files listed in the JSON result. Preserve the original files when
reconstructing either historical version.
