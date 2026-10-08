import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire, stripTypeScriptTypes} from 'node:module';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES + '/playwright');
const source = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const executable = process.argv[4] || '/workspace/scratch/ce7eb129730f/project-browser-runtime/tmp/chromium';
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const bytes = fs.readFileSync(source);
const compiled = stripTypeScriptTypes(bytes.toString('utf8'), {mode: 'strip'});
const moduleUrl = 'data:text/javascript;base64,' + Buffer.from(compiled).toString('base64');
const cases = [], network = [], errors = [];
fs.mkdirSync(path.dirname(output), {recursive: true});
const browser = await chromium.launch({executablePath: executable, headless: true, args: ['--no-sandbox']});
const context = await browser.newContext();
await context.route(/^https?:/, route => { network.push(route.request().url()); return route.abort(); });

async function setup() {
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  await page.setContent('<!doctype html><html><body><main id="ledger-list"></main></body></html>');
  await page.evaluate(async url => {
    const {createInvoiceDetailsView} = await import(url);
    const container = document.querySelector('#ledger-list');
    const view = createInvoiceDetailsView(container);
    const state = {today: '2026-10-08', invoice_details: [{invoice_id: 'INV-1', record: {
      id: 'INV-1', status: 'SENT', detail: {note: 'Synthetic retained invoice'}, items: [],
    }}]};
    window.receiver = {container, view, state, render(ids = ['INV-1']) {
      view.beforeRender(ids);
      container.innerHTML = ids.map(id => view.markup(id, state)).join('');
      view.afterRender();
      view.setAvailability(true, false);
    }};
    window.receiver.render();
  }, moduleUrl);
  return page;
}

try {
  let page = await setup();
  const opening = await page.evaluate(() => {
    const r = window.receiver;
    const summary = r.container.querySelector('summary');
    summary.focus();
    summary.click(); // Native disclosure toggles now; its toggle event is queued.
    const before = r.container.querySelector('details').open;
    r.state.today = '2026-10-09';
    r.render(); // Same view hooks used when an already-running action returns.
    return {before, after: r.container.querySelector('details').open,
      focusRestored: document.activeElement === r.container.querySelector('summary'),
      newSnapshotRendered: r.container.textContent.includes('2026-10-09')};
  });
  cases.push({id: 'just_opened_disclosure_survives_refresh', expected: true, observed: opening,
    passed: opening.before && opening.after && opening.focusRestored && opening.newSnapshotRendered});
  await page.close();

  page = await setup();
  await page.evaluate(() => window.receiver.container.querySelector('summary').click());
  await page.waitForFunction(() => window.receiver.view.markup('INV-1', window.receiver.state).includes(' open'));
  const closing = await page.evaluate(() => {
    const r = window.receiver;
    r.container.querySelector('summary').focus();
    r.container.querySelector('summary').click();
    const before = r.container.querySelector('details').open;
    r.state.today = '2026-10-10';
    r.render();
    return {before, after: r.container.querySelector('details').open,
      focusRestored: document.activeElement === r.container.querySelector('summary'),
      newSnapshotRendered: r.container.textContent.includes('2026-10-10')};
  });
  cases.push({id: 'just_closed_disclosure_stays_closed_on_refresh', expected: false, observed: closing,
    passed: !closing.before && !closing.after && closing.focusRestored && closing.newSnapshotRendered});
  await page.close();

  page = await setup();
  await page.evaluate(() => window.receiver.container.querySelector('summary').click());
  await page.waitForFunction(() => window.receiver.view.markup('INV-1', window.receiver.state).includes(' open'));
  const settled = await page.evaluate(() => {
    const r = window.receiver;
    r.render();
    const retained = r.container.querySelector('details').open;
    r.render([]);
    const removed = !r.container.querySelector('details');
    r.render(['INV-1']);
    return {retained, removed, reopenedIdentityStartsClosed: !r.container.querySelector('details').open};
  });
  cases.push({id: 'settled_toggle_and_removed_identity_negative_control', observed: settled,
    passed: Object.values(settled).every(Boolean)});
  await page.close();
} finally {
  const report = {schema: 'hamon.independent_browser_control.v1',
    source, source_sha256: digest(bytes), stripped_javascript_sha256: digest(compiled),
    receiver_sha256: digest(fs.readFileSync(new URL(import.meta.url))),
    chromium: await browser.version(), executable, executable_sha256: digest(fs.readFileSync(executable)),
    node: process.version, scope: 'Isolated synthetic DOM using the exact production renderer and integration hook order; no Pyodide, native-host, provider, layout or full-app qualification claimed.',
    cases, external_request_attempts: network, page_errors: errors,
    passed: cases.length === 3 && cases.every(row => row.passed) && !network.length && !errors.length};
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify({output, source_sha256: report.source_sha256,
    passed: cases.filter(row => row.passed).length, failed: cases.filter(row => !row.passed).length,
    result: report.passed ? 'PASS' : 'FAIL', cases}));
  await context.close();
  await browser.close();
  if (!report.passed) process.exitCode = 1;
}
