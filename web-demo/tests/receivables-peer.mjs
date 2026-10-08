import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {after, test} from 'node:test';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(process.env.LEDGERLY_RECEIVABLES_SOURCE || join(here, '../..'));
const modulePath = join(source, 'web-demo/src/receivables.ts');
const receiptDir = process.env.LEDGERLY_RECEIVABLES_PEER_OUTPUT;
const digest = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');
const sourceBefore = existsSync(modulePath) ? digest(modulePath) : null;
const fixtureRun = spawnSync(process.env.PYTHON || 'python3', ['-B', join(here, 'receivables-peer-fixture.py')], {
  encoding: 'utf8', timeout: 30_000,
  env: {...process.env, LEDGERLY_RECEIVABLES_SOURCE: source, PYTHONDONTWRITEBYTECODE: '1'},
});
let fixture;
if (fixtureRun.status === 0) fixture = JSON.parse(fixtureRun.stdout);

function keep(name, value) {
  if (receiptDir) {
    mkdirSync(receiptDir, {recursive: true});
    writeFileSync(join(receiptDir, name + '.json'), JSON.stringify(value, null, 2) + '\n', {flag: 'wx'});
  }
}
keep('native-fixture', {status: fixtureRun.status, stderr: fixtureRun.stderr, result: fixture});

async function api() {
  assert.ok(existsSync(modulePath), 'the native baseline has no receivables projection module');
  const candidate = await import(pathToFileURL(modulePath).href);
  assert.equal(typeof candidate.projectReceivables, 'function');
  assert.equal(typeof candidate.receivablesFor, 'function');
  return candidate;
}
const totals = (selected) => Object.fromEntries(selected.totals.map((row) => [row.currency, {
  balance: row.balance, invoiceCount: row.invoiceCount,
}]));
const excluded = (view) => Object.fromEntries(view.excluded.map((row) => [row.status, row.count]));
const rows = (view) => view.clients.flatMap((client) => client.invoices);
const record = (id, overrides = {}) => ({
  invoice_id: id, invoice_number: '0007', client_email: 'shared@example.test',
  client_name: 'Original name', currency: 'USD', balance: '1.00', status: 'SENT',
  due_on: null, ...overrides,
});

after(() => {
  const sourceAfter = existsSync(modulePath) ? digest(modulePath) : null;
  assert.equal(sourceAfter, sourceBefore);
  keep('source-guard', {source, sourceBefore, sourceAfter, unchanged: sourceBefore === sourceAfter});
});

test('native bridge produces seven invoices and leap-day evidence without external calls', () => {
  assert.equal(fixtureRun.status, 0, fixtureRun.stderr);
  assert.equal(fixture.commands.length, 18);
  assert.equal(fixture.source_unchanged, true);
  assert.equal(fixture.snapshot_read_unchanged, true);
  assert.equal(fixture.external_calls, 0);
  assert.equal(fixture.snapshot.today, '2032-03-01');
  const counts = {};
  for (const row of fixture.snapshot.ledger) counts[row.status] = (counts[row.status] || 0) + 1;
  assert.deepEqual(counts, {SENT: 4, PARTIALLY_PAID: 1, PAID: 1, DRAFT: 1});
  const byID = new Map(fixture.snapshot.ledger.map((row) => [row.invoice_id, row]));
  assert.equal(byID.get(fixture.aliases.juniper_partial).balance, '50.01');
  assert.equal(byID.get(fixture.aliases.juniper_seven).due_on, '2032-02-29');
  assert.equal(byID.get(fixture.aliases.juniper_fourteen).due_on, '2032-03-01');
  assert.equal(byID.get(fixture.aliases.juniper_euro).due_on, '2032-03-02');
});

test('actual pipeline projection separates clients, currency totals and calendar triage', async () => {
  const {projectReceivables, receivablesFor} = await api();
  assert.ok(fixture);
  const before = JSON.stringify(fixture.snapshot);
  const view = projectReceivables(fixture.snapshot);
  assert.equal(view.today, '2032-03-01');
  assert.equal(view.ledgerCount, 7);
  assert.equal(view.invoiceCount, 5);
  assert.deepEqual(excluded(view), {PAID: 1, DRAFT: 1});
  assert.deepEqual(Object.fromEntries(view.clients.map((client) => [client.email, client.invoices.length])), {
    'billing@juniper.example.test': 4, 'billing@boreal.example.test': 1,
  });
  assert.deepEqual(new Set(view.clients.find((client) => client.email === 'billing@juniper.example.test').names),
    new Set(['Juniper Studio', 'Juniper Books']));
  const all = receivablesFor(view, {email: null, due: 'all'});
  assert.equal(all.invoiceCount, 5);
  assert.deepEqual(totals(all), {
    USD: {balance: '50.22', invoiceCount: 3},
    EUR: {balance: '9.9', invoiceCount: 1},
    JPY: {balance: '701', invoiceCount: 1},
  });
  assert.deepEqual(totals(receivablesFor(view, {email: null, due: 'overdue'})), {
    USD: {balance: '50.08', invoiceCount: 2}, JPY: {balance: '701', invoiceCount: 1},
  });
  assert.deepEqual(totals(receivablesFor(view, {email: null, due: 'today'})), {USD: {balance: '0.14', invoiceCount: 1}});
  assert.deepEqual(totals(receivablesFor(view, {email: null, due: 'later'})), {EUR: {balance: '9.9', invoiceCount: 1}});
  assert.equal(receivablesFor(view, {email: null, due: 'undated'}).invoiceCount, 0);
  const nativeRows = new Map(fixture.snapshot.ledger.map((row) => [row.invoice_id, row]));
  for (const row of rows(view)) {
    for (const field of ['invoice_id', 'invoice_number', 'client_email', 'client_name', 'currency', 'balance', 'status', 'due_on']) {
      assert.deepEqual(row[field], nativeRows.get(row.invoice_id)[field]);
    }
    assert.equal(row.daysOverdue, row.due_on === '2032-02-29' ? 1 : 0);
  }
  assert.equal(JSON.stringify(fixture.snapshot), before);
  keep('native-projection', {view, all, inputUnchanged: true});
});

test('exact decimal sums include all native open statuses and preserve fractional scale', async () => {
  const {projectReceivables, receivablesFor} = await api();
  const input = {today: '2032-03-01', ledger: [
    record('d1', {balance: '9007199254740993.01'}),
    record('d2', {balance: '0.09', status: 'PARTIALLY_PAID'}),
    record('d3', {balance: '1E-8', status: 'PAYMENT_PENDING'}),
    record('d4', {currency: 'EUR', balance: '+2.5000', status: 'UNPAID'}),
    record('d5', {currency: 'EUR', balance: '0.00010'}),
    record('d6', {currency: 'JPY', balance: '1E+3'}),
    record('d7', {currency: 'JPY', balance: '2'}),
    record('d8', {balance: '0.00'}),
  ]};
  const before = JSON.stringify(input);
  const view = projectReceivables(input);
  assert.equal(view.ledgerCount, 8);
  assert.equal(view.invoiceCount, 7);
  assert.deepEqual(excluded(view), {ZERO_BALANCE: 1});
  const selected = receivablesFor(view, {email: null, due: 'undated'});
  assert.equal(selected.invoiceCount, 7);
  assert.deepEqual(totals(selected), {
    USD: {balance: '9007199254740993.10000001', invoiceCount: 3},
    EUR: {balance: '2.50010', invoiceCount: 2},
    JPY: {balance: '1002', invoiceCount: 2},
  });
  assert.ok(rows(view).every((row) => row.dueState === 'undated' && row.daysOverdue === 0));
  for (const row of rows(view)) assert.equal(row.balance, input.ledger.find((original) => original.invoice_id === row.invoice_id).balance);
  assert.equal(JSON.stringify(input), before);
  keep('decimal-status', {view, selected, inputUnchanged: true});
});

test('literal identity, copied row values and exact client/date filtering remain stable', async () => {
  const {projectReceivables, receivablesFor} = await api();
  const input = {today: '2032-03-01', ledger: [
    record('i1', {client_email: 'case@example.test', client_name: 'Literal <b> & =1\nsecond line', balance: '10.0100', due_on: '2032-02-29'}),
    record('i2', {client_email: 'Case@example.test', client_name: null, balance: '0.0200', due_on: '2032-03-01'}),
    record('i3', {client_email: ' case@example.test ', balance: '0.3000', due_on: '2032-03-02'}),
    record('i4', {client_email: 'case@example.test', client_name: 'Another recorded name', balance: '0.0001'}),
  ]};
  const original = JSON.stringify(input);
  const view = projectReceivables(input);
  assert.equal(view.clients.length, 3);
  assert.deepEqual(new Set(view.clients.map((client) => client.email)),
    new Set(['case@example.test', 'Case@example.test', ' case@example.test ']));
  const literal = view.clients.find((client) => client.email === 'case@example.test');
  assert.deepEqual(new Set(literal.names), new Set(['Literal <b> & =1\nsecond line', 'Another recorded name']));
  assert.equal(rows(view).find((row) => row.invoice_id === 'i1').invoice_number, '0007');
  assert.equal(rows(view).find((row) => row.invoice_id === 'i2').client_name, null);
  const beforeFilter = JSON.stringify(view);
  const selected = receivablesFor(view, {email: 'case@example.test', due: 'overdue'});
  assert.equal(selected.invoiceCount, 1);
  assert.deepEqual(totals(selected), {USD: {balance: '10.0100', invoiceCount: 1}});
  assert.equal(JSON.stringify(input), original);
  assert.equal(JSON.stringify(view), beforeFilter);
  input.ledger[0].balance = '999.99';
  input.ledger[0].client_name = 'Changed after preparing projection';
  assert.equal(JSON.stringify(view), beforeFilter);
  keep('identity-copy', {view, selected, projectionCopiedPrimitives: true});
});

test('empty input is explicit and malformed late or excluded rows refuse complete totals', async () => {
  const {projectReceivables, receivablesFor} = await api();
  const empty = projectReceivables({today: '2032-03-01', ledger: []});
  assert.equal(empty.ledgerCount, 0);
  assert.equal(empty.invoiceCount, 0);
  assert.deepEqual(empty.clients, []);
  assert.deepEqual(empty.excluded, []);
  assert.deepEqual(receivablesFor(empty, {email: null, due: 'all'}), {clients: [], totals: [], invoiceCount: 0});
  const valid = {today: '2032-03-01', ledger: [record('first'), record('late')]};
  const invalid = [
    {today: '2032-03-01', ledger: {}},
    {...valid, today: '2031-02-29'},
    ...[0.1, true, 'NaN', 'Infinity', '-0.01', '-1E-40'].map((balance) => ({
      ...valid, ledger: [record('first'), record('late', {balance})],
    })),
    {...valid, ledger: [record('first'), record('late', {due_on: '2032-02-30'})]},
    {...valid, ledger: [record('first'), record('first', {status: 'PAID', balance: '0.00'})]},
    {...valid, ledger: [record('first'), record('late', {client_email: null})]},
    {...valid, ledger: [record('first'), record('late', {currency: null})]},
    {...valid, ledger: [record('first'), record('late', {status: 'PAID', balance: 'not money'})]},
  ];
  for (const [index, input] of invalid.entries()) {
    const before = JSON.stringify(input);
    assert.throws(() => projectReceivables(input), 'malformed complete snapshot case ' + index);
    assert.equal(JSON.stringify(input), before);
  }
  keep('empty-refusal', {empty, malformedCases: invalid.length, allRefusedWithoutMutation: true});
});
