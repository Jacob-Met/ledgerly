/** A read-only CSV view of the last displayed Python sandbox ledger. */
export type LedgerDownload = Readonly<{text: string; filename: string; count: number}>;

const columns = [
  'Record type', 'Snapshot date', 'Invoice ID', 'Invoice number', 'Client name',
  'Client email', 'Currency', 'Total', 'Paid', 'Balance', 'Status', 'Sent date',
  'Due date', 'Reminders sent',
] as const;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('The displayed ledger is not available for export.');
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, optional = false): string {
  if (optional && value == null) return '';
  if (typeof value !== 'string') {
    throw new Error('The displayed ledger contains an incomplete record.');
  }
  return value;
}

function cell(value: string, amount = false): string {
  // Keep existing decimal strings; do not calculate or reprice an amount.
  const decimal = amount && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value);
  const formulaLike = /^[\s\p{Cf}]*[=+\-@＝＋－＠]/u.test(value) || /^[\t\r\n]/.test(value);
  // This explicit export convention does not promise behavior in every editor.
  const literal = formulaLike && !decimal ? "'" + value : value;
  return '"' + literal.replace(/"/g, '""') + '"';
}

/** Copy snapshot values without calculating money or changing Python state. */
export function ledgerCsv(value: unknown): LedgerDownload {
  const snapshot = record(value);
  const day = text(snapshot.today);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !Array.isArray(snapshot.ledger)) {
    throw new Error('The displayed ledger is not available for export.');
  }
  const rows = snapshot.ledger.map((item) => {
    const entry = record(item);
    const reminders = entry.reminders_sent;
    if (typeof reminders !== 'number' || !Number.isSafeInteger(reminders) || reminders < 0) {
      throw new Error('The displayed ledger contains an incomplete record.');
    }
    return [
      'SANDBOX', day, text(entry.invoice_id), text(entry.invoice_number),
      text(entry.client_name, true), text(entry.client_email), text(entry.currency),
      text(entry.total), text(entry.paid_amount), text(entry.balance), text(entry.status),
      text(entry.sent_on, true), text(entry.due_on, true), String(reminders),
    ];
  });
  const lines = [
    columns.map((value) => cell(value)),
    ...rows.map((row) => row.map((value, index) => cell(value, index >= 7 && index <= 9))),
  ];
  // UTF-8 BOM helps spreadsheet readers retain the visitor's Unicode text.
  return Object.freeze({
    text: '\uFEFF' + lines.map((row) => row.join(',')).join('\r\n') + '\r\n',
    filename: 'ledgerly-sandbox-' + day + '.csv',
    count: rows.length,
  });
}

/** Bind an explicit download button; this controller has no worker or provider API. */
export function createLedgerExport(button: HTMLButtonElement, note: HTMLElement) {
  let snapshot: LedgerDownload | null = null;
  let available = false;
  let invalid = false;

  function update() {
    button.disabled = !available || !snapshot?.count;
    note.textContent = invalid
      ? 'The displayed ledger could not be prepared for download.'
      : !available
        ? 'Download is available when the local engine is ready.'
        : !snapshot?.count
          ? 'Create a sandbox invoice to download its ledger.'
          : snapshot.count + ' sandbox invoice' + (snapshot.count === 1 ? '' : 's') +
            '. Each row keeps its own currency and balances.';
  }

  button.addEventListener('click', () => {
    if (!available || !snapshot?.count) return;
    const selected = snapshot;
    let url: string | null = null;
    let anchor: HTMLAnchorElement | null = null;
    try {
      const blob = new Blob([selected.text], {type: 'text/csv;charset=utf-8;header=present'});
      url = URL.createObjectURL(blob);
      anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = selected.filename;
      document.body.append(anchor);
      anchor.click();
      note.textContent = 'CSV prepared for ' + selected.count + ' sandbox invoice' +
        (selected.count === 1 ? '' : 's') + '.';
    } catch {
      note.textContent = 'The CSV download could not start. Your ledger is unchanged; try downloading again.';
    } finally {
      anchor?.remove();
      if (url) {
        const released = url;
        // Let the browser consume the selected Blob before releasing its URL.
        setTimeout(() => URL.revokeObjectURL(released), 1000);
      }
    }
  });

  update();
  return {
    setSnapshot(value: unknown) {
      try {
        snapshot = ledgerCsv(value);
        invalid = false;
      } catch {
        snapshot = null;
        invalid = true;
      }
      update();
    },
    setAvailable(value: boolean) {
      available = value;
      update();
    },
  };
}
