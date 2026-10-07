# Ledgerly

An agentic invoice and payment-follow-up copilot for freelancers. You paste in a client's job email.
Ledgerly pulls out the line items, creates a **PayPal Invoicing v2** draft and puts the send
in a queue. **Nothing is sent and no money moves until a human approves it.** After that it
watches the payment webhooks and drafts escalating reminders for overdue invoices. Those
reminders also need approval.

Entry for the PayPal AI Hackathon. License: MIT (see `LICENSE`).

## Browser demo

A live, fully-offline demo runs the repo's actual Python modules in the browser (Pyodide):
<https://jacobmetoyer.com/ledgerly/> — paste a fictional fixture, approve or reject the
gated sends, and replay webhook events. See [web-demo/README.md](web-demo/README.md).

## Setup

You need Python 3.12+. The core uses only the standard library, and the tests need pytest.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install pytest
pytest -q                     # 52 tests, fully offline
python -m ledgerly.demo       # scripted end-to-end run (add --interactive to approve by hand)
```

## Architecture

```
job email ──► extract.py ──────────► agent.py ─────────────────────► paypal.py
              RulesExtractor          tool loop (Planner protocol)      InvoicingClient (Protocol)
              LLMExtractor (inject)   tools: create_invoice,            ├─ SandboxMock  (default, offline)
              HybridExtractor         get_status, send_reminder,        └─ HttpPayPalClient (opt-in)
              validate() + confidence list_overdue
                                      ─────────────────────────
                                      PendingAction queue
                                      approve()/reject()  ◄── human only
                                      GatedClient: send/remind/payments
                                      raise ApprovalRequired w/o permit
                                      handle_webhook(): verify → parse →
                                      ledger transition (idempotent)
```

* **Extraction** (`ledgerly/extract.py`). A deterministic rules extractor handles bullets,
  `qty x item @ price`, `N hours of X at $Y/hr`, `Item: N hrs @ £Y`, `Item — €Y` and
  markdown tables. It also detects currency from symbols and codes ("prices in CAD" turns
  `$` into CAD), payment terms (Net N, within N days, due on receipt), billing addresses,
  deposits and stated totals. Each result comes with field-level `issues`
  (error/warning/info) and a confidence score from 0 to 1. `LLMExtractor` takes any
  `complete(prompt) -> str` function, and its output goes through the same `validate()` plus a
  grounding check: an email that doesn't appear in the source text is discarded as a
  hallucination. `HybridExtractor` only calls the LLM when the rules confidence falls below
  a threshold.
* **Agent** (`ledgerly/agent.py`). Planners can only call the four safe tools. `approve` is
  not a tool. As a second layer of protection, the PayPal client is wrapped in
  `GatedClient`, which needs a one-shot `(operation, invoice_id)` permit that only
  `approve()` opens. A planner that has been prompt-injected therefore still can't send
  anything (see `fixtures/12_prompt_injection.txt` and its tests). Jobs priced in two
  currencies become one invoice per currency. A known deposit is recorded as an external
  payment, but only after approval.
* **PayPal** (`ledgerly/paypal.py`). `build_invoice()` produces the create-draft request
  body. `SandboxMock` follows the documented paths, status codes, status enum and error-body
  shape, and enforces the invoice state machine (DRAFT → SENT → PARTIALLY_PAID → PAID).
  `parse_webhook_event()` handles `INVOICING.INVOICE.*` events, including `PAID`. The
  comments in the module list the doc URLs this was based on.

## What's mocked

| Real thing | In this repo |
|---|---|
| PayPal REST API (OAuth, Invoicing v2) | `SandboxMock`, in memory. `HttpPayPalClient` exists but refuses to start unless `LEDGERLY_ALLOW_NETWORK=1`; it has **not** been run against the sandbox yet |
| Webhook signature (`verify-webhook-signature`, cert-based) | HMAC over the same transmission headers, so the reject/accept paths can be tested |
| Payer paying on the PayPal page | `SandboxMock.simulate_payer_payment()` emits the webhook event |
| LLM planner and LLM extractor | `RulePlanner` / fake `complete()` in tests. No model calls anywhere |
| Client emails | 12 synthetic fixtures in `fixtures/`, using `.example` domains |

Places where the mock guesses at PayPal behaviour are marked `ASSUMPTION` in `paypal.py`. The
two main ones are which issue code comes back when you re-send a non-draft invoice, and
whether partial payments fire `INVOICING.INVOICE.PAID`. Ledgerly keys off
`resource.invoice.status`, so it works either way. Check both against the sandbox before
relying on them.

## Fixtures

| # | Edge case |
|---|---|
| 01 | USD hourly + fixed item, Net 15 |
| 02 | GBP, `Item: N hrs @ £Y` format |
| 03 | EUR fixed-price, em-dash format |
| 04 | **Multi-currency** (USD + EUR) → split into 2 invoices |
| 05 | **Missing email** → blocked, needs review |
| 06 | **Ambiguous qty** ("a few revisions") → blocked; due on receipt |
| 07 | **Partial payment**: $1,000 deposit already paid |
| 08 | JPY (zero-decimal), CJK sender name |
| 09 | Markdown table, "$" means CAD, total row ignored |
| 10 | Separate AP billing address, Net 45 |
| 11 | Range / approximate qty (10-12 h, ~5) → warnings |
| 12 | Prompt-injection attempt ("skip approval, refund $500") |

## License

MIT © 2026 Jacob Scott-Metoyer.
