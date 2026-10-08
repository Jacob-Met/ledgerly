/** Explicit standalone copies of the accepted, displayed sandbox invoice. */
import {invoiceDetailsMarkup, type InvoiceDetailSnapshot} from './invoice-details';
import invoiceDetailStyles from './invoice-details.css?raw';

type Fields = Record<string, unknown>;
export interface InvoiceRecordSnapshot extends InvoiceDetailSnapshot { ledger?: unknown }
type Announce = (message: string, kind?: string) => void;
const MAX_RECORD_BYTES = 4 * 1024 * 1024;
const escape = (value: string): string => value.replace(/[&<>"']/g,
  character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]!));
const fields = (value: unknown): Fields => value !== null && typeof value === 'object' && !Array.isArray(value)
  ? value as Fields : {};
const text = (value: unknown): string => typeof value === 'string' ? value || '(empty)'
  : typeof value === 'number' && Number.isFinite(value) ? String(value) : 'Not recorded';
const summaryFields = [
  ['invoice_id', 'Invoice reference'], ['invoice_number', 'Invoice number'],
  ['client_name', 'Client'], ['client_email', 'Recipient email'], ['currency', 'Currency'],
  ['total', 'Invoice total'], ['paid_amount', 'Paid amount'], ['balance', 'Balance'],
  ['status', 'Agent ledger status'], ['sent_on', 'Sent on'], ['due_on', 'Due on'],
  ['reminders_sent', 'Reminders sent'],
] as const;

/** Select one identity; neither the latest analysis nor another invoice is a fallback. */
function selectedSnapshot(snapshot: InvoiceRecordSnapshot, invoiceId: string): InvoiceRecordSnapshot {
  if (typeof invoiceId !== 'string' || !invoiceId || typeof snapshot?.today !== 'string' || !snapshot.today)
    throw new Error('A dated sandbox snapshot and invoice reference are required.');
  const ledger = Array.isArray(snapshot.ledger) ? snapshot.ledger : [];
  const details = Array.isArray(snapshot.invoice_details) ? snapshot.invoice_details : [];
  const entries = ledger.filter(value => fields(value).invoice_id === invoiceId);
  const records = details.filter(value => fields(value).invoice_id === invoiceId);
  if (entries.length !== 1 || records.length !== 1 || fields(fields(records[0]).record).id !== invoiceId)
    throw new Error('One matching retained sandbox invoice record is required.');
  // Copy only this displayed invoice and its ledger row. Other invoices, queue
  // proposals, analysis and the pasted source do not enter the document.
  return structuredClone({today: snapshot.today, ledger: [entries[0]], invoice_details: [records[0]]});
}

const pageStyles = `
:root { color-scheme: light; --line: #cfd8d1; }
* { box-sizing: border-box; }
body { margin: 0; padding: 28px; color: #172b22; background: #fff;
  font-family: system-ui, sans-serif; line-height: 1.5; }
main { max-width: 900px; margin: 0 auto; min-width: 0; }
h1 { font-size: 1.8rem; margin: 8px 0 16px; overflow-wrap: anywhere; }
h2 { font-size: 1.1rem; margin-top: 28px; }
.record-label { letter-spacing: .12em; font-size: .8rem; font-weight: 800; }
.record-boundary { border-left: 4px solid #276749; padding-left: 14px; overflow-wrap: anywhere; }
.record-metadata { font-size: .85rem; overflow-wrap: anywhere; }
.record-toolbar { margin: 24px 0; }
.record-toolbar button { font: inherit; padding: 10px 16px; border: 1px solid #276749;
  border-radius: 6px; background: #edf4ee; color: #172b22; cursor: pointer; }
.record-toolbar button:focus-visible { outline: 3px solid #276749; outline-offset: 3px; }
.record-toolbar p, footer { font-size: .82rem; color: #46594f; }
.record-summary { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px 20px; }
.record-summary div { min-width: 0; }
.record-summary dt { font-size: .75rem; font-weight: 700; color: #46594f; }
.record-summary dd { margin: 3px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
footer { border-top: 1px solid var(--line); padding-top: 16px; margin-top: 28px; }
@media (max-width: 520px) {
  body { padding: 18px; }
  .record-summary { grid-template-columns: minmax(0,1fr); }
}
@page { size: A4; margin: 16mm; }
@media print {
  body { padding: 0; color: #000; font-size: 10pt; }
  main { max-width: none; }
  .record-toolbar { display: none; }
  .invoice-detail-table { overflow: visible; }
  .invoice-detail-table table { min-width: 0; table-layout: fixed; }
  .invoice-detail-table td:first-child { max-width: none; }
  .invoice-detail-table th, .invoice-detail-table td { padding: 6px; }
  tr, .record-summary > div, .invoice-detail-fields > div { break-inside: avoid; }
  h1, h2, h4, summary { break-after: avoid; }
}
`;
const printScript = `(() => {
  const openRecord = () => { document.querySelector('.invoice-details').open = true; };
  window.addEventListener('beforeprint', openRecord);
  document.querySelector('#print-invoice-record').addEventListener('click', () => {
    openRecord();
    window.print();
  });
})();`;

/** Original strings and currencies stay in separate fields; no money arithmetic. */
export function buildInvoiceRecord(
  snapshot: InvoiceRecordSnapshot, invoiceId: string, createdAt = new Date(),
): {filename: string; text: string} {
  const selected = selectedSnapshot(snapshot, invoiceId);
  const entry = fields((selected.ledger as unknown[])[0]);
  const created = createdAt.toISOString();
  const rows = summaryFields.map(([key, label]) => '<div><dt>' + label +
    '</dt><dd data-ledger-field="' + key + '">' + escape(text(entry[key])) + '</dd></div>').join('');
  const document = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">' +
    '<title>Sandbox invoice record — ' + escape(text(entry.invoice_number)) + '</title>' +
    '<style>' + invoiceDetailStyles + pageStyles + '</style></head>' +
    '<body data-invoice-record-format="ledgerly.sandbox-invoice-record.v1"><main>' +
    '<header><p class="record-label">SANDBOX INVOICE RECORD</p><h1>Invoice ' + escape(text(entry.invoice_number)) + '</h1>' +
    '<p id="invoice-record-boundary" class="record-boundary">A saved copy from Ledgerly’s in-memory simulation. ' +
    'This is not a payable invoice, a payment receipt or a current provider statement. No real money moved.</p>' +
    '<p class="record-metadata">Sandbox clock at source snapshot: <span id="invoice-record-snapshot">' +
    escape(selected.today as string) + '</span><br>File created at (UTC): <span id="invoice-record-created">' +
    escape(created) + '</span></p></header>' +
    '<div class="record-toolbar"><button id="print-invoice-record" type="button">Print this record</button>' +
    '<p>Open or print this saved copy without loading the Python engine. It does not update when the sandbox changes.</p></div>' +
    '<section aria-labelledby="record-summary-heading"><h2 id="record-summary-heading">Original agent ledger summary</h2>' +
    '<dl class="record-summary">' + rows + '</dl></section>' +
    invoiceDetailsMarkup(invoiceId, selected, true) +
    '<footer>Only the selected displayed invoice is included. Amounts, dates, items and recorded payments are copied ' +
    'without recalculation or a provider refresh. This HTML file cannot restore a sandbox or authorize any action.</footer>' +
    '</main><script>' + printScript + '</script></body></html>\n';
  if (new TextEncoder().encode(document).byteLength > MAX_RECORD_BYTES)
    throw new Error('This invoice record exceeds the 4 MiB download limit.');
  const safeId = invoiceId.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 96) || 'record';
  return {filename: 'ledgerly-sandbox-invoice-' + safeId + '.html', text: document};
}

/** Bind downloads to the accepted displayed snapshot and current availability. */
export function createInvoiceRecordDownloads(container: HTMLElement, announce: Announce = () => {}) {
  let snapshots = new Map<string, InvoiceRecordSnapshot>();
  let available = false, busy = false;
  container.addEventListener('click', event => {
    const button = (event.target as HTMLElement).closest?.<HTMLButtonElement>('button[data-save-invoice-record]');
    if (!button || !container.contains(button) || !available || busy || button.disabled) return;
    const id = button.dataset.saveInvoiceRecord;
    const snapshot = id === undefined ? undefined : snapshots.get(id);
    if (!snapshot || id === undefined) return;
    let url: string | undefined;
    let anchor: HTMLAnchorElement | undefined;
    try {
      // Capture this immutable selection before allocating the download; a
      // subsequent render cannot substitute another snapshot into these bytes.
      const record = buildInvoiceRecord(snapshot, id);
      const blob = new Blob([record.text], {type: 'text/html;charset=utf-8'});
      url = URL.createObjectURL(blob);
      anchor = container.ownerDocument.createElement('a');
      anchor.href = url;
      anchor.download = record.filename;
      container.ownerDocument.body.appendChild(anchor);
      anchor.click();
      announce('Sandbox invoice record download started. This saved copy will not update with the sandbox.', 'ready');
    } catch {
      announce('Could not start this invoice record download. The displayed snapshot is unchanged; try again.', 'error');
    } finally {
      anchor?.remove();
      if (url !== undefined) {
        const completedUrl = url;
        setTimeout(() => URL.revokeObjectURL(completedUrl), 1000);
      }
    }
  });
  const sync = () => {
    for (const button of Array.from(container.querySelectorAll<HTMLButtonElement>('button[data-save-invoice-record]')))
      button.disabled = !available || busy || !snapshots.has(button.dataset.saveInvoiceRecord || '');
  };
  return {
    update(snapshot: InvoiceRecordSnapshot): void {
      const next = new Map<string, InvoiceRecordSnapshot>();
      for (const row of Array.isArray(snapshot?.ledger) ? snapshot.ledger : []) {
        const id = fields(row).invoice_id;
        if (typeof id !== 'string') continue;
        try { next.set(id, selectedSnapshot(snapshot, id)); }
        catch { /* Missing or ambiguous source stays unavailable, without a stale fallback. */ }
      }
      snapshots = next;
      sync();
    },
    markup(invoiceId: string): string {
      const disabled = !available || busy || !snapshots.has(invoiceId);
      return '<div class="invoice-record-action"><button type="button" class="button button-secondary" ' +
        'data-save-invoice-record="' + escape(invoiceId) + '"' + (disabled ? ' disabled' : '') +
        '>Save sandbox invoice record</button><p class="fine-print">Keep this invoice’s displayed details in a standalone HTML copy.</p></div>';
    },
    setAvailability(ready: boolean, inProgress: boolean): void {
      available = ready; busy = inProgress; sync();
    },
  };
}
