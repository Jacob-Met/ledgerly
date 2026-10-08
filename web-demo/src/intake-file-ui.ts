import {decodeIntakeFile, encodeIntakeFile, MAX_INTAKE_BYTES, type IntakeFile, type IntakeSnapshot} from './intake-file';

import {reviewLinesMarkup} from './review';

type Callbacks = {
  snapshot: () => IntakeSnapshot;
  replace: (file: IntakeFile) => Promise<boolean>;
};

function node<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string): HTMLElementTagNameMap[K] {
  const value = document.createElement(tag);
  if (text !== undefined) value.textContent = text;
  return value;
}

/** Refuse imported strings the existing single-line/editor controls would silently alter. */
function checkEditorValues(file: IntakeFile): void {
  const source = document.createElement('textarea');
  source.value = file.source_text;
  if (source.value !== file.source_text) throw new Error('The source text cannot be restored exactly in the intake editor.');
  if (!file.review_fields) return;
  const fields = file.review_fields;
  const values: [string, string][] = [
    ['text', fields.client_name], ['email', fields.client_email],
    ['text', fields.due_days], ['text', fields.amount_paid],
    ...fields.line_items.flatMap(row => Object.values(row).map(value => ['text', value] as [string, string])),
  ];
  const rendered = document.createElement('div');
  rendered.innerHTML = reviewLinesMarkup(fields.line_items, []);
  const restored = Array.from(rendered.querySelectorAll<HTMLElement>('[data-review-line]')).map(row =>
    Object.fromEntries(['desc', 'qty', 'unit_price', 'currency', 'unit'].map(key =>
      [key, row.querySelector<HTMLInputElement>('[data-field="' + key + '"]')!.value])));
  if (JSON.stringify(restored) !== JSON.stringify(fields.line_items)) {
    throw new Error('A saved line item cannot be restored exactly in the invoice editor.');
  }
  for (const [type, value] of values) {
    const input = document.createElement('input');
    input.type = type;
    input.value = value;
    if (input.value !== value) throw new Error('A saved field cannot be restored exactly in the invoice editor.');
  }
}

export function createIntakeFileControls(mount: HTMLElement, callbacks: Callbacks) {
  let ready = false, busy = false, applying = false, generation = 0;
  let preview: IntakeFile | null = null;
  const section = node('section');
  section.className = 'intake-files';
  section.setAttribute('aria-labelledby', 'intake-files-heading');
  const heading = node('h3', 'Continue this intake later');
  heading.id = 'intake-files-heading';
  const help = node('p', 'Save the source email and unfinished correction fields to a local file. Reopening requires fresh Python checks; the sandbox ledger stays separate.');
  const actions = node('div');
  actions.className = 'intake-file-actions';
  const save = node('button', 'Save intake');
  save.id = 'intake-save';
  save.type = 'button';
  save.className = 'button button-secondary';
  const open = node('button', 'Open intake');
  open.id = 'intake-open';
  open.type = 'button';
  open.className = 'button button-secondary';
  const input = node('input');
  input.id = 'intake-file';
  input.type = 'file';
  input.accept = '.json,application/json';
  input.hidden = true;
  const feedback = node('p');
  feedback.id = 'intake-file-status';
  feedback.setAttribute('role', 'status');
  feedback.setAttribute('aria-live', 'polite');
  const panel = node('section');
  panel.id = 'intake-preview';
  panel.hidden = true;
  panel.setAttribute('aria-labelledby', 'intake-preview-heading');
  const previewHeading = node('h4', 'Review the intake file');
  previewHeading.id = 'intake-preview-heading';
  previewHeading.tabIndex = -1;
  const metadata = node('p');
  metadata.id = 'intake-preview-summary';
  const source = node('pre');
  source.id = 'intake-preview-source';
  const sourceHelp = node('p', 'Source preview: first 2,000 characters. Replacement loads the complete source and all saved editable fields.');
  sourceHelp.className = 'fine-print';
  const replace = node('button', 'Replace current intake');
  replace.id = 'intake-replace';
  replace.type = 'button';
  replace.className = 'button button-primary';
  const cancel = node('button', 'Keep current intake');
  cancel.id = 'intake-cancel';
  cancel.type = 'button';
  cancel.className = 'button button-secondary';
  const warning = node('p', 'Replacement changes the current source and corrections. Save your current intake first if you need it. Existing invoices and queued approvals are unchanged.');
  const previewActions = node('div');
  previewActions.className = 'intake-file-actions';
  previewActions.append(replace, cancel);
  panel.append(previewHeading, metadata, source, sourceHelp, warning, previewActions);
  actions.append(save, open, input);
  section.append(heading, help, actions, feedback, panel);
  mount.append(section);

  function update() {
    const current = callbacks.snapshot();
    save.disabled = busy || applying || (!current.sourceText && !current.fields);
    open.disabled = busy || applying;
    input.disabled = busy || applying;
    replace.disabled = !ready || busy || applying || !preview;
    cancel.disabled = applying;
  }
  function clear(message = '') {
    generation++;
    preview = null;
    panel.hidden = true;
    metadata.textContent = '';
    source.textContent = '';
    input.value = '';
    if (message) feedback.textContent = message;
    update();
  }
  function changed(message = 'Current intake changed. Open the file again to review its replacement.') {
    if (applying) return;
    const hadFile = preview !== null || feedback.dataset.reading === 'true';
    clear(hadFile ? message : '');
    delete feedback.dataset.reading;
  }

  save.addEventListener('click', () => {
    if (busy || applying || save.disabled) return;
    let objectUrl: string | undefined;
    let link: HTMLAnchorElement | undefined;
    try {
      const artifact = encodeIntakeFile(callbacks.snapshot());
      objectUrl = URL.createObjectURL(new Blob([artifact.text], {type: 'application/json;charset=utf-8'}));
      link = node('a');
      link.href = objectUrl;
      link.download = artifact.filename;
      link.hidden = true;
      section.append(link);
      link.click();
      feedback.textContent = 'Intake download prepared: ' + artifact.filename + '. Keep this file to reopen your unfinished input.';
    } catch (error) {
      feedback.textContent = error instanceof Error ? error.message : 'The intake download could not be prepared. Your input remains here.';
    } finally {
      link?.remove();
      if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl!), 1000);
    }
  });
  open.addEventListener('click', () => {
    if (busy || applying) return;
    clear();
    input.click();
  });
  input.addEventListener('cancel', () => clear('File selection cancelled. Current intake is unchanged.'));
  input.addEventListener('change', async () => {
    if (busy || applying) return;
    const file = input.files?.[0];
    clear();
    if (!file) return;
    const ticket = generation;
    feedback.textContent = 'Reading intake file...';
    feedback.dataset.reading = 'true';
    try {
      if (file.size > MAX_INTAKE_BYTES) throw new Error('Choose an intake file no larger than 2 MiB.');
      const bytes = await file.arrayBuffer();
      if (ticket !== generation) return;
      let raw: string;
      try { raw = new TextDecoder('utf-8', {fatal: true}).decode(bytes); }
      catch { throw new Error('The intake file is not valid UTF-8.'); }
      const admitted = decodeIntakeFile(raw);
      checkEditorValues(admitted);
      if (ticket !== generation) return;
      preview = admitted;
      metadata.textContent = file.name + ' · saved ' + admitted.saved_at + ' · '
        + (admitted.review_fields ? admitted.review_fields.line_items.length + ' editable line items'
          + ' · recipient ' + (admitted.review_fields.client_email || '(unfinished)') : 'source email only');
      source.textContent = admitted.source_text.slice(0, 2000);
      panel.hidden = false;
      feedback.textContent = ready
        ? 'File ready for review. Current intake is unchanged until you choose Replace current intake.'
        : 'File ready for review. Load the local Python engine before replacing the intake.';
      previewHeading.focus();
    } catch (error) {
      if (ticket === generation) feedback.textContent = (error instanceof Error ? error.message : 'The intake file could not be read.') + ' Current intake is unchanged.';
    } finally {
      if (ticket === generation) {
        delete feedback.dataset.reading;
        update();
      }
    }
  });
  cancel.addEventListener('click', () => {
    if (applying) return;
    clear('Kept the current intake. No file was applied.');
    open.focus();
  });
  section.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden && !applying) {
      event.preventDefault();
      clear('Kept the current intake. No file was applied.');
      open.focus();
    }
  });
  replace.addEventListener('click', async () => {
    if (!ready || busy || applying || !preview) return;
    const file = preview;
    applying = true;
    generation++;
    update();
    feedback.textContent = 'Analyzing the saved source with Python before restoring its unfinished fields...';
    try {
      if (await callbacks.replace(file)) {
        preview = null;
        panel.hidden = true;
        source.textContent = '';
        metadata.textContent = '';
        feedback.textContent = file.review_fields
          ? 'Intake restored. Read the current Python warnings, confirm the unfinished fields and check them before drafting.'
          : 'Source restored and freshly analyzed. Review the current Python result before drafting.';
      } else {
        feedback.textContent = 'The source could not be analyzed. Previous input is retained and its old review is retired. Retry explicitly or keep the current intake.';
      }
    } catch {
      feedback.textContent = 'The intake could not be restored. Inspect the current input and check it before drafting.';
    } finally {
      applying = false;
      update();
    }
  });
  update();
  return {
    setAvailability(nextReady: boolean, nextBusy: boolean) { ready = nextReady; busy = nextBusy; update(); },
    currentChanged: changed,
  };
}
