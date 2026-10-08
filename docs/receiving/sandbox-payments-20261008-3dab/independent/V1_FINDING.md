# Independent V1 finding: preserve ordinary invoice rounding

The V1 payment admission candidate must not be integrated unchanged. Its new blanket `Inexact` trap during invoice recalculation makes an existing, valid fractional-quantity invoice unpayable.

## Exact source

- Baseline: `5493205cd69a32be75ed2f7dfc669b122efe5563`, PayPal SHA256 `6cacfd8a09dec18a936690965d8177e73f5787d157bfc9670bc9c3ffcebde82f`.
- Candidate V1 PayPal: `3f6aff852d9ed2b7d9cf4d557e127c4aae229d1b279ed7ed52ef2cfd059ca757`.
- Candidate V1 bridge: `6cba49a03053ca3bdee85af121dd87f27b52668bb9f7797baf8d268210317f42`.
- Owner freeze: `35e9f10586d0ed3637b3c048de500f0e4fa4d335cec24d623a6ea306dd4a4109`.
- Original standalone observation probe: `a2968f6260a6e1414f2a67afac775fa3cfc1ebcc3d6b84d4c9a1b9b45f03f692`.
- Independent two-method regression probe: `606d3ae4818854aac0b7529f291942f684fb3e9d0073f97efeee1ffbd3b638e7`.

All 33 baseline and 34 candidate source files were copied privately and hash-verified against the owner freeze. Source copies and owner files still match after execution.

## Native observation

The probe uses the actual published `bridge.handle_json` → `Demo.dispatch` entry points and `SandboxMock`, with a fictional authored email and explicit approval of the queued mock invoice. It changes the existing fixture's work to 1.5 hours at GBP0.01 per hour. Unit price is a valid cent amount. Existing invoice rules round the total GBP0.015 to GBP0.02.

The baseline accepts a GBP0.01 partial payment and then the remaining GBP0.01. V1 refuses the first exact-cent payment with “Sandbox payment could not be applied exactly; the invoice was not changed.” Its blanket trap observes the intended total rounding, although the submitted payment is exact. A second authored 1.3-hours case confirms ordinary downward rounding is also rejected.

The independently authored sequential method starts with a GBP12.34 partial payment and exercises numeric zero, false, NaN text, a negative amount, a fractional-cent amount and negative numeric zero on the same invoice. Each refusal must preserve the invoice, Agent state, previous event and request count; a duplicate replay and exact GBP1.23 retry follow each refusal. Final explicit full-balance settlement is followed by replay of the original partial event. V1 passes that distinct method. Baseline fails its first zero attempt by paying the full remaining balance.

## Disposition

Owner accepted the finding and is preparing a successor that preserves ordinary invoice rounding, exact submitted-payment admission and staged mutation. V1 is retained as a failing intermediate. Approval remains pending successor receiving.

The isolated process sets `LEDGERLY_ALLOW_NETWORK=0`, blocks provider construction and network entry points, and performs no real invoice, payment, account or sending operation. These receipts qualify the actual CPython bridge call boundary; they do not claim deployment or a new browser/WASM execution.
