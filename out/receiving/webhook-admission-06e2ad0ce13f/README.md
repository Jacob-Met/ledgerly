# Webhook admission and current invoice facts

## Result and source boundary

This component makes an accepted webhook a reason to read the current invoice.
It no longer copies the notification's older status or paid amount over the ledger.
The existing current-invoice presentation and reminder invalidation code supplies
the new facts. The accepted event ID is recorded only after that read succeeds.

The final component is based on current main
`4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`, including the merged reminder, invoice
deadline and prior-payment evidence work. Its `ledgerly/agent.py` Git blob is
`91ef4680698f0db52258c6ce7a5e982de3f421c9` (SHA-256
`7860c686c0d172dbcdcb96bb64f688ab09b6f04790db794b20e90a35f6ee641d`).

Production changes are restricted to the `hashlib` import, the event-ID index
initialized in `Agent.__init__`, and `Agent.handle_webhook`. The handler and index
initialization are byte-identical to the independently accepted predecessor.
All eighteen other `Agent` methods are exactly the current-main implementations;
`extract.py` and `paypal.py` are also unchanged from current main. The preservation
proof is in `current-main-method-preservation.json`.

For known new notifications, signature verification and parsing precede admission.
Event and invoice IDs must be nonempty strings without surrounding whitespace.
Accepted event IDs bind to a SHA-256 digest of the complete canonical JSON body.
Harmless JSON key-order and spacing changes repeat the accepted event; changing its
content under the same ID raises `WebhookError`. The configured verifier also runs
for repeats. Unknown local invoices and failed current reads remain retriable.

## Why the change is needed

On the unchanged predecessor main, a delayed partial-payment notification could
replace a paid invoice's displayed facts, and an older paid notification could
replace a current refund. The ID-only index acknowledged conflicting content as
a duplicate and consumed unknown-invoice notifications before they could be used.
The twelve author regression cases all failed against that exact source. They
exercise the real `Agent` and offline `SandboxMock`; no provider endpoint is used.

An independent reviewer authored another twenty-six cases after reading the source
and existing owner tests, without reading the new author regression file during
design. Those cases cover current-state precedence, unchanged reviewed text and
one-shot approval, provider presentation edits, invoice locality, failed-read
retries, unknown-invoice retry, content identity, verifier ordering, invalid IDs,
nonfinite JSON, and next-day reminder invalidation. This was independent authorship,
not a blind source review.

## Receiving results

| Exact stage | Result | Evidence |
|---|---|---|
| Main `1871942`, original suite plus author cases | 94 passed; 12 regression failures; 2 subtests passed | `baseline-composed-tests.log` |
| Main `1871942`, independent cases | 3 controls passed; 23 failed | Adjacent independent packet, `baseline-independent.log` |
| Accepted predecessor `2dbf14c`, independent cases | 26 passed | Adjacent independent packet, `candidate-r1-independent.log` |
| Predecessor with original owner expectations | 104 passed; 2 expectations failed; 2 subtests passed | `candidate-before-contract-updates.log` |
| Received predecessor with portable independent suite | 132 passed; 2 subtests passed | `candidate-native-tests.log` and adjacent independent receipt |
| Predecessor in actual Pyodide and existing browser bridge/review tests | 10 passed; production build passed | `candidate-web-receipt.json` and raw logs |
| Final component on current main `4bdaaa9` | 157 passed; 34 subtests passed | `current-main-native-tests.log` and current-main receipt |
| Independent composition with accepted extraction on current main `4bdaaa9` | 235 passed; 34 subtests passed; actual npm staging and Pyodide 10/10 passed | `../ledgerly-composition-independent-06e2ad0ce13f/current-4bda/` |
| Actual published PRs #19 and #21 composed with newer receipt-term main `1b2b902` | 246 passed; 60 subtests passed; actual npm staging and Pyodide 10/10 passed | `../ledgerly-composition-independent-06e2ad0ce13f/current-1b2/` |

The old source and failing logs are retained. No executable repair was made after
independent acceptance: the later source hash changes only because the accepted
patch was cleanly rebased onto the newer owner code.

Two existing test expectations were deliberately updated with independent review.
The unchanged current-invoice presentation normalizes the numeric balance, so the
bridge test compares `Decimal("500")` instead of requiring the spelling `"500.00"`.
A delayed event whose current read still matches the reviewed GBP 500 balance now
preserves that review. The strengthened test checks the same pending action and
payload, a closed outgoing permit, explicit approval sending the exact subject and
note once, and refusal of a second approval. Original expectations, their failing
execution and the reviewed diffs are preserved in the independent packet.

## Reproduction and limits

Run the repository's maintained suite with Python 3.12 or later and pytest:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
cd web-demo
npm test
npm run build
```

Recorded native runtime: Python 3.12.14 and pytest 9.1.1. Web receiving used Node
24.19.0, the unchanged package lock and installed matching dependencies. The staged
and built Python files were byte-identical to their qualified inputs. Build logs
retain the existing Pyodide Node-module externalization warnings.

Event identity is process-local and in memory. This component does not add durable
event storage or establish real-provider delivery behavior. The HTTP client was
not activated. Native bridge tests and actual Pyodide ran; a new browser navigation
or screenshot was not part of this Python-only change. This record establishes
source qualification, not merge, deployment, live HAMON host state or an estate
coordination lease. Extraction/value changes are a separate component; any combined
receiving packet states its own exact source tuple and base.

The original independently accepted component on main `1871942` is preserved as
local commit `e95af915da6a1d90a91d6a3204adb72937dc6e09`. The current-main rebased
source freeze is local commit `0f1a7f7e72d932d10698258efbcbb38a0d93f9e9`; subsequent
documentation and receiving commits retain the same executable source.

The final independent composition combines extraction commit
`22b7b5404e0bde8c6796d3abd8c5d177b5e84e1f` and webhook freeze `0f1a7f7` on base
`4bdaaa9`. Its composite `agent.py` blob is
`962e8ec37a9fa09dec30e4f13f4f70c05c6022f0`; `extract.py` is
`100e581d3ef0d99555f49264859d01b535c6094f` and `paypal.py` is
`43554a287c3b94b48e5376d9fa10f9287e1bea3f`. The merge is clean, the two component
methods and all seventeen remaining owner methods are preserved, and all forty-four
native/test/config inputs, twenty-two staged files and five runtime inputs remain
unchanged through execution. These combined source copies are receiving evidence;
the executable source in this webhook branch remains the bounded webhook component.

During publication, owner receipt-term PR #20 advanced main to
`1b2b902d5dd412a8b61c9b9075b815c1d0029365`. A further independent receiving run
combined the actual published extraction head
`f67e2c4034804f657eccad38887f377f28011e98` and webhook head
`d4ff41c66abe816a0c8b891bf75e0ad21ebaa755` with that exact new main. The merge was
clean and required no source correction. The composite source is agent
`8ba49c074571f74cbdab3e851861648322de8f17`, extract
`100e581d3ef0d99555f49264859d01b535c6094f`, and PayPal
`1d805837d9ed4fe29f42ae7093764c47b0060edd`. The new owner's `LedgerEntry`, all
seventeen other Agent methods, payment terms and mock-send behavior are preserved.
The packet retains all forty-five inputs, twenty-two staged files and five runtime
pins, together with the 246-test/60-subtest and actual 10-test Pyodide results.
These are composition receipts for the named immutable commits; later documentation
commits in this branch do not modify executable source or tests.
