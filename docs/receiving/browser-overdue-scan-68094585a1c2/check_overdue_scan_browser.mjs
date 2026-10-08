import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const options = new Map();
for (let i = 2; i < process.argv.length; i += 2) options.set(process.argv[i], process.argv[i + 1]);
for (const key of ['--url', '--source', '--playwright', '--chrome', '--output'])
  if (!options.get(key)) throw new Error(`Required: ${key}`);
const url = new URL(options.get('--url'));
assert(url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname));
const source = path.resolve(options.get('--source'));
const output = path.resolve(options.get('--output'));
await fs.mkdir(output);
const {chromium, expect} = await import(pathToFileURL(options.get('--playwright')).href);
const hashes = [];
for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py', 'bridge.py', 'review.py']) {
  const core = !['bridge.py', 'review.py'].includes(name);
  const original = await fs.readFile(path.join(source, core ? 'ledgerly' : 'web-demo/python', name));
  const response = await fetch(new URL(`python/${core ? 'ledgerly/' : ''}${name}`, url));
  assert(response.ok);
  const served = Buffer.from(await response.arrayBuffer());
  assert.deepEqual(served, original, `Wrong served native source: ${name}`);
  hashes.push({name, bytes: served.length, sha256: createHash('sha256').update(served).digest('hex')});
}
const receipt = {started_utc: new Date().toISOString(), node: process.version,
  base_commit: '1b2b902d5dd412a8b61c9b9075b815c1d0029365',
  source_checks: hashes, groups: [], off_origin: [], page_errors: []};
const browser = await chromium.launch({executablePath: options.get('--chrome'), headless: true});
receipt.browser = browser.version();
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
await context.route('**/*', route => {
  if (new URL(route.request().url()).origin !== url.origin) {
    receipt.off_origin.push(route.request().url()); return route.abort();
  }
  return route.continue();
});
await context.addInitScript(() => {
  const OriginalWorker = window.Worker;
  window.__overdueReceiving = {requests: [], replies: []};
  window.Worker = class extends OriginalWorker {
    constructor(...args) {
      super(...args);
      this.addEventListener('message', event => {
        if (event.data?.data?.state) window.__overdueReceiving.replies.push(structuredClone(event.data.data));
      });
    }
    postMessage(message, ...transfer) {
      window.__overdueReceiving.requests.push(structuredClone(message));
      return super.postMessage(message, ...transfer);
    }
  };
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
page.on('pageerror', error => receipt.page_errors.push(String(error)));
const last = () => page.evaluate(() => window.__overdueReceiving.replies.at(-1));
async function action(selector) {
  const before = await page.evaluate(() => window.__overdueReceiving.replies.length);
  await page.locator(selector).click();
  await page.waitForFunction(count => window.__overdueReceiving.replies.length > count, before);
  await expect(page.locator('#analyze')).toBeEnabled();
  const reply = await last();
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.state.external_calls, 0);
  return reply;
}
function passed(name) { receipt.groups.push({name, passed: true}); console.log(JSON.stringify(receipt.groups.at(-1))); }

try {
  await page.goto(url.href);
  console.log(JSON.stringify({stage: 'Loading actual browser Python'}));
  await page.locator('#engine-start').click();
  await expect(page.locator('#engine-status')).toHaveText('PYTHON READY / OFFLINE', {timeout: 60000});
  await page.locator('#fixture-select').selectOption('01_simple_usd_hourly.txt');
  await page.locator('#load-fixture').click();
  await expect(page.locator('#status-message')).toContainText('Fictional input loaded.');
  const invoices = [];
  let sent;
  for (let index = 0; index < 13; index++) {
    await action('#analyze');
    const draft = await action('#draft');
    assert.equal(draft.result.unauthorized_send_blocked, true);
    assert.equal(draft.state.pending.length, 1);
    const pending = draft.state.pending[0];
    assert.equal(pending.kind, 'send_invoice');
    sent = await action(`[data-approve="${pending.id}"]`);
    invoices.push(pending.invoice_id);
    assert.equal(sent.state.ledger.length, index + 1);
  }
  assert.equal(new Set(invoices).size, 13);
  const nextDay = new Date(`${sent.state.ledger[0].due_on}T00:00:00Z`);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  await page.locator('#demo-date').fill(nextDay.toISOString().slice(0, 10));
  await action('#advance-clock');
  const scanned = await action('#run-chase');
  assert.deepEqual(scanned.state.pending.map(a => a.invoice_id), invoices);
  assert(scanned.state.pending.every(a => a.kind === 'send_reminder' && a.status === 'PENDING'));
  assert(scanned.state.ledger.every(e => e.reminders_sent === 0));
  assert.notEqual(scanned.result.final, 'step limit reached');
  await expect(page.locator('#approval-list .approval-card')).toHaveCount(13);
  await fs.writeFile(path.join(output, 'first-scan.json'), JSON.stringify(scanned, null, 2) + '\n');
  passed('Actual UI creates thirteen invoices and scans every overdue invoice without sending a reminder');

  const repeated = await action('#run-chase');
  assert.deepEqual(repeated.state.pending, scanned.state.pending);
  assert(repeated.state.ledger.every(e => e.reminders_sent === 0));
  passed('Repeated explicit scan preserves every queued action ID and exact payload');

  for (const queued of scanned.state.pending.slice(0, 11)) await action(`[data-approve="${queued.id}"]`);
  const cooled = await action('#run-chase');
  const tail = scanned.state.pending.slice(11);
  assert.deepEqual(cooled.state.pending, tail);
  assert(cooled.state.ledger.slice(0, 11).every(e => e.reminders_sent === 1));
  assert(cooled.state.ledger.slice(11).every(e => e.reminders_sent === 0));
  await expect(page.locator('#approval-list .approval-card')).toHaveCount(2);
  await page.locator('#approval-list').screenshot({path: path.join(output, 'last-two-reminders.png')});
  const approved = await action(`[data-approve="${tail[1].id}"]`);
  assert.deepEqual(approved.state.pending, [tail[0]]);
  assert.equal(approved.state.ledger.find(e => e.invoice_id === invoices[12]).reminders_sent, 1);
  assert.equal(approved.state.ledger.find(e => e.invoice_id === invoices[11]).reminders_sent, 0);
  const rejected = await action(`[data-reject="${tail[0].id}"]`);
  assert.deepEqual(rejected.state.pending, []);
  await expect(page.locator('#approval-list .approval-card')).toHaveCount(0);
  receipt.final_state = rejected.state;
  receipt.worker_actions = await page.evaluate(() => window.__overdueReceiving.requests.map(r => r.action));
  passed('Cooldown prefix and explicit approval/rejection preserve the last two action identities');
  assert.deepEqual(receipt.off_origin, []);
  assert.deepEqual(receipt.page_errors, []);
  receipt.passed = true;
} catch (error) {
  receipt.passed = false;
  receipt.error = String(error.stack || error);
  receipt.diagnostic_errors = [];
  for (const [name, capture] of [
    ['failure.html', async () => page.content()],
    ['failure-native-state.json', async () => JSON.stringify(await last(), null, 2)],
  ]) {
    try { await fs.writeFile(path.join(output, name), (await capture()) + '\n'); }
    catch (problem) { receipt.diagnostic_errors.push(String(problem)); }
  }
  process.exitCode = 1;
} finally {
  receipt.completed_utc = new Date().toISOString();
  await browser.close();
  await fs.writeFile(path.join(output, 'browser-receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({passed: receipt.passed, groups: receipt.groups.length, error: receipt.error}));
}
