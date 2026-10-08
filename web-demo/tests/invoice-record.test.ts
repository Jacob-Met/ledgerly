import {afterEach, describe, expect, it, vi} from 'vitest';
import {buildInvoiceRecord, createInvoiceRecordDownloads} from '../src/invoice-record';
import {invoiceDetailsMarkup} from '../src/invoice-details';
import detailStyles from '../src/invoice-details.css?raw';

const id = 'INV/one?<exact>';
const stamp = new Date('2026-10-08T14:15:16.123Z');
function source() {
  return {
    today: '2026-10-08',
    ledger: [{invoice_id: id, invoice_number: 'LDG-0001', client_name: '海 😀 Client',
      client_email: 'client@example.test', currency: 'USD', total: '4.20', paid_amount: '1.01',
      balance: '3.19', status: 'PARTIALLY_PAID', sent_on: '2026-10-07', due_on: '2026-10-30', reminders_sent: 2}],
    invoice_details: [{invoice_id: id, record: {
      id, status: 'PROVIDER-STATUS', detail: {invoice_number: 'PROVIDER-0001', invoice_date: '2026-10-01',
        payment_term: {term_type: 'NET_29', due_date: '2026-10-30'}, note: 'First line\n海 😀 & <literal> "quoted"'},
      primary_recipients: [{billing_info: {name: {given_name: 'Original', surname: 'Recipient'},
        email_address: 'retained@example.test', address: {address_line_1: 'Building <A>', admin_area_2: '東京'}}}],
      invoicer: {name: {given_name: 'Sandbox', surname: 'Issuer'}, email_address: 'issuer@example.test'},
      items: [{name: 'Original service', description: 'Two\nliteral lines', quantity: '3.000',
        unit_of_measure: 'HOURS', unit_amount: {currency_code: 'USD', value: '9007199254740993.01'}}],
      amount: {currency_code: 'USD', value: '9007199254740993.03'},
      payments: {paid_amount: {currency_code: 'USD', value: '3.3300'}, transactions: [
        {payment_date: '2026-10-07', amount: {currency_code: 'USD', value: '1.0100'}, type: 'OTHER', method: 'CASH', payment_id: 'PAY-ONE'},
        {payment_date: '2026-10-08', amount: {currency_code: 'USD', value: '2.3200'}, type: 'OTHER', method: 'BANK_TRANSFER', payment_id: 'PAY-TWO'},
      ]},
      due_amount: {currency_code: 'USD', value: '9007199254740989.7000'},
    }}],
    analysis: {client_name: 'PRIVATE ANALYSIS'},
    pending: [{proposal: 'PRIVATE PENDING'}],
    source_email: 'PRIVATE SOURCE EMAIL',
  };
}
const escape = (value: string) => value.replace(/[&<>"']/g,
  character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]!));

describe('standalone retained invoice documents', () => {
  it('keeps the exact existing detail renderer and its local styles beside the distinct ledger summary', () => {
    const snapshot = source(), before = structuredClone(snapshot);
    const output = buildInvoiceRecord(snapshot, id, stamp);
    expect(output.text).toContain(invoiceDetailsMarkup(id, snapshot, true));
    expect(output.text).toContain('<style>' + detailStyles);
    const displayed = [...output.text.matchAll(/<dd data-ledger-field="([^"]+)">([^]*?)<\/dd>/g)];
    expect(displayed.map(match => [match[1], match[2]])).toEqual(Object.entries(snapshot.ledger[0])
      .map(([key, value]) => [key, escape(String(value))]));
    for (const literal of ['9007199254740993.01', '9007199254740993.03', '9007199254740989.7000',
      '3.3300', '1.0100', '2.3200', 'PAY-ONE', 'PAY-TWO', 'PROVIDER-STATUS', 'PROVIDER-0001'])
      expect(output.text).toContain(literal);
    expect(snapshot).toEqual(before);
    expect(output.text).toContain('not a payable invoice');
    expect(output.text).toContain('id="invoice-record-snapshot">2026-10-08</span>');
    expect(output.text).toContain('id="invoice-record-created">2026-10-08T14:15:16.123Z</span>');
    expect(output.filename).toMatch(/^ledgerly-sandbox-invoice-[A-Za-z0-9_-]+\.html$/);
  });

  it('contains only the selected record, without private source, current analysis, proposals or another invoice', () => {
    const snapshot = source();
    const other = structuredClone(snapshot.invoice_details[0]);
    other.invoice_id = other.record.id = 'INV-other'; other.record.detail.note = 'OTHER INVOICE SECRET';
    snapshot.invoice_details.push(other);
    snapshot.ledger.push({...snapshot.ledger[0], invoice_id: 'INV-other', client_name: 'OTHER LEDGER SECRET'});
    const output = buildInvoiceRecord(snapshot, id, stamp).text;
    for (const absent of ['PRIVATE ANALYSIS', 'PRIVATE PENDING', 'PRIVATE SOURCE EMAIL',
      'OTHER INVOICE SECRET', 'OTHER LEDGER SECRET', 'INV-other']) expect(output).not.toContain(absent);
    expect((output.match(/class="invoice-details"/g) || []).length).toBe(1);
    expect(output).not.toMatch(/<script[^>]+\bsrc=|<link\b|<iframe\b|<form\b|<a\b|\bfetch\s*\(/i);
    expect((output.match(/<button\b/g) || []).length).toBe(1);
    expect(output).toContain('id="print-invoice-record"');
  });

  it('keeps Unicode, multiline descriptions and markup literal without adding executable elements', () => {
    const snapshot = source();
    const hostile = '海 😀 "</script><img src=x onerror=alert(1)>\nsecond\u2028third\u2029fourth';
    snapshot.invoice_details[0].record.detail.note = hostile;
    snapshot.invoice_details[0].record.items[0].description = hostile;
    snapshot.ledger[0].client_name = hostile;
    const output = buildInvoiceRecord(snapshot, id, stamp).text;
    expect(output).toContain(escape(hostile));
    expect((output.match(/<\/script>/g) || []).length).toBe(1);
    expect(output).not.toContain('<img');
    expect(output).toContain('white-space: pre-wrap');
    expect(output).toContain('@media print');
    expect(output).toContain("window.addEventListener('beforeprint', openRecord)");
    expect(output).toContain('window.print()');
  });

  it.each([['USD', '10.20'], ['EUR', '10.2000'], ['JPY', '5000']])(
    'preserves %s original amount text %s without currency conversion', (currency, amount) => {
      const snapshot = source();
      snapshot.ledger[0].currency = currency; snapshot.ledger[0].total = amount;
      snapshot.invoice_details[0].record.amount = {currency_code: currency, value: amount};
      const output = buildInvoiceRecord(snapshot, id, stamp).text;
      expect(output).toContain('<dd data-ledger-field="currency">' + currency + '</dd>');
      expect(output).toContain('<dd data-ledger-field="total">' + amount + '</dd>');
      expect(output).toContain('<dt>Provider invoice total</dt><dd>' + currency + ' ' + amount + '</dd>');
    });

  it('refuses missing, ambiguous and mismatched retained identities instead of a fallback', () => {
    const cases: any[] = [
      {...source(), ledger: []}, {...source(), invoice_details: []},
      {...source(), ledger: [source().ledger[0], source().ledger[0]]},
      {...source(), invoice_details: [source().invoice_details[0], source().invoice_details[0]]},
      {...source(), invoice_details: [{invoice_id: id, record: {id: 'OTHER'}}]},
      {...source(), invoice_details: [{invoice_id: 'OTHER', record: source().invoice_details[0].record}]},
      {...source(), ledger: {invoice_id: id}}, {...source(), invoice_details: {invoice_id: id}},
    ];
    for (const snapshot of cases) expect(() => buildInvoiceRecord(snapshot, id, stamp)).toThrow(/matching retained/);
    for (const today of [undefined, '', 42]) expect(() => buildInvoiceRecord({...source(), today}, id, stamp)).toThrow(/dated sandbox/);
    expect(() => buildInvoiceRecord(source(), '', stamp)).toThrow(/dated sandbox/);
  });

  it('refuses an oversized literal document or invalid creation time without changing its source', () => {
    const snapshot = source();
    snapshot.invoice_details[0].record.detail.note = '海'.repeat(1_500_000);
    const before = structuredClone(snapshot);
    expect(() => buildInvoiceRecord(snapshot, id, stamp)).toThrow(/4 MiB/);
    expect(snapshot).toEqual(before);
    expect(() => buildInvoiceRecord(source(), id, new Date('invalid'))).toThrow();
  });
});

afterEach(() => {
  if (vi.isFakeTimers()) vi.runOnlyPendingTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
});
function delivery() {
  vi.useFakeTimers();
  const button = {dataset: {saveInvoiceRecord: id}, disabled: false};
  const messages: string[] = [], blobs: Blob[] = [], downloaded: Array<{href: string; download: string}> = [];
  const allocations = vi.spyOn(URL, 'createObjectURL').mockImplementation(blob => {
    blobs.push(blob); return 'blob:owned/' + blobs.length;
  });
  const revocations = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  let receive!: (event: any) => void;
  const anchors: any[] = [];
  const container = {
    addEventListener: (_name: string, listener: (event: any) => void) => {receive = listener;},
    contains: (node: any) => node === button,
    querySelectorAll: () => [button],
    ownerDocument: {
      body: {appendChild: vi.fn()},
      createElement: (name: string) => {
        expect(name).toBe('a');
        const anchor = {href: '', download: '', remove: vi.fn(),
          click() {downloaded.push({href: this.href, download: this.download});}};
        anchors.push(anchor); return anchor;
      },
    },
  };
  const controller = createInvoiceRecordDownloads(container as unknown as HTMLElement, message => messages.push(message));
  const click = () => receive({target: {closest: () => button}});
  return {button, messages, blobs, downloaded, allocations, revocations, anchors, controller, click};
}

describe('explicit downloads from the accepted displayed snapshot', () => {
  it('detaches the accepted record and keeps completed bytes fixed across later source and display mutation', async () => {
    const fixture = delivery(), snapshot = source(), accepted = structuredClone(snapshot);
    fixture.controller.update(snapshot); fixture.controller.setAvailability(true, false);
    snapshot.ledger[0].total = 'CHANGED';
    snapshot.invoice_details[0].record.detail.note = 'CHANGED';
    fixture.click();
    expect(fixture.downloaded).toHaveLength(1);
    const saved = await fixture.blobs[0].text();
    expect(saved).toContain(invoiceDetailsMarkup(id, accepted, true));
    expect(saved).toContain('<dd data-ledger-field="total">4.20</dd>');
    fixture.controller.update({...snapshot, ledger: [], invoice_details: []});
    expect(await fixture.blobs[0].text()).toBe(saved);
    expect(fixture.blobs[0].type).toBe('text/html;charset=utf-8');
    expect(fixture.anchors[0].remove).toHaveBeenCalledOnce();
    vi.runOnlyPendingTimers();
    expect(fixture.revocations).toHaveBeenCalledWith(fixture.downloaded[0].href);
  });

  it('blocks forged clicks while busy or inactive, while an unchanged ready snapshot can still be explicitly saved', () => {
    const fixture = delivery(); fixture.controller.update(source());
    for (const state of [[false, false], [true, true], [false, true]]) {
      fixture.controller.setAvailability(state[0], state[1]);
      expect(fixture.button.disabled).toBe(true);
      fixture.button.disabled = false; fixture.click();
      expect(fixture.allocations).not.toHaveBeenCalled();
    }
    fixture.controller.setAvailability(true, false);
    expect(fixture.button.disabled).toBe(false);
    fixture.click(); expect(fixture.downloaded).toHaveLength(1);
  });

  it('clears old availability after an identity gap, an empty reset or an unknown selection', () => {
    const fixture = delivery(); fixture.controller.update(source()); fixture.controller.setAvailability(true, false);
    const validMarkup = fixture.controller.markup(id);
    expect(validMarkup).toContain('data-save-invoice-record="' + escape(id) + '"');
    expect(validMarkup).not.toContain(' disabled');
    for (const next of [
      {...source(), invoice_details: []},
      {...source(), ledger: [source().ledger[0], source().ledger[0]]},
      {today: '2026-10-08', ledger: [], invoice_details: []},
    ]) {
      fixture.controller.update(next);
      expect(fixture.button.disabled).toBe(true);
      expect(fixture.controller.markup(id)).toContain(' disabled');
      fixture.button.disabled = false; fixture.click();
      expect(fixture.allocations).not.toHaveBeenCalled();
    }
    fixture.controller.update(source());
    fixture.button.dataset.saveInvoiceRecord = 'UNKNOWN'; fixture.button.disabled = false; fixture.click();
    expect(fixture.allocations).not.toHaveBeenCalled();
  });

  it('reports a refused Blob URL allocation and allows a later explicit retry against the same accepted record', async () => {
    const fixture = delivery(), snapshot = source(), before = structuredClone(snapshot);
    fixture.controller.update(snapshot); fixture.controller.setAvailability(true, false);
    fixture.allocations.mockImplementationOnce(() => {throw new Error('Injected allocation refusal');});
    fixture.click();
    expect(fixture.downloaded).toEqual([]);
    expect(fixture.messages.at(-1)).toContain('Could not start');
    expect(fixture.messages.at(-1)).toContain('snapshot is unchanged');
    expect(snapshot).toEqual(before);
    fixture.click();
    expect(fixture.downloaded).toHaveLength(1);
    expect(await fixture.blobs[0].text()).toContain(invoiceDetailsMarkup(id, snapshot, true));
    expect(fixture.messages.at(-1)).toContain('download started');
  });
});
