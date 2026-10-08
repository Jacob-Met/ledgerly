import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';

// Independent receiving checks against the actual built page and local Python.
// Failure injection is restricted to this disposable loopback fixture server.
const require = createRequire(import.meta.url);
const puppeteer = require(process.env.PUPPETEER_MODULE || '/Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer-core');
const [distArg, outputArg, expectation = 'candidate'] = process.argv.slice(2);
if (!distArg || !outputArg || !['baseline', 'candidate'].includes(expectation)) {
  throw new Error('Usage: node recovery-browser.mjs DIST OUTPUT baseline|candidate');
}
const dist = path.resolve(distArg), output = path.resolve(outputArg);
const selectedCase = process.env.RECOVERY_CASE || 'all';
const names = ['source-load-retry', 'fatal-startup-recovery', 'refused-initialization', 'in-flight-session-recovery', 'retained-review-recovery'];
if (selectedCase !== 'all' && !names.includes(selectedCase)) throw new Error('Unknown RECOVERY_CASE');
const enabled = name => selectedCase === 'all' || selectedCase === name;
fs.mkdirSync(output, { recursive: true });
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const workerName = fs.readdirSync(path.join(dist, 'assets')).find(x => /^engine\.worker-.*\.js$/.test(x));
if (!workerName) throw new Error('Built worker entry missing');
let mode = '', entries = 0, sourceAttempts = 0;
const requests = [], cases = [];
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  requests.push({ mode, path: pathname });
  if (pathname === '/python/ledgerly/agent.py') {
    sourceAttempts++;
    if (mode === 'retry-source' && sourceAttempts === 1) {
      res.writeHead(503, { 'content-type': 'text/plain', 'cache-control': 'no-store' });
      res.end('Injected single local source availability failure');
      return;
    }
  }
  const file = path.resolve(dist, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(dist + path.sep)) { res.writeHead(403); res.end(); return; }
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); res.end(); return; }
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.py': 'text/plain', '.txt': 'text/plain' };
  res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
  if (path.basename(file) === workerName) {
    entries++;
    let prefix = '';
    if (entries === 1 && mode === 'fatal-init') {
      prefix = `self.addEventListener('message',e=>{if(e.data.action==='init'){e.stopImmediatePropagation();throw new Error('Injected actual worker startup exception');}});\n`;
    } else if (entries === 1 && mode === 'fatal-action') {
      prefix = `let __receivingAnalyzes=0;self.addEventListener('message',e=>{if(e.data.action==='analyze'&&++__receivingAnalyzes===2){e.stopImmediatePropagation();throw new Error('Injected actual in-flight worker exception');}});\n`;
    } else if (entries === 1 && mode === 'fatal-review') {
      prefix = 'self.addEventListener("message",e=>{if(e.data.action==="advance"){e.stopImmediatePropagation();throw new Error("Injected actual in-flight worker exception");}});';
    } else if (mode === 'refused-init') {
      prefix = `self.addEventListener('message',e=>{if(e.data.action==='init'){e.stopImmediatePropagation();self.postMessage({id:e.data.id,ok:true,data:{ok:false,message:'Injected sandbox initialization refusal'}});}});\n`;
    }
    res.end(prefix + fs.readFileSync(file, 'utf8'));
  } else fs.createReadStream(file).pipe(res);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true, args: ['--no-first-run', '--no-default-browser-check', '--disable-background-networking'],
});
const browserVersion = await browser.version();
async function pageFor(nextMode) {
  mode = nextMode; entries = 0; sourceAttempts = 0;
  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  await page.setViewport({ width: 1360, height: 1000 });
  const errors = [], offOrigin = [], consoleMessages = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => consoleMessages.push(message.text()));
  page.on('request', request => {
    const u = new URL(request.url());
    if (!['data:', 'blob:'].includes(u.protocol) && u.origin !== origin) offOrigin.push(request.url());
  });
  await page.evaluateOnNewDocument(() => {
    const NativeWorker = window.Worker;
    window.__receivingWorkers = []; window.__receivingMessages = [];
    window.Worker = class extends NativeWorker {
      constructor(...args) { super(...args); this.receivingGeneration = window.__receivingWorkers.length; window.__receivingWorkers.push(this); }
      postMessage(message, ...rest) {
        window.__receivingMessages.push({ generation: this.receivingGeneration, id: message.id, action: message.action });
        return super.postMessage(message, ...rest);
      }
    };
  });
  await page.goto(origin, { waitUntil: 'networkidle0', timeout: 30000 });
  return { context, page, errors, offOrigin, consoleMessages };
}
async function wait(page, expression, timeout = 10000) {
  try { await page.waitForFunction(expression, { timeout }); return true; }
  catch (error) { if (error.name === 'TimeoutError') return false; throw error; }
}
const ready = `document.querySelector('#engine-status').textContent==='PYTHON READY / OFFLINE'`;
const retryable = `!document.querySelector('#engine-start').disabled`;
const errorStatus = `document.querySelector('#status-message').dataset.kind==='error'`;
async function snapshot(page) {
  return page.evaluate(() => ({
    status: document.querySelector('#status-message').textContent,
    engine: document.querySelector('#engine-status').textContent,
    restartEnabled: !document.querySelector('#engine-start').disabled,
    analyzeEnabled: !document.querySelector('#analyze').disabled,
    email: document.querySelector('#job-email').value,
    analysis: document.querySelector('#analysis').textContent,
    invoices: document.querySelectorAll('#ledger-list .invoice-card').length,
    activeLedgerButtons: [...document.querySelectorAll('#ledger-list button,#approval-list button')].filter(b => !b.disabled).length,
    externalCalls: document.querySelector('#external-calls').textContent,
    messages: window.__receivingMessages,
    generations: window.__receivingWorkers.length,
  }));
}
async function finish(test, name, result) {
  const state = await snapshot(test.page);
  const receipt = { name, ...result, sourceAttempts, workerEntries: entries, state, offOrigin: test.offOrigin, pageErrors: test.errors, consoleMessages: test.consoleMessages, requests: requests.filter(r => r.mode === mode) };
  cases.push(receipt);
  await test.page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
  console.log(JSON.stringify({ name, passed: receipt.passed, sourceAttempts, workerEntries: entries, state }));
  await test.context.close();
}
try {
  if (enabled('source-load-retry')) {
    const test = await pageFor('retry-source');
    await test.page.click('#engine-start');
    const firstFailure = await wait(test.page, errorStatus, 30000);
    const firstRetryable = await wait(test.page, retryable, 2000);
    if (firstRetryable) await test.page.click('#engine-start');
    const recovered = await wait(test.page, ready, 15000);
    await finish(test, 'source-load-retry', { passed: firstFailure && firstRetryable && recovered && sourceAttempts === 2, firstFailure, firstRetryable, recovered });
  }
  if (enabled('fatal-startup-recovery')) {
    const test = await pageFor('fatal-init');
    await test.page.click('#engine-start');
    const failed = await wait(test.page, errorStatus, 3000);
    const settled = await wait(test.page, retryable, 2000);
    if (settled) await test.page.click('#engine-start');
    const recovered = settled && await wait(test.page, ready, 30000);
    await finish(test, 'fatal-startup-recovery', { passed: failed && settled && recovered && entries === 2, failed, settled, recovered });
  }
  if (enabled('refused-initialization')) {
    const test = await pageFor('refused-init');
    await test.page.click('#engine-start');
    await wait(test.page, `document.querySelector('#status-message').textContent.includes('refusal')||${ready}`, 3000);
    const state = await snapshot(test.page);
    await finish(test, 'refused-initialization', { passed: state.restartEnabled && !state.analyzeEnabled && state.engine !== 'PYTHON READY / OFFLINE' && state.status.includes('refusal') });
  }
  if (enabled('in-flight-session-recovery')) {
    const test = await pageFor('fatal-action');
    await test.page.click('#engine-start');
    if (!await wait(test.page, ready, 30000)) throw new Error('Actual Python baseline could not initialize');
    await test.page.click('#load-fixture');
    if (!await wait(test.page, `document.querySelector('#job-email').value.length>10`, 5000)) throw new Error('Fixture missing');
    await test.page.click('#analyze');
    if (!await wait(test.page, `!document.querySelector('#draft').disabled`, 15000)) throw new Error('Actual extraction did not offer draft');
    await test.page.click('#draft');
    if (!await wait(test.page, `document.querySelectorAll('#approval-list button[data-approve]').length===1`, 15000)) throw new Error('Actual sandbox draft missing');
    await test.page.click('#approval-list button[data-approve]');
    if (!await wait(test.page, `document.querySelector('#ledger-list .status-chip')?.textContent==='SENT'`, 15000)) throw new Error('Actual sandbox approval failed');
    const typed = 'Fictional retained source\nFrom: Review <billing@example.test>\n2 hours of analysis at $100/hr\nNet 15';
    await test.page.$eval('#job-email', (el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }, typed);
    await test.page.click('#analyze');
    const failed = await wait(test.page, errorStatus, 3000);
    const settled = await wait(test.page, retryable, 2000);
    const failedState = await snapshot(test.page);
    const retainedBefore = failedState.email === typed;
    const staleActionsDisabled = !failedState.analyzeEnabled && failedState.activeLedgerButtons === 0;
    if (settled) await test.page.click('#engine-start');
    const recovered = settled && await wait(test.page, ready, 30000);
    let retainedAfter = false, emptyAfter = false, noReplay = false, staleErrorIgnored = false, analysisCurrent = false;
    if (recovered) {
      const state = await snapshot(test.page);
      retainedAfter = state.email === typed; emptyAfter = state.invoices === 0;
      analysisCurrent = !/session is unavailable|Restart, then/.test(state.analysis);
      noReplay = state.messages.filter(m => m.generation === 1).every(m => m.action === 'init');
      await test.page.evaluate(() => window.__receivingWorkers[0].dispatchEvent(new ErrorEvent('error', { message: 'Injected late error from discarded worker' })));
      staleErrorIgnored = await test.page.evaluate(() => document.querySelector('#engine-status').textContent === 'PYTHON READY / OFFLINE' && !document.querySelector('#analyze').disabled);
    }
    await finish(test, 'in-flight-session-recovery', { passed: failed && settled && recovered && retainedBefore && retainedAfter && staleActionsDisabled && emptyAfter && noReplay && staleErrorIgnored && analysisCurrent,
      failed, settled, recovered, retainedBefore, retainedAfter, staleActionsDisabled, emptyAfter, noReplay, staleErrorIgnored, analysisCurrent, failedState });
  }
  if (selectedCase === 'retained-review-recovery') {
    const test = await pageFor('fatal-review'), page = test.page;
    await page.click('#engine-start');
    if (!await wait(page, ready, 30000)) throw new Error('Review receiver could not initialize actual Python');
    await page.select('#fixture-select', '05_missing_email.txt');
    await page.click('#load-fixture');
    if (!await wait(page, "document.querySelector('#job-email').value.length>10", 5000)) throw new Error('Review fixture missing');
    await page.click('#analyze');
    if (!await wait(page, "!!document.querySelector('#review-form')", 15000)) throw new Error('Review form missing');
    await page.click('#review-editor summary');
    for (const [selector, value] of [
      ['#review-client-email', 'billing@example.test'],
      ['#review-client-name', 'Fictional retained <review> & client'],
      ['#review-due-days', '0'],
    ]) await page.$eval(selector, (el, text) => { el.value = text; el.dispatchEvent(new Event('input', { bubbles: true })); }, value);
    const fields = () => page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#review-form input:not([type=checkbox]),#review-form select')].map(el => [el.id, el.value])));
    const expectedFields = await fields();
    await page.click('#review-confirm');
    await page.click('#review-check');
    if (!await wait(page, "!document.querySelector('#draft').disabled", 15000)) throw new Error('First actual review did not validate');
    await page.click('#advance-clock');
    const failed = await wait(page, errorStatus, 5000);
    const settled = await wait(page, retryable, 3000);
    const preservedAtFailure = JSON.stringify(await fields()) === JSON.stringify(expectedFields);
    const invalidatedAtFailure = await page.evaluate(() => document.querySelector('#draft').disabled && !document.querySelector('#review-confirm')?.checked);
    if (settled) await page.click('#engine-start');
    const recovered = settled && await wait(page, ready, 30000);
    const preservedAfterRestart = JSON.stringify(await fields()) === JSON.stringify(expectedFields);
    const noReplayBeforeCheck = await page.evaluate(() => window.__receivingMessages.filter(m => m.generation === 1).every(m => m.action === 'init'));
    const stillNeedsReview = await page.evaluate(() => document.querySelector('#draft').disabled && !document.querySelector('#review-confirm')?.checked);
    let freshReview = false, draftCount = 0, separateApproval = false, preservedAfterCheck = false;
    if (recovered && preservedAfterRestart && stillNeedsReview) {
      await page.click('#review-confirm');
      await page.click('#review-check');
      freshReview = await wait(page, "!document.querySelector('#draft').disabled", 15000);
      preservedAfterCheck = JSON.stringify(await fields()) === JSON.stringify(expectedFields);
      const actions = await page.evaluate(() => window.__receivingMessages.filter(m => m.generation === 1).map(m => m.action));
      freshReview = freshReview && JSON.stringify(actions) === JSON.stringify(['init', 'analyze', 'review']);
      if (freshReview) {
        await page.click('#draft');
        if (!await wait(page, "document.querySelectorAll('#approval-list button[data-approve]').length===1", 15000)) throw new Error('Revalidated draft missing');
        draftCount = await page.$eval('#ledger-list .invoice-card', els => els.length);
        separateApproval = await page.$eval('#ledger-list .status-chip', el => el.textContent === 'DRAFT');
        await page.click('#approval-list button[data-approve]');
        separateApproval = separateApproval && await wait(page, "document.querySelector('#ledger-list .status-chip')?.textContent==='SENT'", 15000);
      }
    }
    await finish(test, 'retained-review-recovery', {
      passed: failed && settled && recovered && preservedAtFailure && invalidatedAtFailure && preservedAfterRestart && noReplayBeforeCheck && stillNeedsReview && freshReview && preservedAfterCheck && draftCount === 1 && separateApproval,
      failed, settled, recovered, preservedAtFailure, invalidatedAtFailure, preservedAfterRestart, noReplayBeforeCheck, stillNeedsReview, freshReview, preservedAfterCheck, draftCount, separateApproval,
    });
  }

} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
  const result = { expectation, selectedCase, browserVersion, dist, workerEntry: workerName, workerSha256: hash(path.join(dist, 'assets', workerName)), scriptSha256: hash(new URL(import.meta.url)), cases,
    allPassed: cases.length === (selectedCase === 'all' ? 4 : 1) && cases.every(c => c.passed && c.offOrigin.length === 0 && c.pageErrors.every(error => /Injected actual (worker startup|in-flight worker) exception/.test(error))) };
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ output, allPassed: result.allPassed, cases: cases.length }));
  if (expectation === 'candidate' && !result.allPassed) process.exitCode = 1;
}