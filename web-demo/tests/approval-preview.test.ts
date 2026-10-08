import {beforeAll, expect, it} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {loadPyodide} from 'pyodide';
import {approvalCardMarkup, approvalListMarkup, type PendingApproval} from '../src/approval-preview';

const escaped = (value: string) => value.replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));

it('renders exact multiline reminder content and action identifiers as literal text', () => {
  const action: PendingApproval = {
    id: 'apv_"><img src=x onerror=alert(1)>',
    invoice_id: 'INV <one>', kind: 'send_reminder', summary: 'To client & partner',
    payload: {subject: 'Résumé & <review>', note: 'Hello <script>alert(1)</script>,\n\nPay "USD 0.015" to كريم.\nThanks.'},
  };
  const before = JSON.stringify(action);
  const result = approvalCardMarkup(action);
  expect(result).toContain(escaped((action.payload as any).subject));
  expect(result).toContain(escaped((action.payload as any).note));
  expect(result).toContain('data-approve="' + escaped(action.id) + '"');
  expect(result).toContain('data-reject="' + escaped(action.id) + '"');
  expect(result).not.toContain('<script>');
  expect(result).not.toContain('<img');
  expect(JSON.stringify(action)).toBe(before);
});

it('keeps queued invoice values exact without rounding or merging currencies', () => {
  const action: PendingApproval = {
    id: 'apv_exact', invoice_id: 'INV-EXACT', kind: 'send_invoice', summary: 'Exact queued summary',
    payload: {prepaid: '0.00000000000000000001', invoice: {
      detail: {invoice_number: 'NUMBER-A', currency_code: 'USD', invoice_date: '2026-10-01',
        payment_term: {term_type: 'NET_30', due_date: '2026-10-31'}, note: 'Line one\nLine <two>'},
      invoicer: {name: {given_name: 'Studio', surname: 'A'}, email_address: 'studio@example.test'},
      primary_recipients: [{billing_info: {name: {given_name: 'Queued', surname: 'Client'}, email_address: 'queued@example.test'}}],
      items: [{name: 'Item <literal>', quantity: '9007199254740993.5',
        unit_amount: {currency_code: 'USD', value: '0.01500000000000000001'}, unit_of_measure: 'HOURS'}],
    }},
  };
  const result = approvalCardMarkup(action);
  for (const value of ['queued@example.test', 'Queued Client', 'studio@example.test',
    '9007199254740993.5 hr', 'USD 0.01500000000000000001',
    'USD 0.00000000000000000001', 'Net 30 days', '2026-10-31'])
    expect(result).toContain(value);
  expect(result).toContain('Item &lt;literal&gt;');
  expect(result).toContain('Line one\nLine &lt;two&gt;');
  expect(result).not.toContain('NaN');
});

it('does not invent a date for a queued due-on-receipt invoice', () => {
  const result = approvalCardMarkup({
    id: 'apv_receipt', invoice_id: 'INV-R', kind: 'send_invoice', summary: 'Receipt draft',
    payload: {invoice: {detail: {invoice_date: '2026-10-01', payment_term: {term_type: 'DUE_ON_RECEIPT'}}}},
  });
  expect(result).toContain('Due on receipt');
  expect(result).not.toContain('<dt>Due date</dt>');
});

it('renders every recipient and replaces an invalidated queue with its existing empty state', () => {
  const queued: PendingApproval = {
    id: 'apv_multiple', invoice_id: 'INV-M', kind: 'send_invoice', summary: 'Queued invoice',
    payload: {invoice: {primary_recipients: [
      {billing_info: {email_address: 'first@example.test'}},
      {billing_info: {email_address: 'second@example.test'}},
    ]}},
  };
  expect(approvalListMarkup([queued])).toContain('first@example.test\nsecond@example.test');
  expect(approvalListMarkup([])).toBe('<p class="empty">No approvals waiting. Sends and reminders stay queued until you choose.</p>');
  expect(approvalListMarkup([])).not.toContain('data-approve');
});

let py: any;
const web = process.cwd();
const fixture = (name: string) => fs.readFileSync(path.join(web, 'public', 'fixtures', name), 'utf8');
async function call(action: string, payload: Record<string, unknown> = {}) {
  py.globals.set('request_json', JSON.stringify({action, ...payload}));
  try { return JSON.parse(String(await py.runPythonAsync('bridge.handle_json(request_json)'))); }
  finally { py.globals.delete('request_json'); }
}
function effectState() {
  return String(py.runPython('json.dumps({"requests": bridge.SESSION.mock.requests, "pending": {k: v.to_dict() for k, v in bridge.SESSION.agent.pending.items()}, "audit": bridge.SESSION.agent.audit}, default=str, sort_keys=True)'));
}
beforeAll(async () => {
  py = await loadPyodide();
  py.FS.mkdirTree('/demo/ledgerly');
  for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py'])
    py.FS.writeFile('/demo/ledgerly/' + name, fs.readFileSync(path.join(web, 'public', 'python', 'ledgerly', name), 'utf8'));
  for (const name of ['bridge.py', 'review.py'])
    py.FS.writeFile('/demo/' + name, fs.readFileSync(path.join(web, 'public', 'python', name), 'utf8'));
  await py.runPythonAsync("import sys, json; sys.path.insert(0, '/demo'); import bridge");
});

it('previews the actual queued invoice after a different email is analyzed without any effect', async () => {
  await call('reset');
  const drafted = await call('draft', {text: fixture('01_simple_usd_hourly.txt')});
  expect(drafted.ok).toBe(true);
  const pending = drafted.state.pending[0];
  const invoice = pending.payload.invoice;
  const changed = await call('analyze', {text: fixture('02_gbp_proofreading.txt')});
  expect(changed.ok).toBe(true);
  expect(changed.result.client_email).not.toBe(invoice.primary_recipients[0].billing_info.email_address);
  const before = effectState();
  const result = approvalListMarkup(changed.state.pending);
  expect(result).toContain(escaped(invoice.primary_recipients[0].billing_info.email_address));
  for (const line of invoice.items) {
    expect(result).toContain(escaped(line.name));
    expect(result).toContain(escaped(line.unit_amount.value));
  }
  expect(result).not.toContain(escaped(changed.result.client_email));
  expect(effectState()).toBe(before);
  expect(drafted.result.unauthorized_send_blocked).toBe(true);
  expect(drafted.state.ledger[0].status).toBe('DRAFT');
});

it('shows the actual queued reminder subject and body that the existing approval sends', async () => {
  await call('reset');
  const drafted = await call('draft', {text: fixture('01_simple_usd_hourly.txt')});
  const sent = await call('approve', {action_id: drafted.state.pending[0].id});
  expect(sent.ok).toBe(true);
  const due = new Date(sent.state.ledger[0].due_on + 'T00:00:00Z');
  due.setUTCDate(due.getUTCDate() + 2);
  await call('advance', {day: due.toISOString().slice(0, 10)});
  const chase = await call('chase');
  const pending = chase.state.pending.find((action: any) => action.kind === 'send_reminder');
  expect(pending).toBeTruthy();
  const before = effectState();
  const result = approvalCardMarkup(pending);
  expect(result).toContain(escaped(pending.payload.subject));
  expect(result).toContain(escaped(pending.payload.note));
  expect(result).not.toContain('reviewed_facts');
  expect(result).not.toContain('reviewed_invoice');
  expect(effectState()).toBe(before);
  const approved = await call('approve', {action_id: pending.id});
  expect(approved.ok).toBe(true);
  const effects = JSON.parse(String(py.runPython('json.dumps([body for method, path, body in bridge.SESSION.mock.requests if path.endswith("/remind")])')));
  expect(effects).toHaveLength(1);
  expect(effects[0]).toMatchObject({subject: pending.payload.subject, note: pending.payload.note});
  expect(approved.state.pending).toHaveLength(0);
  expect(approved.state.ledger[0].reminders_sent).toBe(1);
  expect(approved.state.external_calls).toBe(0);
});

it('keeps separate currency actions and rejection independent while displaying the queued deposit', async () => {
  await call('reset');
  const split = await call('draft', {text: fixture('04_multi_currency.txt')});
  expect(split.state.pending).toHaveLength(2);
  const [first, second] = split.state.pending;
  const before = effectState();
  const markup = approvalListMarkup(split.state.pending);
  for (const pending of split.state.pending) {
    expect(markup).toContain('data-approval-id="' + pending.id + '"');
    expect(markup).toContain(escaped(pending.payload.invoice.items[0].unit_amount.currency_code));
  }
  expect(effectState()).toBe(before);
  const rejected = await call('reject', {action_id: first.id});
  expect(rejected.ok).toBe(true);
  expect(rejected.state.pending.map((action: any) => action.id)).toEqual([second.id]);
  expect(rejected.state.mock_requests).toBe(split.state.mock_requests);
  expect(approvalListMarkup(rejected.state.pending)).not.toContain(first.id);
  await call('reset');
  const deposit = await call('draft', {text: fixture('07_partial_payment_deposit.txt')});
  expect(deposit.ok).toBe(true);
  const pending = deposit.state.pending[0];
  expect(pending.payload.prepaid).not.toBe('0');
  expect(approvalCardMarkup(pending)).toContain(escaped(pending.payload.invoice.detail.currency_code + ' ' + pending.payload.prepaid));
  expect(deposit.state.ledger[0].status).toBe('DRAFT');
});
