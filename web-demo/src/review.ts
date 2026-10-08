export type ReviewLine = {desc: string; qty: string; unit_price: string; currency: string; unit: string};
export type ReviewFields = {client_name: string; client_email: string; due_days: string; amount_paid: string; line_items: ReviewLine[]};

const esc = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]!));

export function fieldsFromExtraction(ex: any): ReviewFields {
  return {
    client_name: String(ex.client_name ?? ''), client_email: String(ex.client_email ?? ''),
    due_days: String(ex.due_days ?? ''), amount_paid: String(ex.amount_paid ?? '0'),
    line_items: (ex.line_items ?? []).map((row: any) => ({
      desc: String(row.desc ?? ''), qty: String(row.qty ?? ''), unit_price: String(row.unit_price ?? ''),
      currency: String(row.currency ?? ex.currency ?? ''), unit: String(row.unit ?? ''),
    })),
  };
}

export function readReviewFields(form: HTMLFormElement): ReviewFields {
  const value = (name: string) => (form.elements.namedItem(name) as HTMLInputElement).value;
  return {
    client_name: value('client_name'), client_email: value('client_email'),
    due_days: value('due_days'), amount_paid: value('amount_paid'),
    line_items: Array.from(form.querySelectorAll<HTMLElement>('[data-review-line]')).map(row => {
      const field = (name: string) => row.querySelector<HTMLInputElement>(`[data-field="${name}"]`)!.value;
      return {desc: field('desc'), qty: field('qty'), unit_price: field('unit_price'), currency: field('currency'), unit: field('unit')};
    }),
  };
}

export function reviewLinesMarkup(lines: ReviewLine[], currencies: string[]): string {
  if (!lines.length) return '<p class="empty">No line items. Add the work and price you have confirmed.</p>';
  return lines.map((row, index) => {
    const prefix = `review-line-${index}`;
    const options = Array.from(new Set(['', ...currencies, row.currency])).map(currency => `<option value="${esc(currency)}"${currency === row.currency ? ' selected' : ''}>${esc(currency || 'Choose currency')}</option>`).join('');
    return `<fieldset class="review-line" data-review-line><legend>Line ${index + 1}</legend>
      <label class="review-description" for="${prefix}-desc">Work description<input id="${prefix}-desc" data-field="desc" value="${esc(row.desc)}" required></label>
      <label for="${prefix}-qty">Quantity<input id="${prefix}-qty" data-field="qty" inputmode="decimal" value="${esc(row.qty)}" placeholder="Confirm quantity" required></label>
      <label for="${prefix}-price">Unit price<input id="${prefix}-price" data-field="unit_price" inputmode="decimal" value="${esc(row.unit_price)}" required></label>
      <label for="${prefix}-currency">Currency<select id="${prefix}-currency" data-field="currency">${options}</select></label>
      <label for="${prefix}-unit">Unit (optional)<input id="${prefix}-unit" data-field="unit" value="${esc(row.unit)}" placeholder="hours, items…"></label>
      <button class="button button-link review-remove" type="button" data-remove-line="${index}" aria-label="Remove line ${index + 1}">Remove line</button>
    </fieldset>`;
  }).join('');
}

export function reviewMarkup(ex: any): string {
  const fields = fieldsFromExtraction(ex);
  return `<details id="review-editor" class="review-editor"><summary>Review or correct invoice fields</summary>
    <p>Supply the details you have confirmed. Your corrections are marked as human input; they do not change the original extraction above.</p>
    <form id="review-form" novalidate>
      <div class="review-fields">
        <label for="review-client-name">Client name<input id="review-client-name" name="client_name" value="${esc(fields.client_name)}" autocomplete="off"></label>
        <label for="review-client-email">Recipient email<input id="review-client-email" name="client_email" type="email" value="${esc(fields.client_email)}" autocomplete="off" required></label>
        <label for="review-due-days"><span id="review-due-label">Payment due in days</span><input id="review-due-days" name="due_days" inputmode="numeric" value="${esc(fields.due_days)}" aria-labelledby="review-due-label" aria-describedby="review-due-help" required><small id="review-due-help">0 means due on receipt; maximum 365.</small></label>
        <label for="review-amount-paid"><span id="review-paid-label">Prior payment already received</span><input id="review-amount-paid" name="amount_paid" inputmode="decimal" value="${esc(fields.amount_paid)}" aria-labelledby="review-paid-label" aria-describedby="review-paid-help" required><small id="review-paid-help">0 if none. A payment across currencies needs separate allocation.</small></label>
      </div>
      <div id="review-lines">${reviewLinesMarkup(fields.line_items, ex.review_currencies ?? [])}</div>
      <button id="review-add-line" class="button button-secondary" type="button">Add line item</button>
      <label class="review-confirm" for="review-confirm"><input id="review-confirm" type="checkbox">I checked the recipient, terms, amounts and every original warning against the job details.</label>
      <button id="review-check" class="button button-primary" type="submit" disabled>Check corrected fields with Python</button>
      <section id="review-result" class="review-result" role="status" aria-live="polite"><p>Checking fields creates no invoice and approves no send.</p></section>
    </form>
  </details>`;
}

export function reviewResultMarkup(result: any): string {
  const issues = (result.issues ?? []).map((issue: any) => `<li class="issue ${esc(issue.severity)}"><b>${esc(issue.field)}</b><span>${esc(issue.message)}</span></li>`).join('');
  const totals = (result.totals_by_currency ?? []).map((total: any) => `<li>${esc(total.currency)} ${esc(total.total)}</li>`).join('');
  return `<strong>${result.valid ? 'Checked human input — ready to draft' : 'These fields still need attention'}</strong>
    <p>${esc(result.client_name || 'Client')} · ${esc(result.client_email || 'Recipient missing')}<br>${result.due_days === 0 ? 'Due on receipt' : `Due in ${esc(result.due_days)} days`} · Prior payment: ${esc(result.amount_paid)}</p>
    ${totals ? `<ul class="review-totals" aria-label="Checked totals by currency">${totals}</ul>` : ''}
    ${issues ? `<ul class="issue-list">${issues}</ul>` : '<p>The Python field checks found no issue.</p>'}
    <p>${result.valid ? 'Create the reviewed sandbox draft below. Its send still requires a separate approval.' : 'Correct the fields, confirm your review and check again.'}</p>`;
}
