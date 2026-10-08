import {describe, expect, it} from 'vitest';
import {ledgerCsv} from './ledger-export';

function invoice(overrides: Record<string, unknown> = {}) {
  return {
    invoice_id: 'INV-1', invoice_number: '0007', client_name: 'Example Client',
    client_email: 'billing@example.test', currency: 'USD', total: '1250.00',
    paid_amount: '300.00', balance: '950.00', status: 'PARTIALLY_PAID',
    sent_on: '2026-10-01', due_on: '2026-10-16', reminders_sent: 0, ...overrides,
  };
}

const snapshot = (ledger: unknown[]) => ({today: '2026-10-08', ledger});

describe('sandbox ledger CSV', () => {
  it('exports displayed amounts and each currency without arithmetic or aggregation', () => {
    const source = snapshot([
      invoice({total: '12345678901234567890.0100', paid_amount: '0.0000', balance: '12345678901234567890.0100'}),
      invoice({invoice_id: 'INV-2', currency: 'JPY', total: '1500', paid_amount: '250', balance: '1250'}),
    ]);
    const before = JSON.stringify(source);
    const csv = ledgerCsv(source);
    expect(csv.count).toBe(2);
    expect(csv.filename).toBe('ledgerly-sandbox-2026-10-08.csv');
    expect(csv.text).toContain('"USD","12345678901234567890.0100","0.0000","12345678901234567890.0100"');
    expect(csv.text).toContain('"JPY","1500","250","1250"');
    expect(csv.text.match(/"SANDBOX"/g)).toHaveLength(2);
    expect(csv.text).toContain('"0007"');
    expect(JSON.stringify(source)).toBe(before);
  });

  it('retains signed and scientific decimal strings without conversion', () => {
    const csv = ledgerCsv(snapshot([invoice({total: '1E+3', paid_amount: '-0.0100', balance: '+1000.0100'})]));
    expect(csv.text).toContain('"1E+3","-0.0100","+1000.0100"');
  });

  it('copies snapshot values so later object mutation cannot change a prepared download', () => {
    const entry = invoice();
    const source = snapshot([entry]);
    const prepared = ledgerCsv(source);
    entry.balance = '1.00';
    source.today = '2026-11-01';
    expect(prepared.filename).toBe('ledgerly-sandbox-2026-10-08.csv');
    expect(prepared.text).toContain('"950.00"');
    expect(ledgerCsv(source).text).toContain('"1.00"');
  });

  it('uses UTF-8, CSV quoting and literal multiline/Unicode names', () => {
    const csv = ledgerCsv(snapshot([invoice({client_name: '佐藤, "Design"\r\n第二行'})]));
    expect(csv.text.startsWith('\uFEFF"Record type"')).toBe(true);
    expect(csv.text).toContain('"佐藤, ""Design""\r\n第二行"');
    expect(csv.text.endsWith('\r\n')).toBe(true);
  });

  it.each(['=1+2', '+SUM(A1:A2)', '-1+2', '@SUM(1)', '\t=1', '\rtext', '\ntext', '  =1', '\u200B=1', '＝1', '＋1', '－1', '＠SUM(1)'])(
    'marks formula-like text as literal: %j', (name) => {
      expect(ledgerCsv(snapshot([invoice({client_name: name})])).text).toContain('"' + "'" + name + '"');
    },
  );

  it('keeps delimiters and quotes inside the same protected cell', () => {
    const csv = ledgerCsv(snapshot([invoice({client_name: '=1+2";=3,4'})]));
    expect(csv.text).toContain('"' + "'" + '=1+2"";=3,4"');
  });

  it('does not exempt formula text in an amount field from quoting', () => {
    expect(ledgerCsv(snapshot([invoice({total: '=SUM(A1:A2)'})])).text).toContain('"' + "'" + '=SUM(A1:A2)"');
  });

  it('retains missing dates as empty cells and the supplied status/reminder count', () => {
    const csv = ledgerCsv(snapshot([invoice({client_name: null, sent_on: null, due_on: null, status: 'DRAFT', reminders_sent: 2})]));
    expect(csv.text).toContain('"INV-1","0007","","billing@example.test"');
    expect(csv.text).toContain('"DRAFT","","","2"');
  });

  it('returns only a header for an empty ledger, with no invented record', () => {
    const csv = ledgerCsv(snapshot([]));
    expect(csv.count).toBe(0);
    expect(csv.text).not.toContain('"SANDBOX"');
    expect(csv.text.split('\r\n')).toHaveLength(2);
  });

  it.each([
    null, {}, {today: '../../private', ledger: []}, {today: '2026-10-08', ledger: {}},
    snapshot([null]), snapshot([invoice({total: 1250})]),
    snapshot([invoice({reminders_sent: -1})]), snapshot([invoice({reminders_sent: NaN})]),
    snapshot([invoice({reminders_sent: Number.MAX_SAFE_INTEGER + 1})]),
  ])('refuses incomplete shapes without manufacturing amounts: %j', (value) => {
    expect(() => ledgerCsv(value)).toThrow(/displayed ledger/);
  });
});
