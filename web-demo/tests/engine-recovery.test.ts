import {expect, it} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
import {WorkerClient, WorkerUnavailableError} from '../src/worker-client';
import {retryableLoader} from '../src/retryable-loader';
import {createLedgerExport} from '../src/ledger-export';
import {approvalListMarkup} from '../src/approval-preview';
import {createInvoiceDetailsView} from '../src/invoice-details';
import {readReviewFields, reviewMarkup, reviewLinesMarkup, reviewResultMarkup} from '../src/review';

const sourceRoot = process.env.LEDGERLY_RECOVERY_SOURCE_ROOT || path.resolve(process.cwd(), 'src');
const tick = () => new Promise<void>(resolve => setImmediate(resolve));
function executable(file: string) {
  const source = fs.readFileSync(path.join(sourceRoot, file), 'utf8')
    .replace(/^import[^\n]+\n/gm, '')
    .replace('import.meta.url', "'https://example.test/src/main.ts'");
  return ts.transpileModule(source, {compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  }}).outputText;
}

function app() {
  const elements = new Map<string, any>(), dynamicIds = new Set<string>();
  const dynamic = (selector: string) => selector.startsWith('#review-') || selector === '#engine-recovery-analysis';
  const decode = (value: string) => value.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  function ingest(markup: string) {
    for (const match of markup.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
      const selector = '#' + match[2], node = element(selector);
      dynamicIds.add(selector); node.tagName = match[1].toUpperCase();
      const value = match[0].match(/\bvalue="([^"]*)"/);
      if (value) node.value = decode(value[1]);
    }
  }
  function element(selector: string): any {
    if (!elements.has(selector)) {
      const classes = new Set<string>(), attributes = new Map<string, string>();
      let html = '';
      const node = {
        id: selector.slice(1), tagName: '', value: '', textContent: '', checked: false,
        dataset: {}, disabled: selector !== '#engine-start', handlers: {} as Record<string, (...args: any[]) => any>,
        get innerHTML() { return html; },
        set innerHTML(value: string) {
          html = value;
          if (selector === '#analysis') { for (const id of dynamicIds) elements.delete(id); dynamicIds.clear(); }
          ingest(value);
        },
        insertAdjacentHTML(position: string, value: string) { html = position === 'afterbegin' ? value + html : html + value; ingest(value); },
        classList: {add: (name: string) => classes.add(name), remove: (name: string) => classes.delete(name)},
        addEventListener(type: string, handler: (...args: any[]) => any) { this.handlers[type] = handler; },
        setAttribute: (key: string, value: string) => attributes.set(key, value),
        removeAttribute: (key: string) => attributes.delete(key),
        getAttribute: (key: string) => attributes.get(key),
        remove() { elements.delete(selector); dynamicIds.delete(selector); },
        closest: (query: string) => query === '#review-form' ? elements.get('#review-form') : null,
        elements: {namedItem: (name: string) => element('#' + ({
          client_name: 'review-client-name', client_email: 'review-client-email', due_days: 'review-due-days', amount_paid: 'review-amount-paid',
        } as Record<string, string>)[name])},
        querySelectorAll: (query: string) => {
          if (query !== '[data-review-line]') return [];
          return [...elements.keys()].filter(id => /^#review-line-\d+-desc$/.test(id)).map(id => ({
            querySelector: (fieldQuery: string) => {
              const field = fieldQuery.match(/data-field="([^"]+)"/)![1];
              return element(id.replace(/desc$/, field === 'unit_price' ? 'price' : field));
            },
          }));
        },
      };
      elements.set(selector, node);
    }
    return elements.get(selector);
  }
  const workers: FakeWorker[] = [];
  class FakeWorker {
    messages: any[] = [];
    listeners = new Map<string, Set<(event: any) => void>>();
    terminated = false;
    constructor() { workers.push(this); }
    addEventListener(type: string, listener: (event: any) => void) {
      if (!this.listeners.has(type)) this.listeners.set(type, new Set());
      this.listeners.get(type)!.add(listener);
    }
    removeEventListener(type: string, listener: (event: any) => void) { this.listeners.get(type)?.delete(listener); }
    postMessage(message: any) { this.messages.push(message); }
    terminate() { this.terminated = true; }
    emit(type: string, event: any) { for (const listener of this.listeners.get(type) || []) listener(event); }
    reply(index: number, data: any) { this.emit('message', {data: {id: this.messages[index].id, ok: true, data}}); }
  }
  const document = {
    activeElement: null,
    querySelector: (selector: string) => dynamic(selector) ? elements.get(selector) || null : element(selector),
    querySelectorAll: (selectors: string) => selectors.split(',').flatMap(selector => {
      const match = selector.match(/^#review-form (input|select|button)$/);
      if (match) return [...elements.values()].filter(node => node.id.startsWith('review-') && node.tagName === match[1].toUpperCase());
      return [element(selector)];
    }),
  };
  const context = vm.createContext({document, Worker: FakeWorker, URL, WorkerClient, WorkerUnavailableError,
    readReviewFields, reviewMarkup, reviewLinesMarkup, reviewResultMarkup, approvalListMarkup, createLedgerExport, createInvoiceDetailsView});
  vm.runInContext(executable('main.ts'), context);
  function click(selector: string) {
    let settled = false;
    const promise = element(selector).handlers.click().then(() => { settled = true; });
    return {promise, settled: () => settled};
  }
  function input(selector: string) { element('#analysis').handlers.input({target: element(selector)}); }
  function submitReview() {
    return element('#analysis').handlers.submit({target: element('#review-form'), preventDefault() {}});
  }
  return {element, workers, click, input, submitReview, document};
}

const empty = {ok: true, result: {}, state: {ledger: [], pending: [], audit: [], today: '2026-10-08', can_replay: false}};

it('actual startup hook settles a worker error, retains intake and enables an explicit empty restart', async () => {
  const fixture = app();
  fixture.element('#job-email').value = 'Typed fictional intake remains here.';
  const start = fixture.click('#engine-start');
  fixture.workers[0].emit('error', {message: 'Injected worker script failure'});
  await tick();
  expect(start.settled()).toBe(true);
  expect(fixture.element('#engine-start').disabled).toBe(false);
  expect(fixture.element('#engine-start').textContent).toBe('Restart empty sandbox');
  expect(fixture.element('#analyze').disabled).toBe(true);
  expect(fixture.element('#job-email').value).toBe('Typed fictional intake remains here.');
  expect(fixture.element('#status-message').textContent).toContain('no action will be replayed');
  expect(fixture.workers).toHaveLength(1);
  const restart = fixture.click('#engine-start');
  expect(fixture.workers[1].messages.map(message => message.action)).toEqual(['init']);
  fixture.workers[1].reply(0, empty);
  await tick();
  expect(restart.settled()).toBe(true);
  expect(fixture.element('#engine-status').textContent).toContain('READY');
  expect(fixture.element('#status-message').textContent).toContain('New empty sandbox');
  expect(fixture.element('#engine-recovery-analysis').textContent).toBe('New empty sandbox ready. Analyze the retained source email again.');
  expect(fixture.element('#draft').disabled).toBe(true);
  expect(fixture.element('#job-email').value).toBe('Typed fictional intake remains here.');
});

it('actual action hook disables the lost ledger and settles a pending draft without replay', async () => {
  const fixture = app();
  const start = fixture.click('#engine-start'); fixture.workers[0].reply(0, empty); await start.promise;
  fixture.element('#job-email').value = 'Fictional job, 2 hours at USD 50.';
  fixture.element('#payment-amount').value = '25.50';
  const analyzed = fixture.click('#analyze');
  fixture.workers[0].reply(1, {ok: true, state: empty.state, result: {
    confidence: 0.9, issues: [], line_items: [{desc: 'Work', qty: 2, unit_price: '50', currency: 'USD'}],
  }});
  await analyzed.promise;
  expect(fixture.element('#draft').disabled).toBe(false);
  const drafted = fixture.click('#draft');
  fixture.workers[0].emit('messageerror', {});
  await tick();
  expect(drafted.settled()).toBe(true);
  for (const selector of ['#draft', '#replay-webhook', '#approval-list button', '#ledger-list button'])
    expect(fixture.element(selector).disabled).toBe(true);
  expect(fixture.element('#ledger-list').getAttribute('aria-disabled')).toBe('true');
  expect(fixture.element('#payment-amount').value).toBe('25.50');
  expect(fixture.element('#job-email').value).toBe('Fictional job, 2 hours at USD 50.');
  expect(fixture.workers[0].messages.map(message => message.action)).toEqual(['init', 'analyze', 'draft']);
  const restarted = fixture.click('#engine-start');
  fixture.workers[1].reply(0, empty); await restarted.promise;
  expect(fixture.element('#ledger-list').innerHTML).toContain('No invoices');
  expect(fixture.element('#ledger-list').getAttribute('aria-disabled')).toBeUndefined();
  expect(fixture.element('#draft').disabled).toBe(true);
  expect(fixture.workers[1].messages.map(message => message.action)).toEqual(['init']);
});

it('actual startup hook refuses a completed transport whose initialization result is not ok', async () => {
  const fixture = app();
  const start = fixture.click('#engine-start');
  fixture.workers[0].reply(0, {ok: false, message: 'Injected bridge initialization failure', state: empty.state});
  await start.promise;
  expect(fixture.element('#analyze').disabled).toBe(true);
  expect(fixture.element('#engine-start').disabled).toBe(false);
  expect(fixture.element('#engine-status').textContent).not.toContain('READY');
  expect(fixture.element('#status-message').textContent).toContain('Injected bridge initialization failure');
});

it('actual worker startup retries a rejected runtime load on the next explicit init', async () => {
  let attempts = 0;
  const responses: any[] = [];
  let receive!: (event: any) => void;
  const runtime = {
    FS: {mkdirTree() {}, writeFile() {}},
    globals: new Map(),
    runPythonAsync: async (source: string) => source === 'bridge.handle_json(request_json)' ? JSON.stringify(empty) : undefined,
  };
  const context = vm.createContext({
    URL, retryableLoader,
    loadPyodide: async () => {
      if (++attempts === 1) throw new Error('Injected transient runtime fetch failure');
      return runtime;
    },
    fetch: async () => ({ok: true, text: async () => '# injected source fixture'}),
    self: {
      location: {href: 'https://example.test/assets/engine.worker.js'},
      addEventListener: (_type: string, handler: (event: any) => void) => { receive = handler; },
      postMessage: (message: any) => responses.push(message),
    },
  });
  vm.runInContext(executable('engine.worker.ts'), context);
  receive({data: {id: 1, action: 'init'}}); await vm.runInContext('queue', context);
  expect(responses[0]).toMatchObject({id: 1, ok: false});
  expect(attempts).toBe(1);
  receive({data: {id: 2, action: 'init'}}); await vm.runInContext('queue', context);
  expect(attempts).toBe(2);
  expect(responses.find(message => message.id === 2)).toMatchObject({id: 2, ok: true, data: {ok: true}});
});

it('retains typed corrections across failure and reopens analysis only on explicit revalidation', async () => {
  const fixture = app();
  const start = fixture.click('#engine-start'); fixture.workers[0].reply(0, empty); await start.promise;
  const text = 'Fictional source email requiring a corrected recipient.';
  fixture.element('#job-email').value = text;
  const extraction = {confidence: 0.8, client_name: 'Original client', client_email: '', due_days: 30,
    issues: [{field: 'client_email', severity: 'error', message: 'Recipient missing'}],
    line_items: [{desc: 'Original work', qty: 1, unit_price: '50', currency: 'USD', unit: 'hour'}],
    review_currencies: ['USD'], currency: 'USD'};
  const analyzed = fixture.click('#analyze');
  fixture.workers[0].reply(1, {ok: true, state: empty.state, result: extraction}); await analyzed.promise;
  const edits: Record<string, string> = {
    '#review-client-name': 'Corrected client', '#review-client-email': 'billing@example.test',
    '#review-due-days': '0', '#review-amount-paid': '10.50', '#review-line-0-desc': 'Typed corrected work',
    '#review-line-0-qty': '3', '#review-line-0-price': '25.25', '#review-line-0-currency': 'USD', '#review-line-0-unit': 'hours',
  };
  for (const [id, value] of Object.entries(edits)) fixture.element(id).value = value;
  const fields = readReviewFields(fixture.element('#review-form'));
  fixture.element('#review-confirm').checked = true; fixture.input('#review-confirm');
  const checked = fixture.submitReview();
  fixture.workers[0].reply(2, {ok: true, state: empty.state, result: {valid: true, review_id: 'old-worker-revision'}});
  await checked;
  expect(fixture.element('#draft').disabled).toBe(false);
  fixture.element('#demo-date').value = '2026-10-09';
  const advanced = fixture.click('#advance-clock');
  fixture.workers[0].emit('error', {message: 'Injected terminal failure with a checked correction form'});
  await tick();
  expect(advanced.settled()).toBe(true);
  expect(fixture.element('#review-confirm').checked).toBe(false);
  expect(fixture.element('#draft').disabled).toBe(true);
  for (const [id, value] of Object.entries(edits)) expect(fixture.element(id).value).toBe(value);
  const restarted = fixture.click('#engine-start'); fixture.workers[1].reply(0, empty); await restarted.promise;
  expect(fixture.workers[1].messages.map(message => message.action)).toEqual(['init']);
  expect(fixture.element('#review-confirm').checked).toBe(false);
  expect(fixture.element('#draft').disabled).toBe(true);
  expect(fixture.element('#engine-recovery-analysis').textContent).toContain('corrections are retained');
  for (const [id, value] of Object.entries(edits)) expect(fixture.element(id).value).toBe(value);
  fixture.element('#review-confirm').checked = true; fixture.input('#review-confirm');
  const rechecked = fixture.submitReview();
  expect(fixture.workers[1].messages[1]).toMatchObject({action: 'analyze', payload: {text}});
  fixture.workers[1].reply(1, {ok: true, state: empty.state, result: extraction}); await tick();
  expect(fixture.workers[1].messages[2]).toMatchObject({action: 'review', payload: {text, fields, confirmed: true}});
  fixture.workers[1].reply(2, {ok: true, state: empty.state, result: {valid: true, review_id: 'new-worker-revision'}});
  await rechecked;
  expect(fixture.document.querySelector('#engine-recovery-analysis')).toBeNull();
  expect(fixture.element('#draft').disabled).toBe(false);
  const drafted = fixture.click('#draft');
  expect(fixture.workers[1].messages[3]).toMatchObject({action: 'draft', payload: {text, review_id: 'new-worker-revision'}});
  fixture.workers[1].reply(3, {ok: true, state: empty.state, result: {unauthorized_send_blocked: true, final: 'Draft queued for separate approval'}});
  await drafted.promise;
  await fixture.click('#draft').promise;
  expect(fixture.workers[1].messages.map(message => message.action)).toEqual(['init', 'analyze', 'review', 'draft']);
  for (const [id, value] of Object.entries(edits)) expect(fixture.element(id).value).toBe(value);
});
