/** Optional notes bound to pending action IDs until an explicit rejection. */
export const REJECTION_REASON_LIMIT = 500;

export function createRejectionReasons(root: HTMLElement) {
  const drafts = new Map<string, string>();
  let available = false;
  let serial = 0;

  function inputs() {
    return Array.from(root.querySelectorAll<HTMLTextAreaElement>('textarea[data-rejection-reason]'));
  }
  function check(input: HTMLTextAreaElement) {
    const length = Array.from(input.value).length;
    const message = length > REJECTION_REASON_LIMIT
      ? `Use at most ${REJECTION_REASON_LIMIT} characters for the rejection reason.` : '';
    input.setCustomValidity(message);
    input.setAttribute('aria-invalid', String(Boolean(message)));
    const help = document.getElementById(input.getAttribute('aria-describedby') || '');
    if (help) help.textContent = message || `${length}/${REJECTION_REASON_LIMIT} characters. Saved only when you choose Reject.`;
    return message;
  }

  root.addEventListener('input', event => {
    const input = event.target;
    if (!(input instanceof HTMLTextAreaElement) || !input.hasAttribute('data-rejection-reason')) return;
    drafts.set(input.dataset.rejectionReason!, input.value);
    check(input);
  });

  return {
    afterRender(actionIds: string[]) {
      const pending = new Set(actionIds);
      for (const id of drafts.keys()) if (!pending.has(id)) drafts.delete(id);
      for (const card of Array.from(root.querySelectorAll<HTMLElement>('article[data-approval-id]'))) {
        const id = card.dataset.approvalId!;
        if (!pending.has(id)) continue;
        const label = document.createElement('label');
        label.className = 'rejection-reason';
        const title = document.createElement('span');
        title.textContent = 'Reason for rejecting (optional)';
        const input = document.createElement('textarea');
        input.dataset.rejectionReason = id;
        input.id = `rejection-reason-${++serial}`;
        input.rows = 2;
        input.value = drafts.get(id) || '';
        input.disabled = !available;
        const help = document.createElement('span');
        help.className = 'rejection-reason-help';
        help.id = input.id + '-help';
        input.setAttribute('aria-describedby', help.id);
        label.append(title, input, help);
        card.insertBefore(label, card.querySelector('.button-row'));
        check(input);
      }
    },
    setAvailability(ready: boolean, busy: boolean) {
      available = ready && !busy;
      for (const input of inputs()) input.disabled = !available;
    },
    read(actionId: string): {ok: true; value: string} | {ok: false; message: string} {
      const input = inputs().find(field => field.dataset.rejectionReason === actionId);
      if (!input) return {ok: false, message: 'This pending action is no longer available. Review the current queue.'};
      drafts.set(actionId, input.value);
      const message = check(input);
      if (message) {
        input.reportValidity();
        input.focus();
        return {ok: false, message};
      }
      return {ok: true, value: input.value};
    },
  };
}
