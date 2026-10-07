# Ledgerly / Human-Gated Invoice Studio

A static browser demo that runs the repository's **actual Python modules** in a self-hosted Pyodide Web Worker. It is not a TypeScript rewrite or fixture-only output. Visitor-supplied job email flows through `RulesExtractor`, `Agent`, `RulePlanner`, `GatedClient` and the in-memory `SandboxMock`.

## Workflow

1. Load a fictional fixture or paste a non-sensitive job email; review extracted line items, confidence and validation issues.
2. Create an in-memory draft. Ledgerly probes and proves that an unapproved send is blocked.
3. Explicitly approve or reject the queued send. Only the mock changes state; no PayPal call or real message is sent.
4. Simulate a partial payment and a signed mock webhook, replay the exact event to show idempotency, advance the local clock and draft an overdue reminder.
5. Approve or reject the reminder. The invoice ledger and event trace update across the whole session.

No model, HTTP PayPal client, provider key, backend, analytics or localStorage is used. Pyodide and the staged Python modules load from this repo's Pages site. Email text and ledger state stay in tab memory and disappear on reset/close. The sandbox's HMAC is a test signature, not PayPal's production certificate verification; invoice actions are clearly labelled simulations. The confidence score is a heuristic, not a calibrated probability. Do not paste confidential client material.

## Verify and run

```bash
python -m pytest -q
cd web-demo
npm ci
npm audit --audit-level=moderate
npm test
npm run build
npm run dev
```

`npm test` runs the original Python workflow under Pyodide and covers extraction, the gate, payment/webhook verification, duplicate replay and overdue reminder approval. `npm run build` stages the unmodified Python core, fictional fixtures and self-hosted runtime assets into ignored `public/` directories. `tools/capture_ledgerly.py` performs a browser walkthrough and saves phone/desktop captures (requires Playwright and Chrome).

Pyodide 0.29.3 is MPL-2.0. Its unmodified assets and upstream license are linked from the page footer and `THIRD_PARTY_NOTICES.md`.