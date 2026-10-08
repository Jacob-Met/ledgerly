#!/usr/bin/env node
/** Actual built page and Python Worker receiving, using Node 22 and installed Chrome. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn, execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir, mkdtemp, rm, readdir} from 'node:fs/promises';
import {dirname, extname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const project = resolve(option('--project', join(dirname(fileURLToPath(import.meta.url)), '../..')));
const build = resolve(option('--build', join(project, 'web-demo/dist')));
const output = resolve(option('--output', join(project, 'receivables-browser-receiving')));
const executable = option('--browser', 'google-chrome');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const pause = ms => new Promise(done => setTimeout(done, ms));
await mkdir(output);
const report = {schema:'ledgerly.receivables-browser/1', status:'running',
  claim:'https://github.com/Jacob-Met/ledgerly/issues/39', project, build, executable,
  node:process.version, workflowCheckout:process.env.GITHUB_SHA ?? null,
  checks:[], artifacts:[], requests:[], externalRequests:[], serverRequests:[],
  sourceSha256:{}, buildSha256:{}, sourceUnchanged:false,
  observer:'Copies real Worker calls and snapshots. Availability controls hold one real reply, corrupt one copied transport balance, and dispatch one authored terminal Worker error. Python execution is never replaced.',
  imageBoundary:'PNG files are actual Chrome captures. Generation alone does not establish direct visual inspection.'};
let browser, socket, server, profile, sessionId, sequence = 0, browserError, browserLog = '';
const pending = new Map(), pageErrors = [];
let tracked = [], sourceBefore = null;
const git = (...values) => execFileSync('git', values, {cwd:project, encoding:'utf8'}).trim();
async function sourceHashes() {
  const result = {};
  for (const path of tracked) result[path] = hash(await readFile(join(project, path)));
  return result;
}
async function buildHashes(directory, prefix = '') {
  const result = {};
  for (const entry of await readdir(directory, {withFileTypes:true})) {
    const name = prefix + entry.name;
    if (entry.isDirectory()) Object.assign(result, await buildHashes(join(directory, entry.name), name + '/'));
    else if (entry.isFile()) result[name] = hash(await readFile(join(directory, entry.name)));
    else throw new Error('Nonregular build artifact: ' + name);
  }
  return result;
}
async function waitFor(check, label, attempts = 600) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    if (browserError) throw browserError;
    try { if (await check()) return; } catch (error) { lastError = error; }
    await pause(100);
  }
  throw new Error('Timed out: ' + label + (lastError ? ' (' + lastError.message + ')' : ''));
}
function command(method, params = {}, scope = sessionId) {
  const id = ++sequence;
  return new Promise((done, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 15000);
    pending.set(id, {done, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(scope ? {sessionId:scope} : {})}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
async function key(value, code, number, modifiers = 0) {
  for (const type of ['keyDown', 'keyUp']) await command('Input.dispatchKeyEvent', {
    type, key:value, code, windowsVirtualKeyCode:number, nativeVirtualKeyCode:number, modifiers,
    ...(value === 'Enter' && type === 'keyDown' ? {text:'\r', unmodifiedText:'\r'} : {}),
  });
}
async function focus(selector) {
  assert.equal(await evaluate('(() => {const n=document.querySelector(' + JSON.stringify(selector) +
    ');if(!n||n.matches(":disabled")||!n.getClientRects().length)return false;' +
    'n.scrollIntoView({block:"center"});n.focus();return document.activeElement===n;})()'), true,
    'Available focusable control: ' + selector);
}
async function activate(selector) { await focus(selector); await key('Enter', 'Enter', 13); }
async function textInput(selector, value) {
  await focus(selector); await key('a', 'KeyA', 65, 2);
  if (value) await command('Input.insertText', {text:value}); else await key('Backspace', 'Backspace', 8);
  assert.equal(await evaluate('document.querySelector(' + JSON.stringify(selector) + ').value'), value);
}
async function choose(selector, value) {
  const index = await evaluate('[...document.querySelector(' + JSON.stringify(selector) +
    ').options].findIndex(n=>n.value===' + JSON.stringify(value) + ')');
  assert.ok(index >= 0, 'Existing native option: ' + value);
  await focus(selector); await key('Home', 'Home', 36);
  for (let i = 0; i < index; i++) await key('ArrowDown', 'ArrowDown', 40);
  await key('Tab', 'Tab', 9);
  assert.equal(await evaluate('document.querySelector(' + JSON.stringify(selector) + ').value'), value);
}
async function save(name, bytes, kind) {
  const data = Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
  assert.ok(data.length <= 2 * 1024 * 1024, 'Bounded artifact: ' + name);
  await writeFile(join(output, name), data);
  report.artifacts.push({name, bytes:data.length, sha256:hash(data), kind});
}
async function screenshot(name) {
  const box = await evaluate('(() => {const n=document.querySelector("#receivables-view");' +
    'n.scrollIntoView({block:"start"});const r=n.getBoundingClientRect();' +
    'return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1};})()');
  const {data} = await command('Page.captureScreenshot', {format:'png', clip:box, captureBeyondViewport:true});
  await save(name, Buffer.from(data, 'base64'), 'actual Chrome capture');
}
const passed = name => { report.checks.push(name); console.log('PASS ' + name); };
const OBSERVER = '(() => {' +
  'const NativeWorker=window.Worker;' +
  'const p=window.__receivablesProbe={calls:[],states:[],workers:[],holdNext:false,held:null,corruptNext:false};' +
  'window.Worker=class extends NativeWorker{constructor(...args){super(...args);p.workers.push(this);' +
  'this.addEventListener("message",event=>{if(event.data?.data?.state){' +
  'if(p.holdNext){p.holdNext=false;event.stopImmediatePropagation();p.held={worker:this,data:event.data};return;}' +
  'if(p.corruptNext){p.corruptNext=false;event.stopImmediatePropagation();' +
  'const bad=structuredClone(event.data);bad.data.state.ledger[0].balance="NaN";' +
  'queueMicrotask(()=>this.dispatchEvent(new MessageEvent("message",{data:bad})));return;}' +
  'p.states.push(structuredClone(event.data.data.state));}});}' +
  'postMessage(...args){p.calls.push(structuredClone(args[0]));return super.postMessage(...args);}};' +
  'p.release=()=>{const h=p.held;p.held=null;if(h)h.worker.dispatchEvent(new MessageEvent("message",{data:h.data}));};' +
  '})();';
const state = () => evaluate('window.__receivablesProbe.states.at(-1)');
const calls = () => evaluate('window.__receivablesProbe.calls');
async function action(selector) {
  const count = await evaluate('window.__receivablesProbe.states.length');
  await activate(selector);
  await waitFor(() => evaluate('window.__receivablesProbe.states.length>' + count +
    ' && !document.querySelector("#analyze").disabled'), 'real Python action ' + selector);
  return state();
}
async function board() {
  return evaluate('(() => {const r=document.querySelector("#receivables-view");return {' +
    'state:r.dataset.state,note:document.querySelector("#receivables-note").textContent,' +
    'summary:[...document.querySelectorAll("#receivables-summary .receivables-amount")].map(n=>({' +
    'currency:n.querySelector("span").textContent,balance:n.querySelector("strong").textContent})),' +
    'clients:[...document.querySelectorAll("#receivables-list article")].map(n=>({' +
    'name:n.querySelector("h3").textContent,email:n.querySelector("header p").textContent,' +
    'amounts:[...n.querySelectorAll(".receivables-amount")].map(m=>({' +
    'currency:m.querySelector("span").textContent,balance:m.querySelector("strong").textContent})),' +
    'invoices:[...n.querySelectorAll(".receivables-invoices li")].map(m=>({' +
    'number:m.querySelector("strong").textContent,balance:m.querySelector(".receivables-invoice-balance").textContent,' +
    'dueState:m.dataset.dueState,text:m.textContent}))})),' +
    'disabled:[...r.querySelectorAll("select,button")].map(n=>n.disabled),' +
    'listText:document.querySelector("#receivables-list").textContent};})()');
}
async function originalPanels() {
  return evaluate('({ledger:document.querySelector("#ledger-list").innerHTML,' +
    'pending:document.querySelector("#approval-list").innerHTML,audit:document.querySelector("#audit-list").innerHTML,' +
    'mock:document.querySelector("#mock-requests").textContent,external:document.querySelector("#external-calls").textContent,' +
    'input:document.querySelector("#job-email").value})');
}
const amountList = values => values.map(([currency, balance]) => ({currency, balance}));
async function draft({email, name, currency, amount, terms, approved = true, correctedName}) {
  const before = new Set((await state()).ledger.map(row => row.invoice_id));
  await textInput('#job-email', 'From: ' + name + ' <' + email + '>\n\n- 1 x Design work @ ' +
    currency + ' ' + amount + '\nNet ' + terms + '\n');
  await action('#analyze');
  if (correctedName) {
    await activate('#review-editor > summary');
    await textInput('#review-client-name', correctedName);
    await focus('#review-confirm'); await key(' ', 'Space', 32);
    await action('#review-check');
  }
  const drafted = await action('#draft');
  const fresh = drafted.ledger.filter(row => !before.has(row.invoice_id));
  assert.equal(fresh.length, 1);
  const entry = fresh[0];
  assert.equal(entry.currency, currency); assert.equal(entry.client_email, email); assert.equal(entry.status, 'DRAFT');
  if (approved) {
    const pendingSend = drafted.pending.find(row => row.invoice_id === entry.invoice_id && row.kind === 'send_invoice');
    assert.ok(pendingSend);
    const accepted = await action('#approval-list button[data-approve="' + pendingSend.id + '"]');
    assert.equal(accepted.ledger.find(row => row.invoice_id === entry.invoice_id).status, 'SENT');
  }
  return entry.invoice_id;
}
async function bundle() {
  if (!args.includes('--emit-bundle')) return;
  const names = [...report.artifacts.map(item => item.name), 'receiving-report.json'].sort();
  const files = []; let bytes = 0;
  for (const name of names) {
    const data = await readFile(join(output, name));
    const expected = report.artifacts.find(item => item.name === name);
    if (expected) { assert.equal(data.length, expected.bytes); assert.equal(hash(data), expected.sha256); }
    bytes += data.length;
    assert.ok(bytes <= 2 * 1024 * 1024, 'Receiving packet exceeds 2 MiB; refusing to truncate it.');
    files.push({path:name, bytes:data.length, sha256:hash(data), base64:data.toString('base64')});
  }
  const data = Buffer.from(JSON.stringify({version:1, files}));
  const encoded = data.toString('base64'), chunks = Math.ceil(encoded.length / 4096);
  console.log('LEDGERLY_RECEIVABLES_BUNDLE_BEGIN ' + JSON.stringify({bytes:data.length, sha256:hash(data), chunks}));
  for (let i = 0; i < chunks; i++) console.log('LEDGERLY_RECEIVABLES_BUNDLE_CHUNK ' + i + ' ' + encoded.slice(i * 4096, (i + 1) * 4096));
  console.log('LEDGERLY_RECEIVABLES_BUNDLE_END');
}

try {
  assert.equal(typeof WebSocket, 'function', 'Node built-in WebSocket is required.');
  report.browserExecutableVersion = execFileSync(executable, ['--version'], {encoding:'utf8'}).trim();
  report.checkout = {commit:git('rev-parse', 'HEAD'), tree:git('rev-parse', 'HEAD^{tree}')};
  tracked = execFileSync('git', ['ls-files', '-z', '--', 'ledgerly', 'web-demo/src', 'web-demo/python',
    'web-demo/scripts', 'web-demo/tests', 'web-demo/index.html', 'web-demo/package.json',
    'web-demo/package-lock.json', 'web-demo/tsconfig.json', 'web-demo/vite.config.ts',
    'web-demo/tools/check_receivables_browser.mjs', '.github/workflows/receivables-browser.yml'],
    {cwd:project, encoding:'utf8'}).split('\0').filter(Boolean).sort();
  assert.ok(tracked.includes('web-demo/src/receivables.ts'));
  sourceBefore = await sourceHashes(); report.sourceSha256 = sourceBefore;
  report.buildSha256 = await buildHashes(build);
  for (const [path, digest] of Object.entries(report.buildSha256)) if (path.startsWith('python/')) {
    const native = path.startsWith('python/ledgerly/') ? path.slice(7) : 'web-demo/' + path;
    assert.equal(hash(await readFile(join(project, native))), digest, 'Build stages exact Python bytes: ' + native);
  }
  profile = await mkdtemp(join(output, 'chrome-'));
  server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      report.serverRequests.push({method:request.method, path:pathname});
      if (request.method !== 'GET') { response.writeHead(405).end(); return; }
      const filename = resolve(build, pathname === '/' ? 'index.html' : '.' + pathname);
      if (!filename.startsWith(build + sep)) { response.writeHead(403).end(); return; }
      const data = await readFile(filename);
      const mime = {'.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript',
        '.css':'text/css', '.json':'application/json', '.wasm':'application/wasm',
        '.svg':'image/svg+xml', '.zip':'application/zip'}[extname(filename)] || 'application/octet-stream';
      response.writeHead(200, {'Content-Type':mime, 'Cache-Control':'no-store'}).end(data);
    } catch { response.writeHead(404).end('Missing build file.'); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  const base = 'http://127.0.0.1:' + server.address().port;
  browser = spawn(executable, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
    '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-default-apps',
    '--disable-features=Translate,MediaRouter,OptimizationHints', '--metrics-recording-only',
    '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'], {stdio:['ignore','ignore','pipe']});
  browser.stderr.on('data', chunk => { browserLog = (browserLog + chunk.toString()).slice(-24000); });
  browser.on('error', error => { browserError = error; });
  let active;
  await waitFor(async () => {
    active = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).trim().split('\n');
    return active.length === 2;
  }, 'installed Chrome');
  socket = new WebSocket('ws://127.0.0.1:' + active[0] + active[1]);
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const job = pending.get(message.id); if (!job) return;
      pending.delete(message.id); clearTimeout(job.timer);
      if (message.error) job.reject(new Error(message.error.message)); else job.done(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      pageErrors.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
    } else if (message.method === 'Fetch.requestPaused') {
      const request = message.params.request;
      const allowed = request.method === 'GET' && new URL(request.url).origin === base;
      if (!allowed) report.externalRequests.push({url:request.url, method:request.method});
      void command(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest', {
        requestId:message.params.requestId, ...(!allowed ? {errorReason:'BlockedByClient'} : {}),
      }, message.sessionId).catch(error => pageErrors.push(error.message));
    } else if (message.method === 'Network.requestWillBeSent') {
      report.requests.push({url:message.params.request.url, method:message.params.request.method});
    } else if (message.method === 'Page.javascriptDialogOpening') {
      void command('Page.handleJavaScriptDialog', {accept:true}, message.sessionId).catch(error => pageErrors.push(error.message));
    }
  });
  await new Promise((done, reject) => {
    socket.addEventListener('open', done, {once:true}); socket.addEventListener('error', reject, {once:true});
  });
  report.browser = await command('Browser.getVersion', {}, null);
  const {targetId} = await command('Target.createTarget', {url:'about:blank'}, null);
  ({sessionId} = await command('Target.attachToTarget', {targetId, flatten:true}, null));
  await command('Page.enable'); await command('Runtime.enable'); await command('Network.enable');
  await command('Fetch.enable', {patterns:[{urlPattern:'http*'}]});
  await command('Page.addScriptToEvaluateOnNewDocument', {source:OBSERVER});
  await command('Emulation.setDeviceMetricsOverride', {width:1280, height:1000, deviceScaleFactor:1, mobile:false});
  await command('Page.navigate', {url:base + '/'});
  await waitFor(() => evaluate('document.readyState==="complete" && !!document.querySelector("#receivables-view")'), 'built board');
  assert.equal((await board()).state, 'unavailable');
  assert.deepEqual((await board()).disabled, [true, true, true]);
  const empty = await action('#engine-start');
  assert.deepEqual(empty.ledger, []); assert.equal(empty.external_calls, 0);
  assert.equal((await board()).state, 'empty');
  passed('actual Python startup exposes an empty board only after the accepted snapshot');

  const north = {email:'north@example.test', name:'North Studio'};
  const south = {email:'south@example.test', name:'South Studio'};
  const first = await draft({...north, currency:'USD', amount:'0.10', terms:1});
  const second = await draft({...north, currency:'USD', amount:'0.20', terms:7});
  const literal = 'North <img src=x onerror=window.boardExecuted=1> & "Studio"';
  const euro = await draft({...north, currency:'EUR', amount:'12.30', terms:14, correctedName:literal});
  const partial = await draft({...south, currency:'USD', amount:'120.75', terms:1});
  await textInput('#payment-amount', '20.25');
  await action('#ledger-list button[data-pay="' + partial + '"]');
  const paid = await draft({...south, currency:'USD', amount:'20.00', terms:1});
  await textInput('#payment-amount', '');
  await action('#ledger-list button[data-pay="' + paid + '"]');
  const draftOnly = await draft({...north, currency:'GBP', amount:'9.99', terms:1, approved:false});
  const current = await state();
  const clock = new Date(current.today + 'T00:00:00Z'); clock.setUTCDate(clock.getUTCDate() + 7);
  const day = clock.toISOString().slice(0, 10);
  await evaluate('(() => {const n=document.querySelector("#demo-date");n.value=' + JSON.stringify(day) +
    ';n.dispatchEvent(new Event("input",{bubbles:true}));n.dispatchEvent(new Event("change",{bubbles:true}));})()');
  const accepted = await action('#advance-clock');
  assert.equal(accepted.today, day); assert.equal(accepted.ledger.length, 6);
  assert.equal(accepted.ledger.find(row => row.invoice_id === partial).balance, '100.50');
  assert.equal(accepted.ledger.find(row => row.invoice_id === partial).status, 'PARTIALLY_PAID');
  assert.equal(accepted.ledger.find(row => row.invoice_id === paid).status, 'PAID');
  assert.equal(accepted.ledger.find(row => row.invoice_id === draftOnly).status, 'DRAFT');
  const all = await board();
  assert.equal(all.state, 'ready'); assert.equal(all.clients.length, 2);
  assert.deepEqual(all.summary, amountList([['EUR','12.3'],['USD','100.80']]));
  assert.deepEqual(all.clients.find(client => client.email === north.email).amounts, amountList([['EUR','12.3'],['USD','0.3']]));
  assert.deepEqual(all.clients.find(client => client.email === south.email).amounts, amountList([['USD','100.50']]));
  assert.ok(all.clients.find(client => client.email === north.email).name.includes(literal));
  assert.deepEqual(all.clients.flatMap(client => client.invoices).map(row => row.dueState).sort(), ['later','overdue','overdue','today']);
  assert.match(all.note, /1 DRAFT/); assert.match(all.note, /1 PAID/); assert.ok(all.note.includes(day));
  assert.equal(await evaluate('document.querySelectorAll("#receivables-view img,#receivables-view script,#receivables-view [onerror]").length'), 0);
  assert.equal(await evaluate('window.boardExecuted ?? null'), null);
  report.nativeInvoiceIds = {first, second, euro, partial, paid, draftOnly};
  await save('accepted-native-snapshot.json', JSON.stringify(accepted, null, 2) + '\n', 'real Python Worker snapshot');
  await save('all-balances.json', JSON.stringify(all, null, 2) + '\n', 'actual board DOM projection');
  await screenshot('desktop-client-balances.png');
  passed('actual draft, approval, partial/full payment and clock changes produce exact per-client currency totals and literal names');

  const beforeCalls = await calls(), beforeState = await state(), panels = await originalPanels();
  const beforeRequests = report.requests.length;
  const clientIndex = await evaluate('[...document.querySelector("#receivables-client").options].find(n=>n.textContent==="north@example.test").value');
  await choose('#receivables-client', clientIndex);
  await choose('#receivables-due', 'overdue');
  const filtered = await board();
  assert.equal(filtered.clients.length, 1); assert.equal(filtered.clients[0].email, north.email);
  assert.equal(filtered.clients[0].invoices.length, 1);
  assert.deepEqual(filtered.summary, amountList([['USD','0.1']]));
  assert.ok(filtered.clients[0].invoices[0].text.includes(first));
  await choose('#receivables-due', 'undated');
  assert.deepEqual((await board()).summary, []); assert.deepEqual((await board()).clients, []);
  assert.match((await board()).listText, /No outstanding invoices match/);
  await activate('#receivables-reset');
  assert.deepEqual((await board()).summary, all.summary);
  assert.deepEqual(await calls(), beforeCalls); assert.deepEqual(await state(), beforeState);
  assert.deepEqual(await originalPanels(), panels);
  assert.equal(report.requests.length, beforeRequests);
  passed('native keyboard client/due filters and reset change only the board, with no Worker call, request or ledger mutation');

  await command('Emulation.setDeviceMetricsOverride', {width:390, height:844, deviceScaleFactor:1, mobile:false});
  await focus('#receivables-client'); await key('Tab', 'Tab', 9);
  assert.equal(await evaluate('document.activeElement.id'), 'receivables-due');
  await key('Tab', 'Tab', 9); assert.equal(await evaluate('document.activeElement.id'), 'receivables-reset');
  const layout = await evaluate('(() => {const n=document.querySelector("#receivables-view");' +
    'const r=n.getBoundingClientRect();return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,' +
    'left:r.left,right:r.right,scrollWidth:n.scrollWidth,clientWidth:n.clientWidth,' +
    'overflow:[...n.querySelectorAll("*")].filter(e=>e.getClientRects().length&&e.getBoundingClientRect().right>innerWidth+1)' +
    '.map(e=>({tag:e.tagName,id:e.id,text:e.textContent.slice(0,80)}))};})()');
  assert.ok(layout.documentWidth <= layout.width + 1, 'No horizontal page overflow at 390px');
  assert.ok(layout.left >= -1 && layout.right <= layout.width + 1, 'Board fits the viewport');
  assert.ok(layout.scrollWidth <= layout.clientWidth + 1, 'Board content fits its container');
  assert.deepEqual(layout.overflow, []);
  report.narrowLayout = layout;
  await screenshot('narrow-client-balances.png');
  passed('390px board wraps actual amounts and literal names, with sequential keyboard focus and no horizontal overflow');

  await evaluate('window.__receivablesProbe.holdNext=true');
  await activate('#analyze');
  await waitFor(() => evaluate('!!window.__receivablesProbe.held'), 'held real Worker reply');
  const held = await board();
  assert.equal(held.state, 'busy'); assert.deepEqual(held.summary, []); assert.deepEqual(held.clients, []);
  assert.deepEqual(held.disabled, [true,true,true]);
  await evaluate('window.__receivablesProbe.release()');
  await waitFor(() => evaluate('!document.querySelector("#analyze").disabled'), 'real reply delivered');
  assert.deepEqual((await board()).summary, all.summary);
  await evaluate('window.__receivablesProbe.corruptNext=true');
  await action('#analyze');
  const invalid = await board();
  assert.equal(invalid.state, 'invalid'); assert.deepEqual(invalid.summary, []); assert.deepEqual(invalid.clients, []);
  assert.deepEqual(invalid.disabled, [true,true,true]); assert.match(invalid.note, /Invalid native balance/);
  await action('#analyze');
  assert.deepEqual((await board()).summary, all.summary);
  passed('a held real action hides old balances; an authored malformed transport snapshot refuses complete totals and the next valid reply restores them');

  const beforeFailure = await calls();
  await evaluate('window.__receivablesProbe.workers.at(-1).dispatchEvent(new ErrorEvent("error",{message:"authored terminal Worker failure"}))');
  await waitFor(() => evaluate('document.querySelector("#engine-status").textContent==="PYTHON UNAVAILABLE"'), 'session unavailable');
  assert.equal((await board()).state, 'unavailable');
  assert.deepEqual((await board()).summary, []); assert.deepEqual((await board()).clients, []);
  assert.deepEqual((await board()).disabled, [true,true,true]); assert.deepEqual(await calls(), beforeFailure);
  const restarted = await action('#engine-start');
  assert.deepEqual(restarted.ledger, []); assert.equal((await board()).state, 'empty');
  await draft({...south, currency:'USD', amount:'1.23', terms:7});
  assert.deepEqual((await board()).summary, amountList([['USD','1.23']]));
  const reset = await action('#reset-sandbox');
  assert.deepEqual(reset.ledger, []); assert.equal((await board()).state, 'empty');
  assert.deepEqual((await board()).summary, []); assert.deepEqual((await board()).clients, []);
  assert.deepEqual((await board()).disabled, [true,true,true]);
  passed('terminal session loss clears accepted balances; explicit restart and populated sandbox reset cannot revive old clients');

  assert.deepEqual(report.externalRequests, []); assert.deepEqual(pageErrors, []);
  assert.ok(report.serverRequests.every(request => request.method === 'GET'));
  report.workerCalls = await calls(); report.finalState = await state();
  assert.equal(report.finalState.external_calls, 0);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = error.stack ?? String(error); report.browserLog = browserLog;
  if (sessionId) {
    try { report.lastPage = await evaluate('({focus:document.activeElement?.id,text:document.body.innerText.slice(0,12000)})'); await screenshot('failed-state.png'); }
    catch (captureError) { report.captureError = String(captureError); }
  }
  console.error(report.error); process.exitCode = 1;
} finally {
  if (socket?.readyState === 1) { try { await command('Browser.close', {}, null); } catch {} }
  socket?.close(); for (const job of pending.values()) clearTimeout(job.timer);
  if (browser && browser.exitCode === null) browser.kill('SIGTERM');
  if (server) { server.closeAllConnections(); await new Promise(done => server.close(done)); }
  if (profile) { await pause(200); await rm(profile, {recursive:true, force:true}); }
  if (sourceBefore) {
    report.sourceUnchanged = JSON.stringify(await sourceHashes()) === JSON.stringify(sourceBefore);
    if (!report.sourceUnchanged) { report.status = 'failed'; process.exitCode = 1; }
  }
  report.pageErrors = pageErrors;
  await writeFile(join(output, 'receiving-report.json'), JSON.stringify(report, null, 2) + '\n');
  try { await bundle(); }
  catch (error) {
    report.status = 'failed'; report.bundleError = String(error); process.exitCode = 1;
    await writeFile(join(output, 'receiving-report.json'), JSON.stringify(report, null, 2) + '\n');
    console.error(error);
  }
  console.log(JSON.stringify({status:report.status, checks:report.checks.length,
    sourceUnchanged:report.sourceUnchanged, receipt:join(output, 'receiving-report.json')}));
}

