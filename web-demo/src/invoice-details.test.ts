import {expect, it} from 'vitest';
import {invoiceDetailsMarkup} from './invoice-details';

function snapshot(record: Record<string, unknown> = {}) {
  return {today: '2026-10-08', invoice_details: [{invoice_id: 'INV-1', record: {id: 'INV-1', ...record}}]};
}

it('shows retained item, recipient, terms and provider fields with explicit provenance', () => {
  const markup = invoiceDetailsMarkup('INV-1', snapshot({status: 'SENT', detail: {
    invoice_number: 'LDG-12', invoice_date: '2026-10-08', note: 'Original job',
    payment_term: {term_type: 'NET_15', due_date: '2026-10-23'},
  }, primary_recipients: [{billing_info: {name: {given_name: 'Maya', surname: 'Chen'},
    email_address: 'maya@example.test', address: {address_line_1: '1 Fictional Road', country_code: 'US'}}}],
  items: [{name: 'Copywriting', quantity: '12', unit_of_measure: 'HOURS', unit_amount: {currency_code: 'USD', value: '85.00'}}],
  amount: {currency_code: 'USD', value: '1020.00'}, payments: {paid_amount: {currency_code: 'USD', value: '0.00'}, transactions: []},
  due_amount: {currency_code: 'USD', value: '1020.00'}}));
  for (const value of ['Invoice details', 'sandbox record', 'Sandbox clock at snapshot: 2026-10-08',
    'Sandbox provider status', 'Maya Chen', 'maya@example.test', '1 Fictional Road', 'Net 15 days',
    '2026-10-23', 'Copywriting', 'USD 85.00', 'No recorded sandbox payments.', 'agent’s view']) expect(markup).toContain(value);
  expect(markup).not.toContain('<button');
});

it('escapes all imported text and identifiers without generating active elements', () => {
  const literal = '\"><img src=x onerror=alert(1)> & 日本語 😀\n\u2028\u2029';
  const input = {today: literal, invoice_details: [{invoice_id: literal, record: {id: literal, status: literal,
    detail: {invoice_number: literal, note: literal, payment_term: {term_type: literal}},
    items: [{name: literal, description: literal, quantity: literal, unit_of_measure: literal,
      unit_amount: {currency_code: literal, value: literal}}],
    primary_recipients: [{billing_info: {email_address: literal}}],
    payments: {transactions: [{payment_date: literal, type: literal, method: literal, payment_id: literal, amount: {value: literal}}]},
  }}]};
  const html = invoiceDetailsMarkup(literal, input);
  expect(html).toContain('&quot;&gt;&lt;img src=x onerror=alert(1)&gt; &amp; 日本語 😀\n\u2028\u2029');
  expect(html).not.toMatch(/<(img|script|iframe|a|form)\b/);
});

it('retains original decimal strings and each amount currency without arithmetic', () => {
  const html = invoiceDetailsMarkup('INV-1', snapshot({amount: {currency_code: 'USD', value: '9007199254740993.000'},
    due_amount: {currency_code: 'JPY', value: '123456789'},
    items: [{quantity: '2.5000', unit_amount: {currency_code: 'EUR', value: '10.2300'}}],
    payments: {paid_amount: {currency_code: 'GBP', value: '0.000'}, transactions: [
      {payment_date: '2026-10-08', type: 'EXTERNAL', method: 'OTHER', payment_id: 'PAY-42', amount: {currency_code: 'CAD', value: '100.25'}},
    ]}}));
  for (const text of ['USD 9007199254740993.000', 'JPY 123456789', '2.5000', 'EUR 10.2300', 'GBP 0.000', 'CAD 100.25', 'PAY-42']) expect(html).toContain(text);
});

it('requires one exact matching identity and never falls back to another record', () => {
  for (const rows of [[], [{invoice_id: 'INV-2', record: {id: 'INV-2', detail: {note: 'PRIVATE OTHER'}}}],
    [{invoice_id: 'INV-1', record: {id: 'INV-2', detail: {note: 'PRIVATE OTHER'}}}],
    [...snapshot({detail: {note: 'PRIVATE OTHER'}}).invoice_details, ...snapshot().invoice_details]]) {
    const html = invoiceDetailsMarkup('INV-1', {invoice_details: rows});
    expect(html).toContain('No matching retained sandbox invoice record');
    expect(html).not.toContain('PRIVATE OTHER');
  }
});

it('labels absent, empty and malformed data without inventing zero amounts or actions', () => {
  const html = invoiceDetailsMarkup('INV-1', snapshot({detail: {note: '', payment_term: null},
    items: [null], payments: {transactions: {}}, primary_recipients: [null]}));
  expect(html).toContain('(empty)');
  expect(html).toContain('Not recorded');
  expect(html).toContain('Currency not recorded amount not recorded');
  expect(html).toContain('Payment details not recorded.');
  expect(html).not.toContain('USD 0');
  expect(html).not.toContain('data-pay');
});

it('does not change the received snapshot or add pending approval semantics', () => {
  const input = snapshot({detail: {note: 'Retained invoice'}, items: [{name: 'Work', quantity: '1.00'}]});
  const before = JSON.stringify(input);
  const html = invoiceDetailsMarkup('INV-1', input, true);
  expect(JSON.stringify(input)).toBe(before);
  expect(html).toContain('data-invoice-detail-id="INV-1" open');
  expect(html).not.toMatch(/data-(approve|reject|pay)=/);
});

it('provides native disclosure semantics and labeled scrollable tables', () => {
  const html = invoiceDetailsMarkup('INV-1', snapshot({items: [], payments: {transactions: [{payment_id: 'PAY-1'}]}}));
  expect(html).toContain('<summary>Invoice details');
  expect(html).toContain('<caption>Invoice items</caption>');
  expect(html).toContain('<caption>Recorded sandbox payments</caption>');
  expect(html.match(/scope="col"/g)).toHaveLength(8);
  expect(html.match(/tabindex="0" role="region"/g)).toHaveLength(2);
});

it('preserves unknown provider status and receipt terms instead of inventing interpretations', () => {
  const html = invoiceDetailsMarkup('INV-1', snapshot({status: 'PROVIDER_FUTURE_STATUS', detail: {payment_term: {term_type: '__proto__'}}}));
  expect(html).toContain('PROVIDER_FUTURE_STATUS');
  expect(html).toContain('__proto__');
  expect(invoiceDetailsMarkup('INV-1', snapshot({detail: {payment_term: {term_type: 'DUE_ON_RECEIPT'}}}))).toContain('Due on receipt');
});
