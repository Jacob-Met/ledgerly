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
function editable(ex: any) {
  return {
    client_name: ex.client_name || 'Fictional client', client_email: ex.client_email || 'billing@example.test',
    due_days: String(ex.due_days ?? 30), amount_paid: String(ex.amount_paid ?? '0'),
    line_items: ex.line_items.map((row: any) => ({desc: row.desc, qty: String(row.qty ?? '1'), unit_price: String(row.unit_price), currency: row.currency || ex.currency || '', unit: row.unit || ''})),
  };
}
async function analyze(name = '05_missing_email.txt') {
  await call('reset');
  const text = fixture(name);
  const response = await call('analyze', {text});
  expect(response.ok).toBe(true);
  return {text, original: response.result, fields: editable(response.result)};
}
beforeAll(async () => {
  py = await loadPyodide();
  py.FS.mkdirTree('/demo/ledgerly');
  for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py'])
    py.FS.writeFile('/demo/ledgerly/' + name, fs.readFileSync(path.join(web, 'public', 'python', 'ledgerly', name), 'utf8'));
  for (const name of ['bridge.py', 'review.py']) {
    const source = path.join(web, 'public', 'python', name);
    if (fs.existsSync(source)) py.FS.writeFile('/demo/' + name, fs.readFileSync(source, 'utf8'));
  }
  await py.runPythonAsync("import sys; sys.path.insert(0, '/demo'); import bridge");
});

it('lets a visitor correct a missing recipient without changing the extraction or approving a send', async () => {
  const {text, original, fields} = await analyze();
  expect(original.issues.some((issue: any) => issue.field === 'client_email' && issue.severity === 'error')).toBe(true);
  const blocked = await call('draft', {text});
  expect(blocked.state.ledger).toHaveLength(0);
  fields.due_days = '0';
  const checked = await call('review', {text, fields, confirmed: true});
  expect(checked.ok).toBe(true);
  expect(checked.result.valid).toBe(true);
  expect(checked.result.source).toBe('human_review');
  expect(checked.result.original_issues).toEqual(original.issues);
  expect(checked.state.mock_requests).toBe(0);
  expect(checked.state.pending).toHaveLength(0);
  const draft = await call('draft', {text, review_id: checked.result.review_id});
  expect(draft.result.unauthorized_send_blocked).toBe(true);
  expect(draft.state.mock_requests).toBe(3);
  expect(draft.state.ledger).toHaveLength(1);
  expect(draft.state.ledger[0]).toMatchObject({client_email: fields.client_email, status: 'DRAFT', total: original.total});
  const pending = draft.state.pending[0];
  expect(pending.kind).toBe('send_invoice');
  const sent = await call('approve', {action_id: pending.id});
  expect(sent.state.ledger[0].status).toBe('SENT');
  expect(sent.state.ledger[0].due_on).toBe(sent.state.today);
  expect(sent.state.external_calls).toBe(0);
  const originalAgain = await call('analyze', {text});
  expect(originalAgain.result.issues).toEqual(original.issues);
  expect(originalAgain.result.client_email).toEqual(original.client_email);
});

it('requires explicit confirmation and refuses client-supplied derived metadata', async () => {
  const {text, fields} = await analyze();
  for (const confirmed of [false, 'true', 1, null]) {
    const result = await call('review', {text, fields, confirmed});
    expect(result.ok).toBe(false);
    expect(result.state.mock_requests).toBe(0);
  }
  const forged = await call('review', {text, fields: {...fields, confidence: 1, issues: [], source: 'rules'}, confirmed: true});
  expect(forged.ok).toBe(false);
  expect(forged.state.ledger).toHaveLength(0);
});

it('keeps invalid recipient, quantity, price, currency and terms out of the draft queue', async () => {
  const {text, fields} = await analyze();
  const mutations = [
    (f: any) => {f.client_email = 'not-an-email';},
    (f: any) => {f.line_items[0].qty = '0';},
    (f: any) => {f.line_items[0].qty = '-2';},
    (f: any) => {f.line_items[0].unit_price = '0';},
    (f: any) => {f.line_items[0].currency = 'ZZZ';},
    (f: any) => {f.line_items[0].desc = '';},
    (f: any) => {f.due_days = '366';},
    (f: any) => {f.amount_paid = '-1';},
    (f: any) => {f.line_items = [];},
  ];
  for (const mutate of mutations) {
    const invalid = structuredClone(fields); mutate(invalid);
    const result = await call('review', {text, fields: invalid, confirmed: true});
    expect(result.ok).toBe(true);
    expect(result.result.valid).toBe(false);
    expect(result.result.review_id).toBeNull();
    expect(result.result.issues.some((issue: any) => issue.severity === 'error')).toBe(true);
    expect(result.state.ledger).toHaveLength(0);
    expect(result.state.mock_requests).toBe(0);
  }
});

it('refuses non-finite and ambiguous numeric edits before invoice side effects', async () => {
  const {text, fields} = await analyze();
  for (const number of ['NaN', 'Infinity', '-Infinity', '1e10000', '1,200', '', 'two', 'true']) {
    const invalid = structuredClone(fields); invalid.line_items[0].qty = number;
    const result = await call('review', {text, fields: invalid, confirmed: true});
    expect(result.ok).toBe(false);
    expect(result.state.mock_requests).toBe(0);
  }
  for (const days of ['1.5', '-1', 'NaN']) {
    const result = await call('review', {text, fields: {...fields, due_days: days}, confirmed: true});
    expect(result.ok).toBe(false);
    expect(result.state.pending).toHaveLength(0);
  }
});

it('consumes a checked revision once and refuses a stale revision without duplicate drafts', async () => {
  const {text, fields} = await analyze();
  const checked = await call('review', {text, fields, confirmed: true});
  expect(checked.result.valid).toBe(true);
  const payload = {text, review_id: checked.result.review_id};
  const first = await call('draft', payload);
  expect(first.state.ledger).toHaveLength(1);
  const repeated = await call('draft', payload);
  expect(repeated.ok).toBe(false);
  expect(repeated.state.ledger).toHaveLength(1);
  expect(repeated.state.mock_requests).toBe(first.state.mock_requests);
  const next = await call('review', {text, fields, confirmed: true});
  const changed = await call('draft', {text: text + '\nChanged source.', review_id: next.result.review_id});
  expect(changed.ok).toBe(false);
  expect(changed.state.ledger).toHaveLength(1);
  expect((await call('draft', {text, review_id: next.result.review_id})).ok).toBe(false);
});

it('invalidates checked fields after another analysis, failed correction or reset', async () => {
  const {text, fields} = await analyze();
  for (const invalidate of ['analyze', 'review', 'reset']) {
    await call('analyze', {text});
    const checked = await call('review', {text, fields, confirmed: true});
    expect(checked.result.valid).toBe(true);
    if (invalidate === 'review') await call('review', {text, fields: {...fields, client_email: ''}, confirmed: true});
    else await call(invalidate, {text});
    const stale = await call('draft', {text, review_id: checked.result.review_id});
    expect(stale.ok).toBe(false);
    expect(stale.state.ledger).toHaveLength(0);
    expect(stale.state.mock_requests).toBe(0);
  }
});

it('keeps per-currency totals separate and gates every reviewed split invoice', async () => {
  const {text, fields} = await analyze('04_multi_currency.txt');
  const checked = await call('review', {text, fields, confirmed: true});
  expect(checked.result.valid).toBe(true);
  expect(checked.result.totals_by_currency).toHaveLength(2);
  const draft = await call('draft', {text, review_id: checked.result.review_id});
  expect(draft.state.ledger).toHaveLength(2);
  expect(draft.state.ledger.every((entry: any) => entry.status === 'DRAFT')).toBe(true);
  expect(draft.result.unauthorized_send_blocked).toBe(true);
  expect(draft.state.pending).toHaveLength(2);
  expect(draft.state.external_calls).toBe(0);
  const deposit = await call('review', {text, fields: {...fields, amount_paid: '1'}, confirmed: true});
  expect(deposit.result.valid).toBe(false);
  expect(deposit.result.issues.some((issue: any) => issue.field === 'amount_paid' && issue.severity === 'error')).toBe(true);
});

it('preserves zero-decimal currency checks and requires a confirmed quantity', async () => {
  const {text, fields} = await analyze('08_jpy_zero_decimal.txt');
  fields.line_items[0].unit_price = '10.50';
  const fraction = await call('review', {text, fields, confirmed: true});
  expect(fraction.result.valid).toBe(false);
  expect(fraction.state.mock_requests).toBe(0);
  const ambiguous = await analyze('06_ambiguous_qty.txt');
  const checked = await call('review', {...ambiguous, confirmed: true});
  expect(checked.result.valid).toBe(true);
  const draft = await call('draft', {text: ambiguous.text, review_id: checked.result.review_id});
  expect(draft.state.ledger.length).toBeGreaterThan(0);
  expect(draft.result.unauthorized_send_blocked).toBe(true);
});
