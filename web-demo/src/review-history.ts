import {approvalProposalMarkup, type PendingApproval} from './approval-preview';

type Fields = Record<string, unknown>;
const fields = (value: unknown): Fields =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Fields : {};
const escape = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g,
  character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]!));
const text = (value: unknown): string =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : 'Not recorded';

function completedReviewMarkup(record: Fields): string {
  const status = String(record.status);
  const outcomeUnknown = fields(record.result).outcome === 'UNKNOWN';
  const kind = record.kind === 'send_invoice' ? 'SEND INVOICE' :
    record.kind === 'send_reminder' ? 'SEND REMINDER' : text(record.kind);
  const proposal: PendingApproval = {
    id: text(record.id), kind: text(record.kind), invoice_id: text(record.invoice_id),
    summary: text(record.summary), payload: record.payload,
  };
  const result = record.result === null || record.result === undefined
    ? 'No result details were recorded.' : JSON.stringify(record.result, null, 2);
  return '<details class="completed-review" data-review-id="' + escape(proposal.id) + '">' +
    '<summary><span class="review-status review-status-' + status.toLowerCase() + '">' +
    escape(status) + (outcomeUnknown ? ' · OUTCOME UNKNOWN' : '') + '</span> ' +
    '<span class="review-kind">' + escape(kind) + '</span> ' +
    '<span class="review-invoice">' + escape(proposal.invoice_id) + '</span></summary>' +
    '<div class="completed-review-body"><p class="approval-summary">' + escape(proposal.summary) + '</p>' +
    '<dl class="approval-fields"><div><dt>Action ID</dt><dd>' + escape(proposal.id) + '</dd></div>' +
    '<div><dt>Queued at</dt><dd>' + escape(text(record.created_at)) + '</dd></div></dl>' +
    approvalProposalMarkup(proposal, 'completed') +
    '<section class="review-result" aria-label="Recorded action result"><h3>Recorded result</h3>' +
    (outcomeUnknown ? '<p class="review-unknown">Outcome unknown. Check the invoice before creating another approval.</p>' : '') +
    '<pre data-review-result>' + escape(result) + '</pre></section></div></details>';
}

/** Render retained results only; there are no action handlers or provider calls. */
export function completedReviewsMarkup(value: unknown): string {
  const records = Array.isArray(value) ? value.map(fields).filter(record =>
    ['APPROVED', 'REJECTED', 'FAILED'].includes(String(record.status))) : [];
  return records.length ? records.map(completedReviewMarkup).join('') :
    '<p class="empty">No completed reviews in this sandbox yet.</p>';
}

/** Preserve disclosures across ordinary snapshots; reset removes their IDs. */
export function renderCompletedReviews(container: HTMLElement, value: unknown): void {
  const openIds = new Set(Array.from(container.querySelectorAll<HTMLDetailsElement>('details.completed-review'))
    .filter(panel => panel.open).map(panel => panel.dataset.reviewId));
  const focused = container.ownerDocument?.activeElement;
  const focusId = focused?.tagName === 'SUMMARY' && container.contains(focused)
    ? focused.parentElement?.dataset.reviewId : undefined;
  container.innerHTML = completedReviewsMarkup(value);
  for (const panel of Array.from(container.querySelectorAll<HTMLDetailsElement>('details.completed-review'))) {
    if (openIds.has(panel.dataset.reviewId)) panel.open = true;
    if (focusId !== undefined && panel.dataset.reviewId === focusId) panel.querySelector<HTMLElement>('summary')?.focus();
  }
}
