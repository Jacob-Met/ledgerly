export type ApprovalKindFilter = 'all' | 'send_invoice' | 'send_reminder';
export function approvalMatches(text: string, actionKind: string, query: string, kind: ApprovalKindFilter): boolean {
  return (kind === 'all' || actionKind === kind) && text.toLowerCase().includes(query.trim().toLowerCase());
}
interface Controls {
  list: HTMLElement; query: HTMLInputElement; kind: HTMLSelectElement;
  clear: HTMLButtonElement; note: HTMLElement; empty: HTMLElement;
}
interface Identity {id: string; invoiceId: string; kind: string}

/** A view over the original cards. This controller never submits or edits a queued action. */
export function createApprovalFilters(controls: Controls) {
  let identities: readonly Identity[] | null = null;
  let ready = false, busy = false;
  const cards = () => Array.from(controls.list.querySelectorAll<HTMLElement>(':scope > .approval-card'));
  function bound(rows: HTMLElement[]): boolean {
    return identities !== null && rows.length === identities.length && rows.every((card, index) => {
      const id = identities![index].id;
      const approve = card.querySelectorAll<HTMLButtonElement>('button[data-approve]');
      const reject = card.querySelectorAll<HTMLButtonElement>('button[data-reject]');
      return card.dataset.approvalId === id && approve.length === 1 && reject.length === 1
        && approve[0].dataset.approve === id && reject[0].dataset.reject === id;
    });
  }
  function paint() {
    const rows = cards(), kind = controls.kind.value;
    const valid = (kind === 'all' || kind === 'send_invoice' || kind === 'send_reminder') && bound(rows);
    controls.query.disabled = controls.kind.disabled = !ready || busy || !valid;
    controls.clear.disabled = !ready || busy;
    if (!valid) {
      for (const card of rows) card.hidden = false;
      controls.empty.hidden = true;
      controls.note.textContent = identities === null && !ready
        ? 'Load the local engine to find pending approvals.'
        : 'The displayed cards could not be matched to the current queue. All cards remain visible; filters are retained.';
      return;
    }
    let shown = 0;
    rows.forEach((card, index) => {
      const identity = identities![index];
      const text = Array.from(card.querySelectorAll<HTMLElement>('.approval-head,.approval-summary,.approval-preview'))
        .map(part => part.textContent || '').join('\n') + '\n' + identity.id + '\n' + identity.invoiceId;
      card.hidden = !approvalMatches(text, identity.kind, controls.query.value, kind);
      if (!card.hidden) shown++;
    });
    controls.empty.hidden = !ready || rows.length === 0 || shown !== 0;
    const count = shown + ' of ' + rows.length;
    controls.note.textContent = !ready
      ? 'Last displayed queue: ' + count + ' cards match. The Python session is unavailable; these actions are inactive. Filters are retained.'
      : 'Showing ' + count + ' pending approvals. ' + (busy
        ? 'Python is working; filter controls are temporarily unavailable.'
        : 'Filtering does not approve, reject or remove an action.');
  }
  function clear() {
    controls.query.value = ''; controls.kind.value = 'all'; paint();
  }
  controls.query.addEventListener('input', paint);
  controls.kind.addEventListener('change', paint);
  controls.clear.addEventListener('click', clear);
  paint();
  return {
    update(queue: unknown) {
      identities = null;
      if (Array.isArray(queue)) {
        const seen = new Set<string>(), copy: Identity[] = [];
        for (const action of queue) {
          if (!action || typeof action.id !== 'string' || !action.id || seen.has(action.id)
            || typeof action.invoice_id !== 'string' || typeof action.kind !== 'string') break;
          seen.add(action.id);
          copy.push({id: action.id, invoiceId: action.invoice_id, kind: action.kind});
        }
        if (copy.length === queue.length) identities = copy;
      }
      paint();
    },
    setAvailability(nextReady: boolean, nextBusy: boolean) {ready = nextReady; busy = nextBusy; paint();},
    clear,
  };
}
