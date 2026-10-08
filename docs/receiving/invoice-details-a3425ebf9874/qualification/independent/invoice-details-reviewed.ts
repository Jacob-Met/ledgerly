/** Read-only display of detached records returned by the Python sandbox. */
type Fields = Record<string, unknown>;

export interface InvoiceDetailSnapshot {
  today?: unknown;
  invoice_details?: unknown;
}

const escape = (value: string): string => value.replace(/[&<>"']/g,
  character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]!));

function fields(value: unknown): Fields {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Fields : {};
}

function text(value: unknown, missing = 'Not recorded'): string {
  if (typeof value === 'string') return value || '(empty)';
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : missing;
}

function row(label: string, value: unknown): string {
  return '<div><dt>' + escape(label) + '</dt><dd>' + escape(text(value)) + '</dd></div>';
}

function money(value: unknown): string {
  const amount = fields(value);
  return text(amount.currency_code, 'Currency not recorded') + ' ' + text(amount.value, 'amount not recorded');
}

function person(value: unknown): string {
  const person = fields(value), name = fields(person.name), address = fields(person.address);
  const parts = [
    [name.given_name, name.surname].filter(value => typeof value === 'string' && value.length).join(' '),
    person.email_address,
    ...['address_line_1', 'address_line_2', 'admin_area_2', 'admin_area_1', 'postal_code', 'country_code'].map(key => address[key]),
  ].filter(value => typeof value === 'string' && value.length);
  return parts.length ? parts.join('\n') : 'Not recorded';
}

function terms(value: unknown): string {
  const kind = text(value, ''), net = /^NET_([0-9]+)$/.exec(kind);
  if (kind === 'DUE_ON_RECEIPT') return 'Due on receipt';
  if (kind === 'DUE_ON_DATE_SPECIFIED') return 'Due on the stated date';
  if (kind === 'NO_DUE_DATE') return 'No due date';
  return net ? 'Net ' + net[1] + ' days' : kind || 'Not recorded';
}

function itemsMarkup(value: unknown): string {
  const items = Array.isArray(value) ? value : [];
  const rows = items.map(value => {
    const item = fields(value);
    const description = typeof item.description === 'string'
      ? '<span class="invoice-detail-description">' + escape(item.description) + '</span>' : '';
    return '<tr><td>' + escape(text(item.name)) + description + '</td><td>' + escape(text(item.quantity)) +
      '</td><td>' + escape(text(item.unit_of_measure)) + '</td><td>' + escape(money(item.unit_amount)) + '</td></tr>';
  }).join('');
  return '<div class="invoice-detail-table" tabindex="0" role="region" aria-label="Invoice items; scroll horizontally if needed">' +
    '<table><caption>Invoice items</caption><thead><tr><th scope="col">Item</th><th scope="col">Quantity</th>' +
    '<th scope="col">Unit</th><th scope="col">Unit price</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="4">No item details recorded.</td></tr>') + '</tbody></table></div>';
}

function paymentsMarkup(value: unknown): string {
  const payments = fields(value), transactions = Array.isArray(payments.transactions) ? payments.transactions : [];
  if (!transactions.length) return '<p class="invoice-detail-empty">' +
    (Array.isArray(payments.transactions) ? 'No recorded sandbox payments.' : 'Payment details not recorded.') + '</p>';
  const rows = transactions.map(value => {
    const payment = fields(value);
    return '<tr><td>' + escape(text(payment.payment_date)) + '</td><td>' + escape(money(payment.amount)) +
      '</td><td>' + escape(text(payment.type)) + ' / ' + escape(text(payment.method)) + '</td><td>' +
      escape(text(payment.payment_id)) + '</td></tr>';
  }).join('');
  return '<div class="invoice-detail-table" tabindex="0" role="region" aria-label="Recorded sandbox payments; scroll horizontally if needed">' +
    '<table><caption>Recorded sandbox payments</caption><thead><tr><th scope="col">Date</th><th scope="col">Amount</th>' +
    '<th scope="col">Type / method</th><th scope="col">Reference</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
}

function availabilityText(available: boolean, busy: boolean): string {
  if (!available) return 'Last displayed sandbox snapshot. The Python session is inactive; restart clears these records.';
  if (busy) return 'Last displayed sandbox snapshot. An action is in progress; details update when it finishes.';
  return 'Read-only copy from this tab’s in-memory sandbox. Opening details makes no provider request.';
}

/** Exact identity matching; no analysis, pending-action or different-invoice fallback. */
export function invoiceDetailsMarkup(invoiceId: string, snapshot: InvoiceDetailSnapshot, open = false): string {
  const rows = Array.isArray(snapshot.invoice_details) ? snapshot.invoice_details : [];
  const matches = rows.filter(value => fields(value).invoice_id === invoiceId);
  const record = matches.length === 1 ? fields(fields(matches[0]).record) : {};
  const available = record.id === invoiceId;
  const detail = fields(record.detail), payment = fields(detail.payment_term), payments = fields(record.payments);
  const recipients = Array.isArray(record.primary_recipients) ? record.primary_recipients : [];
  const recipient = recipients.map(value => person(fields(value).billing_info)).join('\n\n') || 'Not recorded';
  const content = available ?
    '<dl class="invoice-detail-fields">' + row('Invoice reference', record.id) + row('Invoice number', detail.invoice_number) +
    row('Sandbox provider status', record.status) + row('Recipient', recipient) + row('From', person(record.invoicer)) +
    row('Invoice date', detail.invoice_date) + row('Payment terms', terms(payment.term_type)) + row('Due date', payment.due_date) +
    '</dl>' + itemsMarkup(record.items) + '<dl class="invoice-detail-fields invoice-detail-amounts">' +
    row('Provider invoice total', money(record.amount)) + row('Provider paid amount', money(payments.paid_amount)) +
    row('Provider amount due', money(record.due_amount)) + '</dl>' +
    '<p class="invoice-detail-explanation">Amounts and payment entries are copied from the sandbox provider record. The ledger summary above is the agent’s view; these values are not recalculated or combined across currencies.</p>' +
    '<h4>Invoice note</h4><div class="invoice-detail-note">' + escape(text(detail.note)) + '</div>' + paymentsMarkup(record.payments) :
    '<p class="invoice-detail-empty">No matching retained sandbox invoice record is available. The ledger summary above may still be inspected.</p>';
  return '<details class="invoice-details" data-invoice-detail-id="' + escape(invoiceId) + '"' + (open ? ' open' : '') +
    '><summary>Invoice details <span>· sandbox record</span></summary><div class="invoice-detail-content">' +
    '<p class="invoice-detail-provenance">Sandbox clock at snapshot: ' + escape(text(snapshot.today)) + '</p>' +
    '<p class="invoice-detail-state" data-invoice-details-state></p>' + content + '</div></details>';
}

/** Keep open details and keyboard focus across normal whole-ledger rendering. */
export function createInvoiceDetailsView(container: HTMLElement) {
  const openIds = new Set<string>();
  let focusedId: string | undefined;
  container.addEventListener('toggle', event => {
    const detail = event.target as HTMLDetailsElement;
    if (!detail.matches?.('.invoice-details')) return;
    const id = detail.dataset.invoiceDetailId;
    if (id !== undefined) { if (detail.open) openIds.add(id); else openIds.delete(id); }
  }, true);
  return {
    beforeRender(ids: readonly string[]): void {
      for (const id of openIds) if (!ids.includes(id)) openIds.delete(id);
      const focused = container.ownerDocument?.activeElement;
      const detail = focused?.closest<HTMLDetailsElement>('.invoice-details');
      focusedId = detail && container.contains(detail) ? detail.dataset.invoiceDetailId : undefined;
    },
    markup(invoiceId: string, snapshot: InvoiceDetailSnapshot): string {
      return invoiceDetailsMarkup(invoiceId, snapshot, openIds.has(invoiceId));
    },
    afterRender(): void {
      if (focusedId === undefined) return;
      const detail = Array.from(container.querySelectorAll<HTMLDetailsElement>('.invoice-details'))
        .find(detail => detail.dataset.invoiceDetailId === focusedId);
      detail?.querySelector<HTMLElement>('summary')?.focus({preventScroll: true});
      focusedId = undefined;
    },
    setAvailability(available: boolean, busy: boolean): void {
      for (const message of Array.from(container.querySelectorAll<HTMLElement>('[data-invoice-details-state]'))) {
        message.textContent = availabilityText(available, busy);
        message.dataset.inactive = String(!available);
      }
    },
  };
}
