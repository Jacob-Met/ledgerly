import type {ReviewFields} from './review';

export const MAX_INTAKE_BYTES = 2 * 1024 * 1024;
export const MAX_INTAKE_LINES = 200;
export type IntakeSnapshot = {sourceText: string; fields: ReviewFields | null};
export type IntakeFile = {
  format: 'ledgerly-intake';
  version: 1;
  saved_at: string;
  source_text: string;
  review_fields: ReviewFields | null;
};

const encoder = new TextEncoder();
const fieldKeys = ['client_name', 'client_email', 'due_days', 'amount_paid', 'line_items'];
const lineKeys = ['desc', 'qty', 'unit_price', 'currency', 'unit'];

function record(value: unknown, keys: string[], label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length !== keys.length
    || !keys.every(key => Object.prototype.hasOwnProperty.call(value, key))) {
    throw new Error(label + ' has missing or unexpected fields.');
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string') throw new Error(label + ' must be text.');
  return value;
}

function copyFields(value: unknown): ReviewFields | null {
  if (value === null) return null;
  const fields = record(value, fieldKeys, 'Editable invoice fields');
  if (!Array.isArray(fields.line_items) || fields.line_items.length > MAX_INTAKE_LINES) {
    throw new Error('An intake file can contain at most ' + MAX_INTAKE_LINES + ' editable line items.');
  }
  return {
    client_name: text(fields.client_name, 'Client name'),
    client_email: text(fields.client_email, 'Recipient email'),
    due_days: text(fields.due_days, 'Payment terms'),
    amount_paid: text(fields.amount_paid, 'Prior payment'),
    line_items: fields.line_items.map((value, index) => {
      const row = record(value, lineKeys, 'Line item ' + (index + 1));
      return {
        desc: text(row.desc, 'Work description'), qty: text(row.qty, 'Quantity'),
        unit_price: text(row.unit_price, 'Unit price'), currency: text(row.currency, 'Currency'),
        unit: text(row.unit, 'Unit'),
      };
    }),
  };
}

function admit(value: unknown): IntakeFile {
  const data = record(value, ['format', 'version', 'saved_at', 'source_text', 'review_fields'], 'Intake file');
  if (data.format !== 'ledgerly-intake' || data.version !== 1) {
    throw new Error('Choose a Ledgerly intake file in the supported version 1 format.');
  }
  const savedAt = text(data.saved_at, 'Saved time');
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(savedAt)
    || !Number.isFinite(new Date(savedAt).getTime()) || new Date(savedAt).toISOString() !== savedAt) {
    throw new Error('The intake file needs an exact UTC saved time.');
  }
  return {
    format: 'ledgerly-intake', version: 1, saved_at: savedAt,
    source_text: text(data.source_text, 'Source email'),
    review_fields: copyFields(data.review_fields),
  };
}

function bounded(value: string): string {
  if (encoder.encode(value).byteLength > MAX_INTAKE_BYTES) {
    throw new Error('Choose an intake file no larger than 2 MiB.');
  }
  return value;
}

/** Preserve input strings, including unfinished values. Python owns invoice validation. */
export function encodeIntakeFile(snapshot: IntakeSnapshot, savedAt = new Date().toISOString()): {text: string; filename: string} {
  const file = admit({
    format: 'ledgerly-intake', version: 1, saved_at: savedAt,
    source_text: snapshot.sourceText, review_fields: snapshot.fields,
  });
  return {
    text: bounded(JSON.stringify(file, null, 2) + '\n'),
    filename: 'ledgerly-intake-' + savedAt.replace(/[-:.]/g, '') + '.json',
  };
}

/** Admit and detach the complete file. No approval, token or derived result is imported. */
export function decodeIntakeFile(raw: string): IntakeFile {
  if (typeof raw !== 'string') throw new Error('The intake file must be UTF-8 JSON text.');
  let value: unknown;
  try { value = JSON.parse(bounded(raw)); }
  catch (error) {
    if (error instanceof SyntaxError) throw new Error('The intake file is not valid JSON.');
    throw error;
  }
  return admit(value);
}
