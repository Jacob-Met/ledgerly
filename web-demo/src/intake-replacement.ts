import type {ReviewFields} from './review';

export function hasIntakeCorrections(current: ReviewFields | null, extracted: ReviewFields | null): boolean {
  return current !== null && extracted !== null && JSON.stringify(current) !== JSON.stringify(extracted);
}

export type IntakeChoice = 'keep' | 'replace' | 'cancel';

export function createIntakeReplacementReview(mount: HTMLElement) {
  const dialog = document.createElement('dialog');
  dialog.id = 'intake-replacement-dialog';
  dialog.className = 'intake-replacement';
  dialog.setAttribute('aria-labelledby', 'intake-replacement-heading');
  dialog.setAttribute('aria-describedby', 'intake-replacement-description');
  dialog.innerHTML = '<h2 id="intake-replacement-heading">Keep your invoice corrections?</h2><p id="intake-replacement-description"></p><div class="intake-replacement-actions"><button id="intake-keep-corrections" type="button" class="button button-primary">Analyze and keep corrections</button><button id="intake-use-extraction" type="button" class="button button-secondary">Analyze and use extracted fields</button><button id="intake-cancel-replacement" type="button" class="button button-secondary">Cancel</button></div>';
  mount.append(dialog);
  const keep = dialog.querySelector<HTMLButtonElement>('#intake-keep-corrections')!;
  const replace = dialog.querySelector<HTMLButtonElement>('#intake-use-extraction')!;
  const cancel = dialog.querySelector<HTMLButtonElement>('#intake-cancel-replacement')!;
  const description = dialog.querySelector<HTMLElement>('#intake-replacement-description')!;
  let settle: ((choice: IntakeChoice) => void) | null = null;
  function finish(choice: IntakeChoice) {
    const resolve = settle;
    settle = null;
    if (dialog.open) dialog.close();
    resolve?.(choice);
  }
  keep.addEventListener('click', () => finish('keep'));
  replace.addEventListener('click', () => finish('replace'));
  cancel.addEventListener('click', () => finish('cancel'));
  dialog.addEventListener('cancel', event => {event.preventDefault(); finish('cancel');});
  dialog.addEventListener('close', () => {if (!dialog.open) finish('cancel');});
  return {
    request(kind: 'analyze' | 'fixture'): Promise<IntakeChoice> {
      finish('cancel');
      keep.hidden = kind === 'fixture';
      replace.textContent = kind === 'fixture' ? 'Discard corrections and load example' : 'Analyze and use extracted fields';
      description.textContent = kind === 'fixture'
        ? 'Loading a fictional example replaces your source text and corrected fields. Save intake first if you want to keep a file. Cancel keeps this intake unchanged.'
        : 'Your corrected fields differ from the extraction. Analyze this source and keep those fields for a fresh review, or replace them with the new extraction. Nothing is drafted or approved by this choice.';
      return new Promise(resolve => {
        settle = resolve;
        dialog.showModal();
        (kind === 'fixture' ? cancel : keep).focus();
      });
    },
    cancel: () => finish('cancel'),
  };
}
