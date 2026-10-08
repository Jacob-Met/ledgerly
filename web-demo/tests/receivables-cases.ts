import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

type Project = (snapshot: unknown) => any;
type Select = (view: any, filter: {email: string | null; due: string}) => any;
type Case = {name: string; run: (project: Project, select: Select) => void};

function invoice(overrides: Record<string, unknown> = {}) {
  return {
    invoice_id: 'INV-A', invoice_number: '0001', client_email: 'client@example.test',
    client_name: 'Client', currency: 'USD', balance: '1.00', status: 'SENT', due_on: '2026-10-08',
    ...overrides,
  };
}
function snapshot(ledger: unknown[], today = '2026-10-08') { return {today, ledger}; }
function all(view: any, select: Select) { return select(view, {email: null, due: 'all'}); }
function total(selection: any, currency: string) {
  return selection.totals.find((row: any) => row.currency === currency)?.balance;
}
export const receivablesCases: Case[] = [
  {name: 'actual native mixed-client ledger preserves exact remaining balances and separate currencies',
   run(project, select) {
     const native = JSON.parse(readFileSync(new URL('./fixtures/receivables-native-snapshot.json', import.meta.url), 'utf8'));
     const view = project(native);
     assert.equal(view.ledgerCount, 6); assert.equal(view.invoiceCount, 4);
     assert.equal(view.today, '2026-10-15');
     assert.deepEqual(view.excluded, [{status: 'DRAFT', count: 1}, {status: 'PAID', count: 1}]);
     const north = select(view, {email: 'north@example.test', due: 'all'});
     assert.equal(north.invoiceCount, 3);
     assert.equal(total(north, 'USD'), '0.3'); assert.equal(total(north, 'EUR'), '12.3');
     assert.equal(total(select(view, {email: 'south@example.test', due: 'all'}), 'USD'), '100.50');
     assert.equal(total(all(view, select), 'USD'), '100.80');
     assert.deepEqual(view.clients.flatMap((group: any) => group.invoices.map((row: any) => row.dueState)).sort(),
       ['later', 'overdue', 'overdue', 'today']);
   }},
  {name: 'decimal addition preserves cents beyond safe integers and scientific native strings',
   run(project, select) {
     const view = project(snapshot([
       invoice({invoice_id: 'large', balance: '9007199254740993.01'}),
       invoice({invoice_id: 'cents', balance: '0.09'}),
       invoice({invoice_id: 'exponent', balance: '1E+2'}),
     ]));
     assert.equal(total(all(view, select), 'USD'), '9007199254741093.10');
     assert.equal(view.clients[0].invoices.find((row: any) => row.invoice_id === 'exponent').balance, '1E+2');
   }},
  {name: 'fraction scale is exact and currencies are never pooled',
   run(project, select) {
     const view = project(snapshot([
       invoice({invoice_id: 'a', balance: '1.005'}),
       invoice({invoice_id: 'b', balance: '0.0005'}),
       invoice({invoice_id: 'c', balance: '0.9945'}),
       invoice({invoice_id: 'd', currency: 'JPY', balance: '300'}),
       invoice({invoice_id: 'e', currency: 'JPY', balance: '20'}),
     ]));
     assert.deepEqual(all(view, select).totals, [
       {currency: 'JPY', balance: '320', invoiceCount: 2},
       {currency: 'USD', balance: '2.0000', invoiceCount: 3},
     ]);
   }},
  {name: 'only the four native open states with positive balance enter receivables',
   run(project, select) {
     const statuses = ['SENT', 'UNPAID', 'PARTIALLY_PAID', 'PAYMENT_PENDING', 'DRAFT', 'PAID',
       'MARKED_AS_PAID', 'CANCELLED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'SCHEDULED'];
     const view = project(snapshot(statuses.map((status, n) => invoice({invoice_id: String(n), status}))));
     assert.equal(view.invoiceCount, 4); assert.equal(total(all(view, select), 'USD'), '4.00');
     assert.equal(view.excluded.reduce((n: number, row: any) => n + row.count, 0), 7);
     assert.deepEqual(view.clients[0].invoices.map((row: any) => row.status).sort(),
       ['PARTIALLY_PAID', 'PAYMENT_PENDING', 'SENT', 'UNPAID']);
   }},
  {name: 'zero balances are outside the positive open view with an explicit count',
   run(project, select) {
     const view = project(snapshot([invoice({balance: '0.00'}), invoice({invoice_id: 'b', balance: '-0E-2'})]));
     assert.equal(view.invoiceCount, 0); assert.deepEqual(view.clients, []);
     assert.deepEqual(view.excluded, [{status: 'ZERO_BALANCE', count: 2}]);
     assert.deepEqual(all(view, select).totals, []);
   }},
  {name: 'Gregorian leap-day and undated boundaries do not depend on the local timezone',
   run(project, select) {
     const view = project(snapshot([
       invoice({invoice_id: 'before', due_on: '2024-02-28'}),
       invoice({invoice_id: 'same', due_on: '2024-02-29'}),
       invoice({invoice_id: 'after', due_on: '2024-03-01'}),
       invoice({invoice_id: 'unknown', due_on: null}),
     ], '2024-02-29'));
     const keyed = Object.fromEntries(view.clients[0].invoices.map((row: any) => [row.invoice_id, row]));
     assert.deepEqual(Object.values(keyed).map((row: any) => [row.dueState, row.daysOverdue]).sort(),
       [['later', 0], ['overdue', 1], ['today', 0], ['undated', 0]]);
     assert.equal(select(view, {email: null, due: 'undated'}).invoiceCount, 1);
   }},
  {name: 'exact billing email is identity while names remain literal display facts',
   run(project, select) {
     const view = project(snapshot([
       invoice({invoice_id: 'a', client_email: 'Case@example.test', client_name: 'Same name'}),
       invoice({invoice_id: 'b', client_email: 'case@example.test', client_name: 'Same name'}),
       invoice({invoice_id: 'c', client_email: 'case@example.test', client_name: 'Updated <name> & Co'}),
       invoice({invoice_id: 'd', client_email: ' case@example.test ', client_name: null}),
     ]));
     assert.equal(view.clients.length, 3);
     const group = view.clients.find((row: any) => row.email === 'case@example.test');
     assert.deepEqual(group.names, ['Same name', 'Updated <name> & Co']);
     assert.equal(select(view, {email: 'Case@example.test', due: 'all'}).invoiceCount, 1);
     assert.equal(total(select(view, {email: 'case@example.test', due: 'all'}), 'USD'), '2.00');
   }},
  {name: 'client and due filters compose without changing the full snapshot or its totals',
   run(project, select) {
     const raw = snapshot([
       invoice({invoice_id: 'a', client_email: 'a@example.test', due_on: '2026-10-07', balance: '2.10'}),
       invoice({invoice_id: 'b', client_email: 'a@example.test', due_on: '2026-10-08', balance: '3.20'}),
       invoice({invoice_id: 'c', client_email: 'b@example.test', due_on: '2026-10-07', balance: '4.30'}),
     ]);
     const before = JSON.stringify(raw); const view = project(raw); const original = JSON.stringify(view);
     const selected = select(view, {email: 'a@example.test', due: 'overdue'});
     assert.equal(selected.invoiceCount, 1); assert.equal(total(selected, 'USD'), '2.10');
     assert.equal(total(all(view, select), 'USD'), '9.60');
     assert.equal(select(view, {email: 'missing@example.test', due: 'all'}).invoiceCount, 0);
     assert.equal(JSON.stringify(view), original); assert.equal(JSON.stringify(raw), before);
   }},
  {name: 'the prepared view detaches native row and client text from later input mutation',
   run(project, select) {
     const raw = snapshot([invoice({client_name: 'Zoë <AP>\n& literal', balance: '7.50'})]);
     const view = project(raw);
     (raw.ledger[0] as any).balance = '999';
     (raw.ledger[0] as any).client_name = 'different';
     raw.ledger.push(invoice({invoice_id: 'new'}));
     assert.equal(total(all(view, select), 'USD'), '7.50');
     assert.deepEqual(view.clients[0].names, ['Zoë <AP>\n& literal']);
     assert.equal(view.invoiceCount, 1);
   }},
  {name: 'empty sandbox is a complete empty view',
   run(project, select) {
     const view = project(snapshot([]));
     assert.equal(view.ledgerCount, 0); assert.equal(view.invoiceCount, 0);
     assert.deepEqual(view.clients, []); assert.deepEqual(view.excluded, []);
     assert.deepEqual(all(view, select), {clients: [], totals: [], invoiceCount: 0});
   }},
  {name: 'ambiguous identity or malformed values refuse the complete projection',
   run(project) {
     const invalid = [
       snapshot([invoice(), invoice()]),
       snapshot([invoice({balance: 1})]), snapshot([invoice({balance: 'NaN'})]),
       snapshot([invoice({balance: 'Infinity'})]), snapshot([invoice({balance: '-0.01'})]),
       snapshot([invoice({balance: '1,000.00'})]), snapshot([invoice({balance: '1e10001'})]),
       snapshot([invoice({due_on: '2026-02-29'})]), snapshot([invoice({due_on: ''})]),
       snapshot([invoice({currency: 'usd'})]), snapshot([invoice({client_email: ''})]),
       snapshot([invoice({invoice_id: ''})]), snapshot([invoice({client_name: 5})]),
       snapshot([invoice()], '2026-02-29'), {today: '2026-10-08'}, null,
     ];
     for (const value of invalid) assert.throws(() => project(value), Error);
   }},
  {name: 'malformed non-open records also prevent a misleading partial ledger total',
   run(project) {
     assert.throws(() => project(snapshot([
       invoice({invoice_id: 'healthy', balance: '50.00'}),
       invoice({invoice_id: 'draft', status: 'DRAFT', balance: 'broken'}),
     ])), Error);
   }},
];
