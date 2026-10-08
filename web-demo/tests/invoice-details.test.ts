import {beforeAll, expect, it} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {loadPyodide} from 'pyodide';

let py: any;
const web = process.cwd();
const fixture = (name: string) => fs.readFileSync(path.join(web, 'public', 'fixtures', name), 'utf8');
async function call(action: string, payload: Record<string, unknown> = {}) {
  py.globals.set('request_json', JSON.stringify({action, ...payload}));
  try { return JSON.parse(String(await py.runPythonAsync('bridge.handle_json(request_json)'))); }
  finally { py.globals.delete('request_json'); }
}
beforeAll(async () => {
  py = await loadPyodide();
  py.FS.mkdirTree('/demo/ledgerly');
  for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py'])
    py.FS.writeFile('/demo/ledgerly/' + name, fs.readFileSync(path.join(web, 'public', 'python', 'ledgerly', name), 'utf8'));
  for (const name of ['bridge.py', 'review.py', 'invoice_details.py', 'review_history.py'])
    py.FS.writeFile('/demo/' + name, fs.readFileSync(path.join(web, 'public', 'python', name), 'utf8'));
  await py.runPythonAsync("import sys; sys.path.insert(0, '/demo'); import bridge");
});

it('keeps exact original items available when approval removes the queued payload', async () => {
  await call('reset');
  const drafted = await call('draft', {text: fixture('01_simple_usd_hourly.txt')});
  const before = drafted.state.invoice_details[0].record;
  expect(drafted.state.mock_requests).toBe(3);
  const approved = await call('approve', {action_id: drafted.state.pending[0].id});
  expect(approved.state.pending).toEqual([]);
  expect(approved.state.invoice_details[0].record.items).toEqual(before.items);
  expect(approved.state.invoice_details[0].record.primary_recipients).toEqual(before.primary_recipients);
  expect(approved.state.invoice_details[0].record.status).toBe('SENT');
  expect(approved.state.mock_requests).toBe(drafted.state.mock_requests + 2);
  const sentRequests = JSON.parse(String(await py.runPythonAsync(
    'bridge.json.dumps([request[:2] for request in bridge.SESSION.mock.requests[-2:]])'
  )));
  expect(sentRequests).toEqual([
    ['GET', `/v2/invoicing/invoices/${before.id}`],
    ['POST', `/v2/invoicing/invoices/${before.id}/send`],
  ]);
  expect(approved.state.external_calls).toBe(0);
});

it('reports a real partial payment and zero-decimal invoice through Python WASM', async () => {
  await call('reset');
  const drafted = await call('draft', {text: fixture('08_jpy_zero_decimal.txt')});
  const invoice = drafted.state.ledger[0].invoice_id;
  await call('approve', {action_id: drafted.state.pending[0].id});
  const paid = await call('payment', {invoice_id: invoice, amount: '1000'});
  const record = paid.state.invoice_details[0].record;
  expect(record.payments.transactions[0].amount).toEqual({currency_code: 'JPY', value: '1000'});
  expect(record.status).toBe('PARTIALLY_PAID');
  expect(record.amount.value).not.toContain('.');
  const replayed = await call('replay');
  expect(replayed.state.invoice_details).toEqual(paid.state.invoice_details);
});

it('keeps per-invoice currencies and original records after analyzing another input', async () => {
  await call('reset');
  const drafted = await call('draft', {text: fixture('04_multi_currency.txt')});
  expect(drafted.state.invoice_details.length).toBeGreaterThan(1);
  for (const entry of drafted.state.ledger) {
    const record = drafted.state.invoice_details.find((row: any) => row.invoice_id === entry.invoice_id).record;
    expect(record.id).toBe(entry.invoice_id);
    expect(record.detail.currency_code).toBe(entry.currency);
  }
  const analyzed = await call('analyze', {text: fixture('02_gbp_proofreading.txt')});
  expect(analyzed.state.invoice_details).toEqual(drafted.state.invoice_details);
  expect(analyzed.state.mock_requests).toBe(drafted.state.mock_requests);
});

it('copies nested records without mock requests and clears them on reset', async () => {
  await py.runPythonAsync("from copy import deepcopy\nrequests_before = deepcopy(bridge.SESSION.mock.requests)\nrecord_before = deepcopy(bridge.SESSION.mock.invoices)\ns = bridge.SESSION.snapshot()\ns['invoice_details'][0]['record']['items'][0]['name'] = 'Mutated browser copy'\nassert bridge.SESSION.mock.invoices == record_before\nassert bridge.SESSION.mock.requests == requests_before");
  const reset = await call('reset');
  expect(reset.state.invoice_details).toEqual([]);
  expect(reset.state.ledger).toEqual([]);
  expect(reset.state.mock_requests).toBe(0);
});
