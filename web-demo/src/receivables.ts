/** Read-only client balances from one accepted native sandbox snapshot. */
export type DueState = 'overdue' | 'today' | 'later' | 'undated';
export type ReceivableInvoice = {
  invoice_id: string; invoice_number: string; client_email: string; client_name: string | null;
  currency: string; balance: string; status: string; due_on: string | null;
  dueState: DueState; daysOverdue: number;
};
export type ClientReceivables = {email: string; names: string[]; invoices: ReceivableInvoice[]};
export type Receivables = {
  today: string; ledgerCount: number; invoiceCount: number;
  clients: ClientReceivables[]; excluded: {status: string; count: number}[];
};
export type CurrencyTotal = {currency: string; balance: string; invoiceCount: number};
export type ReceivablesSelection = {clients: ClientReceivables[]; totals: CurrencyTotal[]; invoiceCount: number};
type DecimalValue = {units: bigint; scale: number};
const OPEN = new Set(['SENT', 'UNPAID', 'PARTIALLY_PAID', 'PAYMENT_PENDING']);
const DUE: Record<DueState, string> = {
  overdue: 'Overdue', today: 'Due today', later: 'Due later', undated: 'Undated',
};
const compare = (left: string, right: string) => left < right ? -1 : left > right ? 1 : 0;

function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`Missing or invalid ${field}.`);
  return value;
}
function day(value: unknown, field: string): number {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) {
    throw new Error(`Invalid ${field}; an ISO calendar date is required.`);
  }
  const parsed = new Date(value + 'T00:00:00.000Z');
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) {
    throw new Error(`Invalid ${field}; an ISO calendar date is required.`);
  }
  return parsed.getTime() / 86400000;
}
function decimal(value: unknown): DecimalValue {
  if (typeof value !== 'string' || value.length > 1100) throw new Error('Invalid native balance string.');
  const match = /^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d{1,4}))?$/.exec(value);
  if (!match) throw new Error('Invalid native balance string.');
  const fraction = match[3] || '';
  const exponent = Number(match[4] || 0);
  if (Math.abs(exponent) > 1000 || match[2].length + fraction.length > 1000) {
    throw new Error('Native balance exceeds the supported display range.');
  }
  let units = BigInt(match[2] + fraction);
  if (match[1] === '-') units = -units;
  if (units < 0n) throw new Error('A native balance cannot be negative.');
  let scale = fraction.length - exponent;
  if (scale < 0) { units *= 10n ** BigInt(-scale); scale = 0; }
  return {units, scale};
}
function plus(left: DecimalValue, right: DecimalValue): DecimalValue {
  const scale = Math.max(left.scale, right.scale);
  return {units: left.units * 10n ** BigInt(scale - left.scale)
    + right.units * 10n ** BigInt(scale - right.scale), scale};
}
function fixed(value: DecimalValue): string {
  const digits = value.units.toString().padStart(value.scale + 1, '0');
  return value.scale ? digits.slice(0, -value.scale) + '.' + digits.slice(-value.scale) : digits;
}
function totals(invoices: ReceivableInvoice[]): CurrencyTotal[] {
  const grouped = new Map<string, {value: DecimalValue; count: number}>();
  for (const invoice of invoices) {
    const existing = grouped.get(invoice.currency);
    const amount = decimal(invoice.balance);
    grouped.set(invoice.currency, {value: existing ? plus(existing.value, amount) : amount,
      count: (existing?.count || 0) + 1});
  }
  return [...grouped].sort(([a], [b]) => compare(a, b))
    .map(([currency, entry]) => ({currency, balance: fixed(entry.value), invoiceCount: entry.count}));
}

/** Admission is complete before any totals are exposed; native source objects are not retained. */
export function projectReceivables(snapshot: unknown): Receivables {
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) throw new Error('A native snapshot is required.');
  const value = snapshot as Record<string, unknown>;
  const todayNumber = day(value.today, 'snapshot date');
  if (!Array.isArray(value.ledger)) throw new Error('A complete native ledger is required.');
  const seen = new Set<string>(), clients = new Map<string, ClientReceivables>();
  const excluded = new Map<string, number>();
  let invoiceCount = 0;
  for (const [position, raw] of value.ledger.entries()) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error(`Invalid ledger row ${position + 1}.`);
    const row = raw as Record<string, unknown>;
    const invoice_id = text(row.invoice_id, 'invoice identity');
    if (seen.has(invoice_id)) throw new Error('Duplicate invoice identity in the native ledger.');
    seen.add(invoice_id);
    const invoice_number = text(row.invoice_number, 'invoice number');
    const client_email = text(row.client_email, 'billing email');
    if (row.client_name !== null && typeof row.client_name !== 'string') throw new Error('Invalid native client name.');
    const client_name = row.client_name as string | null;
    const currency = text(row.currency, 'currency');
    if (!/^[A-Z]{3}$/.test(currency)) throw new Error('Invalid native currency code.');
    const status = text(row.status, 'invoice status');
    const amount = decimal(row.balance);
    const dueNumber = row.due_on === null ? null : day(row.due_on, 'invoice due date');
    const due_on = row.due_on as string | null;
    if (!OPEN.has(status) || amount.units === 0n) {
      const reason = OPEN.has(status) ? 'ZERO_BALANCE' : status;
      excluded.set(reason, (excluded.get(reason) || 0) + 1);
      continue;
    }
    const difference = dueNumber === null ? 0 : todayNumber - dueNumber;
    const dueState: DueState = dueNumber === null ? 'undated'
      : difference > 0 ? 'overdue' : difference === 0 ? 'today' : 'later';
    const invoice: ReceivableInvoice = {invoice_id, invoice_number, client_email, client_name,
      currency, balance: row.balance as string, status, due_on, dueState,
      daysOverdue: Math.max(0, difference)};
    let client = clients.get(client_email);
    if (!client) { client = {email: client_email, names: [], invoices: []}; clients.set(client_email, client); }
    if (client_name && !client.names.includes(client_name)) client.names.push(client_name);
    client.invoices.push(invoice); invoiceCount++;
  }
  return {today: value.today as string, ledgerCount: value.ledger.length, invoiceCount,
    clients: [...clients.values()].sort((a, b) => compare(a.email, b.email)),
    excluded: [...excluded].sort(([a], [b]) => compare(a, b)).map(([status, count]) => ({status, count}))};
}

/** Filters select existing admitted rows and never mutate their source projection. */
export function receivablesFor(view: Receivables, filter: {email: string | null; due: 'all' | DueState}): ReceivablesSelection {
  if (filter.due !== 'all' && !Object.prototype.hasOwnProperty.call(DUE, filter.due)) throw new Error('Unknown due-state filter.');
  const clients = view.clients.filter(client => filter.email === null || client.email === filter.email)
    .map(client => ({email: client.email, names: [...client.names],
      invoices: client.invoices.filter(invoice => filter.due === 'all' || invoice.dueState === filter.due)
        .map(invoice => ({...invoice}))}))
    .filter(client => client.invoices.length);
  const invoices = clients.flatMap(client => client.invoices);
  return {clients, totals: totals(invoices), invoiceCount: invoices.length};
}

const escape = (value: string) => value.replace(/[&<>"']/g, character =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]!));
function moneyMarkup(values: CurrencyTotal[]): string {
  return values.map(value => `<div class="receivables-amount"><span>${escape(value.currency)}</span><strong>${escape(value.balance)}</strong><small>${value.invoiceCount} invoice${value.invoiceCount === 1 ? '' : 's'}</small></div>`).join('');
}
function clientMarkup(client: ClientReceivables): string {
  return `<article class="receivables-client"><header><h3>${escape(client.names.join(' / ') || client.email)}</h3><p>${escape(client.email)}</p></header>
    <div class="receivables-amounts">${moneyMarkup(totals(client.invoices))}</div>
    <ul class="receivables-invoices">${client.invoices.map(invoice => `<li data-due-state="${invoice.dueState}">
      <div><strong>${escape(invoice.invoice_number)}</strong><span>${escape(invoice.status)}</span></div>
      <div class="receivables-invoice-balance">${escape(invoice.currency)} ${escape(invoice.balance)}</div>
      <p><b>${DUE[invoice.dueState]}</b>${invoice.due_on ? ' · ' + escape(invoice.due_on) : ' · No due date recorded'}${invoice.daysOverdue ? ' · ' + invoice.daysOverdue + ' day' + (invoice.daysOverdue === 1 ? '' : 's') + ' late' : ''}</p>
      <small>Invoice ID: ${escape(invoice.invoice_id)}</small></li>`).join('')}</ul></article>`;
}

export type ReceivablesElements = {
  mount: HTMLElement; note: HTMLElement; client: HTMLSelectElement; due: HTMLSelectElement;
  reset: HTMLButtonElement; summary: HTMLElement; list: HTMLElement;
};
/** No provider/Worker references: this controller only reads a detached accepted snapshot. */
export function createReceivablesView(elements: ReceivablesElements) {
  let prepared: Receivables | null = null, invalid = '', ready = false, busy = false;
  let email: string | null = null, due: 'all' | DueState = 'all';
  const {mount, note, client, due: dueSelect, reset, summary, list} = elements;
  function render() {
    const usable = ready && !busy && prepared !== null && !invalid;
    for (const control of [client, dueSelect, reset]) control.disabled = !usable || !prepared?.invoiceCount;
    summary.innerHTML = ''; list.innerHTML = '';
    if (!usable) {
      mount.dataset.state = busy ? 'busy' : !ready ? 'unavailable' : 'invalid';
      note.textContent = busy ? 'Updating the sandbox. Client balances will return with the accepted snapshot.'
        : !ready ? 'Load the local engine to review client balances.'
        : invalid ? 'Client balances unavailable: ' + invalid : 'Waiting for an accepted sandbox snapshot.';
      if (!prepared) { client.innerHTML = '<option value="">All clients</option>'; client.value = ''; }
      return;
    }
    const current = prepared!;
    mount.dataset.state = current.invoiceCount ? 'ready' : 'empty';
    client.innerHTML = '<option value="">All clients</option>' + current.clients.map((entry, index) =>
      `<option value="${index}">${escape(entry.email)}</option>`).join('');
    const index = current.clients.findIndex(entry => entry.email === email);
    client.value = email === null || index < 0 ? '' : String(index);
    dueSelect.value = due;
    const selected = receivablesFor(current, {email, due});
    const outside = current.excluded.map(entry => `${entry.count} ${entry.status === 'ZERO_BALANCE' ? 'zero balance' : entry.status}`).join(', ');
    note.textContent = `Snapshot ${current.today}. Showing ${selected.invoiceCount} of ${current.invoiceCount} outstanding invoices. ${email === null ? 'All clients' : email}; ${due === 'all' ? 'all due states' : DUE[due]}.`
      + (outside ? ` Not counted: ${outside}.` : '');
    if (!current.invoiceCount) {
      list.innerHTML = '<p class="empty">No positive open balances in this sandbox ledger.</p>';
    } else if (!selected.invoiceCount) {
      list.innerHTML = '<p class="empty">No outstanding invoices match these filters.</p>';
    } else {
      summary.innerHTML = '<p class="receivables-selection-label">TOTALS FOR THIS SELECTION · SEPARATE CURRENCIES</p><div class="receivables-amounts">'
        + moneyMarkup(selected.totals) + '</div>';
      list.innerHTML = selected.clients.map(clientMarkup).join('');
    }
  }
  client.addEventListener('change', () => {
    const index = client.value === '' ? -1 : Number(client.value);
    email = prepared && Number.isInteger(index) && index >= 0 ? prepared.clients[index]?.email ?? null : null;
    render();
  });
  dueSelect.addEventListener('change', () => {
    due = Object.prototype.hasOwnProperty.call(DUE, dueSelect.value) ? dueSelect.value as DueState : 'all';
    render();
  });
  reset.addEventListener('click', () => { email = null; due = 'all'; render(); });
  render();
  return {
    setSnapshot(snapshot: unknown) {
      try {
        prepared = projectReceivables(snapshot); invalid = '';
        if (!prepared.clients.some(entry => entry.email === email)) email = null;
        if (!prepared.invoiceCount) due = 'all';
      } catch (error) {
        prepared = null; invalid = error instanceof Error ? error.message : 'Invalid native snapshot.';
        email = null; due = 'all';
      }
      render();
    },
    setAvailability(isReady: boolean, isBusy: boolean) {
      // A lost running session cannot revive its old board merely by becoming ready again.
      if (ready && !isReady) { prepared = null; invalid = ''; email = null; due = 'all'; }
      ready = isReady; busy = isBusy; render();
    },
  };
}
