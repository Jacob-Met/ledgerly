import {expect, it} from 'vitest';
import {decodeIntakeFile, encodeIntakeFile, MAX_INTAKE_BYTES, MAX_INTAKE_LINES} from '../src/intake-file';
import type {ReviewFields} from '../src/review';

const at = '2026-10-08T16:00:00.000Z';
const fields = (): ReviewFields => ({
  client_name: '<script>fictional()</script> & 雨', client_email: '',
  due_days: 'unfinished', amount_paid: '-3.000',
  line_items: [{desc: 'Review & résumé', qty: '', unit_price: '1,200.00', currency: 'ZZZ', unit: ''}],
});
const saved = () => JSON.parse(encodeIntakeFile({sourceText: 'Fictional source\nUnfinished work 🙂', fields: fields()}, at).text);
const read = (value: unknown) => decodeIntakeFile(JSON.stringify(value));

it('round-trips a source-only intake without creating editable or approval state', () => {
  const out = encodeIntakeFile({sourceText: 'A fictional source.\n', fields: null}, at);
  expect(decodeIntakeFile(out.text)).toEqual({
    format: 'ledgerly-intake', version: 1, saved_at: at, source_text: 'A fictional source.\n', review_fields: null,
  });
  expect(out.filename).toBe('ledgerly-intake-20261008T160000000Z.json');
  expect(out.text.endsWith('\n')).toBe(true);
});

it('preserves unfinished strings and literal text without validating or repricing them', () => {
  const input = {sourceText: 'Source & <tag>\n🙂', fields: fields()};
  const decoded = decodeIntakeFile(encodeIntakeFile(input, at).text);
  expect(decoded.source_text).toBe(input.sourceText);
  expect(decoded.review_fields).toEqual(input.fields);
  expect(Object.keys(decoded)).toEqual(['format', 'version', 'saved_at', 'source_text', 'review_fields']);
});

it('detaches encoded and decoded values from later caller changes', () => {
  const input = {sourceText: 'Original', fields: fields()};
  const out = encodeIntakeFile(input, at);
  input.fields.client_name = 'Changed';
  input.fields.line_items[0].qty = '200';
  const first = decodeIntakeFile(out.text);
  first.review_fields!.line_items[0].qty = 'another change';
  const second = decodeIntakeFile(out.text);
  expect(second.review_fields!.client_name).toBe(fields().client_name);
  expect(second.review_fields!.line_items[0].qty).toBe('');
});

it('retains exact order, zero lines and the maximum 200 editable lines', () => {
  const f = fields();
  f.line_items = [];
  expect(decodeIntakeFile(encodeIntakeFile({sourceText: '', fields: f}, at).text).review_fields!.line_items).toEqual([]);
  f.line_items = Array.from({length: MAX_INTAKE_LINES}, (_, i) => ({desc: String(i), qty: '1', unit_price: '001.00', currency: 'USD', unit: ''}));
  expect(decodeIntakeFile(encodeIntakeFile({sourceText: '', fields: f}, at).text).review_fields!.line_items).toEqual(f.line_items);
  f.line_items.push({...f.line_items[0]});
  expect(() => encodeIntakeFile({sourceText: '', fields: f}, at)).toThrow(/at most 200/);
  const value = saved(); value.review_fields = f;
  expect(() => read(value)).toThrow(/at most 200/);
});

it.each([null, false, 1, [], 'text'])('rejects a non-record root: %j', value => {
  expect(() => read(value)).toThrow();
});

it.each([
  ['format', 'invoice'], ['version', 2], ['version', '1'], ['source_text', 7],
  ['saved_at', '2026-02-30T00:00:00.000Z'], ['saved_at', '2026-10-08T16:00:00Z'],
  ['saved_at', '2026-10-08T09:00:00.000-07:00'], ['saved_at', null],
])('rejects unsupported envelope %s', (key, value) => {
  const data = saved(); data[key as string] = value;
  expect(() => read(data)).toThrow();
});

it.each(['review_id', 'confirmed', 'invoice_id', 'pending', 'confidence', '__proto__'])('rejects unexpected envelope authority %s', key => {
  const data = saved();
  Object.defineProperty(data, key, {value: key, enumerable: true});
  expect(() => read(data)).toThrow(/unexpected fields/);
});

it('requires complete editable-field keys and exact string types', () => {
  for (const key of ['client_name', 'client_email', 'due_days', 'amount_paid', 'line_items']) {
    const data = saved(); delete data.review_fields[key];
    expect(() => read(data)).toThrow(/missing or unexpected/);
  }
  for (const key of ['client_name', 'client_email', 'due_days', 'amount_paid']) {
    const data = saved(); data.review_fields[key] = 1;
    expect(() => read(data)).toThrow(/must be text/);
  }
  for (const value of [[], 'fields', 2, false]) {
    const data = saved(); data.review_fields = value;
    expect(() => read(data)).toThrow();
  }
});

it('refuses extra derived fields and malformed line objects', () => {
  const extras = saved(); extras.review_fields.total = '1.00';
  expect(() => read(extras)).toThrow(/unexpected/);
  for (const value of [null, [], 2, false, 'line', {desc: 'only a description'}]) {
    const data = saved(); data.review_fields.line_items = [value];
    expect(() => read(data)).toThrow();
  }
  for (const key of ['desc', 'qty', 'unit_price', 'currency', 'unit']) {
    const data = saved(); data.review_fields.line_items[0][key] = 7;
    expect(() => read(data)).toThrow(/must be text/);
  }
  const extraLine = saved(); extraLine.review_fields.line_items[0].total = '100';
  expect(() => read(extraLine)).toThrow(/unexpected/);
});

it('uses UTF-8 byte limits at both encoder and decoder boundaries', () => {
  const base = encodeIntakeFile({sourceText: '', fields: null}, at).text;
  const remaining = MAX_INTAKE_BYTES - new TextEncoder().encode(base).byteLength;
  const exact = encodeIntakeFile({sourceText: 'a'.repeat(remaining), fields: null}, at).text;
  expect(new TextEncoder().encode(exact).byteLength).toBe(MAX_INTAKE_BYTES);
  expect(decodeIntakeFile(exact).source_text.length).toBe(remaining);
  expect(() => encodeIntakeFile({sourceText: 'a'.repeat(remaining + 1), fields: null}, at)).toThrow(/2 MiB/);
  expect(() => decodeIntakeFile(exact + ' ')).toThrow(/2 MiB/);
  expect(() => encodeIntakeFile({sourceText: '🙂'.repeat(Math.ceil(remaining / 4) + 1), fields: null}, at)).toThrow(/2 MiB/);
});

it('accepts reordered JSON keys without changing the recorded values', () => {
  const data = saved();
  const reordered = {review_fields: data.review_fields, source_text: data.source_text,
    saved_at: data.saved_at, version: data.version, format: data.format};
  expect(read(reordered)).toEqual(data);
});

it.each(['', '{', '{"format":', 'undefined'])('refuses malformed JSON text', raw => {
  expect(() => decodeIntakeFile(raw)).toThrow(/valid JSON/);
});
