/** Read-only presentation of the concrete action returned by the Python queue. */
export interface PendingApproval {
  id: string;
  kind: string;
  invoice_id: string;
  summary: string;
  payload: unknown;
}

type Fields = Record<string, unknown>;

const escape = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g,
  character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]!));

function fields(value: unknown): Fields {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Fields : {};
}

function text(value: unknown, missing = 'Not provided'): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : missing;
}

function row(label: string, value: unknown): string {
  return '<div><dt>' + escape(label) + '</dt><dd>' + escape(text(value)) + '</dd></div>';
}

function person(value: unknown): string {
  const person = fields(value);
  const name = fields(person.name);
  const fullName = [text(name.given_name, ''), text(name.surname, '')].filter(Boolean).join(' ');
  const email = text(person.email_address, '');
  return [fullName, email].filter(Boolean).join(' · ') || 'Not provided';
}

function paymentTerms(value: unknown): string {
  const term = fields(value);
  const kind = text(term.term_type, '');
  const names: Record<string, string> = {
    DUE_ON_RECEIPT: 'Due on receipt',
    DUE_ON_DATE_SPECIFIED: 'Due on the stated date',
    NO_DUE_DATE: 'No due date',
  };
  const net = /^NET_([0-9]+)$/.exec(kind);
  const label = names[kind] ?? (net ? 'Net ' + net[1] + ' days' : kind || 'Not provided');
  return row('Payment terms', label) + (typeof term.due_date === 'string' ? row('Due date', term.due_date) : '');
}

function invoicePreview(payload: Fields): string {
  const invoice = fields(payload.invoice);
  const detail = fields(invoice.detail);
  const recipients = Array.isArray(invoice.primary_recipients) ? invoice.primary_recipients : [];
  const items = Array.isArray(invoice.items) ? invoice.items : [];
  const currency = text(detail.currency_code, '');
  const recipientText = recipients.map(recipient => person(fields(recipient).billing_info)).join('\n') || 'Not provided';
  const itemRows = items.map(item => {
    const line = fields(item);
    const price = fields(line.unit_amount);
    const unit = line.unit_of_measure === 'HOURS' ? 'hr' : line.unit_of_measure === 'QUANTITY' ? '' : text(line.unit_of_measure, '');
    return '<tr><td>' + escape(text(line.name)) + '</td><td>' + escape(text(line.quantity)) +
      (unit ? ' ' + escape(unit) : '') + '</td><td>' + escape(text(price.currency_code, currency)) +
      ' ' + escape(text(price.value)) + '</td></tr>';
  }).join('');
  const note = typeof detail.note === 'string'
    ? '<div class="approval-message-label">Invoice note</div><div class="approval-message" data-preview-invoice-note>' + escape(detail.note) + '</div>'
    : '';
  const priorPayment = payload.prepaid !== undefined
    ? row('Prior payment reported', (currency ? currency + ' ' : '') + text(payload.prepaid))
    : '';
  return '<details class="approval-preview" open><summary>Review queued invoice</summary>' +
    '<div class="approval-preview-content"><dl class="approval-fields">' +
    row('Invoice', detail.invoice_number) + row('Recipient', recipientText) +
    row('From', person(invoice.invoicer)) + row('Invoice date', detail.invoice_date) +
    paymentTerms(detail.payment_term) + priorPayment + '</dl>' +
    '<div class="approval-items"><table><caption>Queued invoice items</caption><thead><tr><th scope="col">Item</th>' +
    '<th scope="col">Quantity</th><th scope="col">Unit price</th></tr></thead><tbody>' +
    (itemRows || '<tr><td colspan="3">No item details in this queued action.</td></tr>') +
    '</tbody></table></div>' + note + '</div></details>';
}

function reminderPreview(payload: Fields): string {
  return '<section class="approval-preview approval-reminder" aria-label="Queued reminder">' +
    '<h3>Review queued reminder</h3><dl class="approval-fields">' +
    row('Subject', payload.subject) + '</dl><div class="approval-message-label">Message</div>' +
    '<div class="approval-message" data-preview-reminder-note>' + escape(text(payload.note)) + '</div></section>';
}

export function approvalCardMarkup(action: PendingApproval): string {
  const payload = fields(action.payload);
  const invoice = action.kind === 'send_invoice';
  const reminder = action.kind === 'send_reminder';
  const preview = invoice ? invoicePreview(payload) : reminder ? reminderPreview(payload) : '';
  return '<article class="approval-card" data-approval-id="' + escape(action.id) + '">' +
    '<div class="approval-head"><span class="source-chip">' +
    (invoice ? 'SEND INVOICE' : reminder ? 'SEND REMINDER' : 'PENDING ACTION') +
    '</span><span class="mono">' + escape(action.invoice_id) + '</span></div><p class="approval-summary">' +
    escape(action.summary) + '</p>' + preview + '<div class="button-row">' +
    '<button class="button button-approve" data-approve="' + escape(action.id) + '">Approve in sandbox</button>' +
    '<button class="button button-reject" data-reject="' + escape(action.id) + '">Reject</button></div></article>';
}

export function approvalListMarkup(queue: readonly PendingApproval[]): string {
  return queue.length ? queue.map(approvalCardMarkup).join('') :
    '<p class="empty">No approvals waiting. Sends and reminders stay queued until you choose.</p>';
}
