#!/usr/bin/env node
/** Real Python Worker -> explicit invoice HTML download -> offline/print receiving.
 * Node 22 and installed system Chrome; no extra package or browser installation.
 */
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {spawn} from "node:child_process";
import {createServer} from "node:http";
import {readFile, writeFile, mkdir, mkdtemp, rm, readdir, lstat} from "node:fs/promises";
import {dirname, extname, join, resolve, sep} from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";
const argv = process.argv.slice(2);
const option = (name, fallback) => argv.includes(name) ? argv[argv.indexOf(name) + 1] : fallback;
const project = resolve(option("--project", join(dirname(fileURLToPath(import.meta.url)), "../..")));
const build = resolve(option("--build", join(project, "web-demo/dist")));
const executable = option("--browser", "google-chrome");
const output = resolve(option("--output", join(project, "invoice-record-receiving")));
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
await mkdir(output);
const downloadPath = join(output, "downloads");
await mkdir(downloadPath);
const profile = await mkdtemp(join(output, "chrome-"));
const report = {schema:"ledgerly.invoice-record-browser/1",status:"running",project,build,
  executable,node:process.version,checkout:process.env.GITHUB_SHA??null,
  claim:"https://github.com/Jacob-Met/ledgerly/issues/34",
  checks:[],artifacts:[],requests:[],externalRequests:[],serverRequests:[],
  sourceSha256:{},buildSha256:{},sourceUnchanged:false,
  observer:"Native Worker replies are copied without replacing the Python engine. One explicit busy control delays delivery of a real reply; the terminal-error control dispatches an authored Worker error.",
  printBoundary:"Actual standalone HTML, print DOM and PDF generation; no physical printer or direct pixel/PDF-text inspection claim."};
const sourcePaths = [
  "ledgerly/__init__.py","ledgerly/agent.py","ledgerly/extract.py","ledgerly/paypal.py",
  "web-demo/python/bridge.py","web-demo/python/review.py","web-demo/python/invoice_details.py",
  "web-demo/src/main.ts","web-demo/src/invoice-details.ts","web-demo/src/invoice-details.css",
  "web-demo/src/invoice-record.ts","web-demo/src/review.ts","web-demo/src/approval-preview.ts",
  "web-demo/src/engine.worker.ts","web-demo/src/worker-client.ts",
  "web-demo/scripts/stage-python.mjs","web-demo/package.json","web-demo/package-lock.json",
  "web-demo/index.html","web-demo/tsconfig.json","web-demo/vite.config.ts",
  "fixtures/04_multi_currency.txt","fixtures/08_jpy_zero_decimal.txt",
  "web-demo/tools/check_invoice_record_browser.mjs",".github/workflows/invoice-record-browser.yml",
];
async function sourceHashes() {
  const result={};
  for(const name of sourcePaths) {
    try {result[name]=hash(await readFile(join(project,name)));}
    catch(error) {if(error.code==="ENOENT"&&name==="web-demo/src/invoice-record.ts")result[name]=null;else throw error;}
  }
  return result;
}
async function buildHashes(directory,prefix="") {
  const result={};
  for(const item of await readdir(directory,{withFileTypes:true})) {
    const name=prefix+item.name;
    if(item.isDirectory()) Object.assign(result,await buildHashes(join(directory,item.name),name+"/"));
    else if(item.isFile()) result[name]=hash(await readFile(join(directory,item.name)));
    else throw new Error("Unexpected nonregular build artifact: "+name);
  }
  return result;
}
report.sourceSha256=await sourceHashes();
const sourceBefore={...report.sourceSha256};
report.buildSha256=await buildHashes(build);
const downloads=new Map(),pageErrors=[],pending=new Map();
let browser,socket,sessionId,appSession,fileSession,browserLog="",sequence=0,pageRequests=[];
const sleep=milliseconds=>new Promise(resolve_=>setTimeout(resolve_,milliseconds));
const server=createServer(async(request,response)=>{
  try{
    const pathname=decodeURIComponent(new URL(request.url,"http://localhost").pathname);
    report.serverRequests.push({method:request.method,path:pathname});
    if(request.method!=="GET"){response.writeHead(405).end();return;}
    const filename=resolve(build,pathname==="/"?"index.html":"."+pathname);
    if(!filename.startsWith(build+sep)){response.writeHead(403).end();return;}
    const bytes=await readFile(filename);
    const mime={".html":"text/html",".js":"text/javascript",".mjs":"text/javascript",
      ".css":"text/css",".json":"application/json",".wasm":"application/wasm",
      ".svg":"image/svg+xml",".zip":"application/zip"}[extname(filename)]||"application/octet-stream";
    response.writeHead(200,{"Content-Type":mime,"Cache-Control":"no-store"}).end(bytes);
  }catch{response.writeHead(404).end("Missing build file.");}
});
await new Promise(resolve_=>server.listen(0,"127.0.0.1",resolve_));
const base="http://127.0.0.1:"+server.address().port;
async function waitFor(check, label, attempts = 600) {
  let lastError;
  for (let step = 0; step < attempts; step++) {
    try { if (await check()) return; } catch (error) { lastError = error; }
    await sleep(100);
  }
  throw new Error('Timed out: ' + label + (lastError ? ' (' + lastError.message + ')' : ''));
}
function command(method, params = {}, scoped = true) {
  const id = ++sequence;
  return new Promise((resolve_, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id); reject(new Error('CDP timeout: ' + method));
    }, 15000);
    pending.set(id, {resolve: resolve_, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(scoped && sessionId ? {sessionId: typeof scoped === "string" ? scoped : sessionId} : {})}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description
    ?? result.exceptionDetails.text);
  return result.result.value;
}
async function key(key_, code, virtualKey, modifiers = 0) {
  for (const type of ['keyDown', 'keyUp']) {
    await command('Input.dispatchKeyEvent', {type, key: key_, code,
      windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey, modifiers,
      ...(key_ === 'Enter' && type === 'keyDown' ? {text: '\r', unmodifiedText: '\r'} : {})});
  }
}
async function activate(selector) {
  const exists = await evaluate('(() => { const node = document.querySelector(' +
    JSON.stringify(selector) + '); if (!node || node.matches(":disabled") || !node.getClientRects().length) return false; ' +
    'node.scrollIntoView({block:"center"}); node.focus(); return true; })()');
  assert.ok(exists, 'Available keyboard control: ' + selector);
  await key('Enter', 'Enter', 13);
}
async function click(selector) {
  const box = await evaluate('(() => { const node = document.querySelector(' +
    JSON.stringify(selector) + '); if (!node || node.matches(":disabled")) return null; ' +
    'node.scrollIntoView({block:"center"}); const b = node.getBoundingClientRect(); ' +
    'return {x:b.x+b.width/2,y:b.y+b.height/2,width:b.width,height:b.height}; })()');
  assert.ok(box && box.width > 0 && box.height > 0, 'Visible pointer control: ' + selector);
  for (const type of ['mousePressed', 'mouseReleased']) {
    await command('Input.dispatchMouseEvent', {type, x: box.x, y: box.y,
      button: 'left', clickCount: 1});
  }
}
async function textInput(selector, value) {
  await evaluate('(() => {const node=document.querySelector(' + JSON.stringify(selector) +
    '); if(!node) throw new Error("Missing input"); node.scrollIntoView({block:"center"}); node.focus();})()');
  await key('a', 'KeyA', 65, 2);
  await command('Input.insertText', {text: value});
  assert.equal(await evaluate('document.querySelector(' + JSON.stringify(selector) + ').value'), value);
}
async function navigate(url, readySelector, width = 1280, height = 1000) {
  await command('Emulation.setEmulatedMedia', {media: ''});
  await command('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  pageRequests = [];
  await command('Page.navigate', {url});
  await waitFor(() => evaluate('document.URL === ' + JSON.stringify(url) +
    ' && document.readyState === "complete" && !!document.querySelector(' +
    JSON.stringify(readySelector) + ')'), 'actual page ' + url);
}
async function saveArtifact(name, bytes, details = {}) {
  const buffer = Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
  assert.ok(buffer.length <= 2 * 1024 * 1024, 'Bounded artifact: ' + name);
  await writeFile(join(output, name), buffer);
  const value = {name, bytes: buffer.length, sha256: hash(buffer), ...details};
  report.artifacts.push(value);
  return value;
}
async function screenshot(name, selector = null) {
  if (selector) await evaluate('document.querySelector(' + JSON.stringify(selector) +
    ').scrollIntoView({block:"start"})');
  const {data} = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  return saveArtifact(name, Buffer.from(data, 'base64'), {kind: 'actual Chrome screenshot'});
}
const passed = name => { report.checks.push(name); console.log('PASS ' + name); };

async function downloaded(button, name) {
  const prior = new Set(downloads.keys());
  await activate(button);
  let actual;
  await waitFor(() => {
    actual = [...downloads.values()].find(value => !prior.has(value.guid) && value.state === 'completed');
    return !!actual;
  }, 'actual download ' + name);
  const bytes = await readFile(join(downloadPath, actual.guid));
  await saveArtifact(name, bytes, {kind: 'actual browser download',
    suggestedFilename: actual.suggestedFilename});
  return {bytes, file: join(output, name), suggestedFilename: actual.suggestedFilename};
}

const OBSERVER = "(() => {"+
  "const NativeWorker=window.Worker;const p=window.__invoiceRecordProbe={calls:[],states:[],workers:[],holdNext:false,held:null};"+
  "window.Worker=class extends NativeWorker{constructor(...args){super(...args);p.workers.push(this);"+
  "this.addEventListener('message',event=>{if(event.data?.data?.state){"+
  "if(p.holdNext){p.holdNext=false;event.stopImmediatePropagation();p.held={worker:this,data:event.data};return;}"+
  "p.states.push(JSON.parse(JSON.stringify(event.data.data.state)));}});}"+
  "postMessage(...args){p.calls.push(JSON.parse(JSON.stringify(args[0])));return super.postMessage(...args);}};"+
  "p.release=()=>{const h=p.held;p.held=null;if(h)h.worker.dispatchEvent(new MessageEvent('message',{data:h.data}));};"+
  "})();";
async function newPage(observe=false) {
  const {targetId}=await command("Target.createTarget",{url:"about:blank"},false);
  ({sessionId}=await command("Target.attachToTarget",{targetId,flatten:true},false));
  await command("Page.enable");await command("Runtime.enable");await command("Network.enable");
  await command("Fetch.enable",{patterns:[{urlPattern:"http*"}]});
  if(observe)await command("Page.addScriptToEvaluateOnNewDocument",{source:OBSERVER});
  return sessionId;
}
const state=()=>evaluate("window.__invoiceRecordProbe.states.at(-1)");
const calls=()=>evaluate("window.__invoiceRecordProbe.calls");
async function action(selector) {
  const count=await evaluate("window.__invoiceRecordProbe.states.length");
  await activate(selector);
  await waitFor(()=>evaluate("window.__invoiceRecordProbe.states.length>"+count+
    " && !document.querySelector('#analyze').disabled"),"real Python action "+selector);
  return state();
}
async function sourceText(text) {
  await textInput("#job-email",text);
  await action("#analyze");
}
const buttonFor=id=>'button[data-save-invoice-record="'+id+'"]';
const detailFor=id=>'details[data-invoice-detail-id="'+id+'"]';
async function openDetail(id) {
  const selector=detailFor(id);
  if(!await evaluate("document.querySelector("+JSON.stringify(selector)+").open"))
    await activate(selector+" > summary");
  return selector;
}
async function projection(selector) {
  return evaluate("(() => {const root=document.querySelector("+JSON.stringify(selector)+");"+
    "if(!root)throw new Error('Missing invoice projection');return {"+
    "fields:[...root.querySelectorAll('.invoice-detail-fields > div')].map(row=>[row.querySelector('dt').textContent,row.querySelector('dd').textContent]),"+
    "tables:[...root.querySelectorAll('table')].map(table=>({caption:table.caption?.textContent,rows:[...table.rows].map(row=>[...row.cells].map(cell=>cell.textContent))})),"+
    "note:root.querySelector('.invoice-detail-note')?.textContent??null,"+
    "explanations:[...root.querySelectorAll('.invoice-detail-explanation,.invoice-detail-empty')].map(node=>node.textContent),"+
    "snapshot:root.querySelector('.invoice-detail-provenance').textContent};})()");
}
async function saveState(name,snapshot) {
  return saveArtifact(name,JSON.stringify(snapshot,null,2)+"\n",{kind:"actual Python Worker snapshot"});
}
async function receiveDownload(id,name,snapshot) {
  const selector=await openDetail(id);
  const display=await projection(selector);
  const beforeCalls=await calls(),beforeState=await state();
  const file=await downloaded(buttonFor(id),name);
  assert.match(file.suggestedFilename,/^ledgerly-sandbox-invoice-[A-Za-z0-9_-]+\.html$/);
  assert.equal(file.bytes.toString("utf8").startsWith("<!doctype html>"),true);
  assert.deepEqual(await calls(),beforeCalls,"Downloading must not send a Worker request");
  assert.deepEqual(await state(),beforeState,"Downloading must not change the accepted snapshot");
  assert.equal(snapshot.invoice_details.find(row=>row.invoice_id===id).record.id,id);
  return {...file,id,name,display,snapshot:structuredClone(snapshot)};
}
const ledgerKeys=["invoice_id","invoice_number","client_name","client_email","currency",
  "total","paid_amount","balance","status","sent_on","due_on","reminders_sent"];
function nativeText(value){return typeof value==="string"?(value||"(empty)"):
  typeof value==="number"&&Number.isFinite(value)?String(value):"Not recorded";}
async function inspectOffline(file,width=1280,print=false) {
  const captureName=file.name.replace(/\.html$/, "")+"-"+width;
  if(!fileSession)fileSession=await newPage(false);
  else sessionId=fileSession;
  const url=pathToFileURL(file.file).href;
  await navigate(url,"#print-invoice-record",width,width===390?844:1000);
  assert.equal(await evaluate("document.body.dataset.invoiceRecordFormat"),"ledgerly.sandbox-invoice-record.v1");
  assert.deepEqual(await projection(".invoice-details"),file.display,"Complete retained record display");
  const entry=file.snapshot.ledger.find(row=>row.invoice_id===file.id);
  const summary=await evaluate("[...document.querySelectorAll('[data-ledger-field]')].map(node=>[node.dataset.ledgerField,node.textContent])");
  assert.deepEqual(summary,ledgerKeys.map(key=>[key,nativeText(entry[key])]),"All original ledger fields");
  assert.equal(await evaluate("document.querySelector('#invoice-record-snapshot').textContent"),file.snapshot.today);
  const created=await evaluate("document.querySelector('#invoice-record-created').textContent");
  assert.equal(new Date(created).toISOString(),created);
  const structure=await evaluate("({remote:document.querySelectorAll('script[src],link[href],img,iframe,object,embed,form,a[href]').length,"+
    "controls:[...document.querySelectorAll('button,input,select,textarea')].map(n=>n.id),"+
    "injected:typeof window.recordExecuted,overflow:document.documentElement.scrollWidth>innerWidth,"+
    "sandbox:document.body.innerText.includes('SANDBOX INVOICE RECORD'),"+
    "explanation:document.querySelector('#invoice-record-boundary').textContent})");
  assert.equal(structure.remote,0);assert.deepEqual(structure.controls,["print-invoice-record"]);
  assert.equal(structure.injected,"undefined");assert.equal(structure.overflow,false);
  assert.equal(structure.sandbox,true);assert.match(structure.explanation,/not a payable invoice/i);
  assert.ok(pageRequests.every(url_=>!/^https?:/.test(url_)),"Offline record has no HTTP request");
  if(print){
    await activate(".invoice-details > summary");
    assert.equal(await evaluate("document.querySelector('.invoice-details').open"),false);
    await evaluate("(()=>{const original=window.print;window.__recordPrintCalls=0;window.print=function(...args){window.__recordPrintCalls++;return Reflect.apply(original,this,args);};})()");
    await activate("#print-invoice-record");
    await waitFor(()=>evaluate("window.__recordPrintCalls===1"),"actual standalone window.print");
    assert.equal(await evaluate("document.querySelector('.invoice-details').open"),true);
    await command("Emulation.setEmulatedMedia",{media:"print"});
    const paper=await evaluate("({buttonRects:document.querySelector('#print-invoice-record').getClientRects().length,"+
      "tables:[...document.querySelectorAll('table')].map(n=>({width:n.getBoundingClientRect().width,parent:n.parentElement.getBoundingClientRect().width})),"+
      "note:getComputedStyle(document.querySelector('.invoice-detail-note')).whiteSpace})");
    assert.equal(paper.buttonRects,0,"Print control has no rendered box, including a hidden ancestor");assert.equal(paper.note,"pre-wrap");
    assert.ok(paper.tables.every(table=>table.width<=table.parent+1));
    const pdf=await command("Page.printToPDF",{printBackground:true,preferCSSPageSize:true});
    const bytes=Buffer.from(pdf.data,"base64");
    assert.equal(bytes.subarray(0,5).toString(),"%PDF-");
    const pages=(bytes.toString("latin1").match(/\/Type\s*\/Page\b/g)||[]).length;
    assert.ok(pages>=1&&pages<=12,"Bounded actual invoice print pages");
    await saveArtifact(captureName+".pdf",bytes,
      {kind:"actual Chrome PDF",pages,boundary:report.printBoundary});
    await command("Emulation.setEmulatedMedia",{media:""});
  }
  await screenshot(captureName+".png");
  sessionId=appSession;
}

/** The landed CSV receiver's bounded, numbered fixture bundle convention.
 * Only these authored rendering fixtures and the receiving report are eligible.
 * Never scan output recursively or include browser state, source or environment files.
 */
async function printReceivingBundle() {
  const rendered = [
    "original-usd-record.html", "paid-usd-record.html", "eur-record.html",
    "literal-jpy-record.html", "retried-literal-record.html",
    "paid-usd-record-1280.png", "eur-record-390.png",
    "original-usd-record-1280.png", "literal-jpy-record-390.png",
    "paid-usd-record-1280.pdf", "literal-jpy-record-390.pdf",
  ];
  if (report.status === "passed")
    for (const name of rendered) assert.ok(report.artifacts.some(item => item.name === name),
      "A successful run must retain its fixed rendering fixture: " + name);
  const names = [...rendered, "failed-state.png"].filter(name =>
    report.artifacts.some(item => item.name === name));
  names.push("receiving-report.json");
  const files = [];
  let total = 0;
  for (const name of names.sort()) {
    const filename = join(output, name);
    const info = await lstat(filename);
    assert.ok(info.isFile() && !info.isSymbolicLink(), "Bundle fixture must be a regular file: " + name);
    assert.ok(info.size <= 2 * 1024 * 1024, "Bundle fixture exceeds 2 MiB: " + name);
    const bytes = await readFile(filename);
    assert.equal(bytes.length, info.size, "Bundle fixture changed while being read: " + name);
    const digest = hash(bytes), expected = report.artifacts.find(item => item.name === name);
    if (expected) {
      assert.equal(bytes.length, expected.bytes, "Bundle fixture size differs from actual artifact: " + name);
      assert.equal(digest, expected.sha256, "Bundle fixture digest differs from actual artifact: " + name);
    }
    total += bytes.length;
    assert.ok(total <= 2 * 1024 * 1024, "Receiving packet exceeds 2 MiB; refusing to truncate evidence.");
    files.push({path: name, bytes: bytes.length, sha256: digest, base64: bytes.toString("base64")});
  }
  const payload = Buffer.from(JSON.stringify({version: 1, files}), "utf8");
  assert.ok(payload.length <= 4 * 1024 * 1024, "Serialized receiving packet exceeds 4 MiB.");
  const encoded = payload.toString("base64"), chunks = [];
  for (let offset = 0; offset < encoded.length; offset += 4096)
    chunks.push(encoded.slice(offset, offset + 4096));
  console.log("LEDGERLY_INVOICE_RECORD_BUNDLE_BEGIN " + JSON.stringify({
    bytes: payload.length, sha256: hash(payload), chunks: chunks.length}));
  for (let index = 0; index < chunks.length; index++)
    console.log("LEDGERLY_INVOICE_RECORD_BUNDLE_CHUNK " + index + " " + chunks[index]);
  console.log("LEDGERLY_INVOICE_RECORD_BUNDLE_END");
}

try {
  browser=spawn(executable,["--headless=new","--disable-gpu","--no-sandbox","--no-first-run",
    "--disable-background-networking","--disable-component-update","--disable-sync","--disable-default-apps",
    "--disable-features=Translate,MediaRouter,OptimizationHints","--metrics-recording-only",
    "--remote-debugging-port=0","--user-data-dir="+profile,"about:blank"],{stdio:["ignore","ignore","pipe"]});
  browser.stderr.on("data",chunk=>{browserLog=(browserLog+chunk.toString()).slice(-24000);});
  browser.on("error",error=>{browserLog+=String(error);});
  let active;
  await waitFor(async()=>{active=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).trim().split("\n");return active.length===2;},"system Chrome");
  socket=new WebSocket("ws://127.0.0.1:"+active[0]+active[1]);
  socket.addEventListener("message",event=>{
    const message=JSON.parse(event.data);
    if(message.id){
      const request=pending.get(message.id);if(!request)return;
      pending.delete(message.id);clearTimeout(request.timer);
      if(message.error)request.reject(new Error(message.error.message));else request.resolve(message.result);
    } else if(message.method==="Browser.downloadWillBegin"||message.method==="Browser.downloadProgress"){
      const value=message.params;downloads.set(value.guid,{...downloads.get(value.guid),...value});
    } else if(message.method==="Runtime.exceptionThrown"){
      pageErrors.push(message.params.exceptionDetails.exception?.description??message.params.exceptionDetails.text);
    } else if(message.method==="Fetch.requestPaused"){
      const request=message.params.request;
      const allowed=request.method==="GET"&&new URL(request.url).origin===base;
      if(!allowed)report.externalRequests.push({url:request.url,method:request.method});
      void command(allowed?"Fetch.continueRequest":"Fetch.failRequest",
        {requestId:message.params.requestId,...(!allowed?{errorReason:"BlockedByClient"}:{})},
        message.sessionId).catch(error=>pageErrors.push(error.message));
    } else if(message.method==="Network.requestWillBeSent"){
      pageRequests.push(message.params.request.url);
      report.requests.push({url:message.params.request.url,method:message.params.request.method});
    } else if(message.method==="Page.javascriptDialogOpening"){
      void command("Page.handleJavaScriptDialog",{accept:true},message.sessionId).catch(error=>pageErrors.push(error.message));
    }
  });
  await new Promise((resolve_,reject)=>{socket.addEventListener("open",resolve_,{once:true});socket.addEventListener("error",reject,{once:true});});
  report.browser=await command("Browser.getVersion",{},false);
  await command("Browser.setDownloadBehavior",{behavior:"allowAndName",downloadPath,eventsEnabled:true},false);
  appSession=await newPage(true);
  await navigate(base+"/","#engine-start");
  await action("#engine-start");
  const empty=await state();
  assert.deepEqual(empty.ledger,[]);assert.deepEqual(empty.invoice_details,[]);assert.equal(empty.external_calls,0);
  passed("actual local Python Worker starts empty with no external calls");

  const twoCurrencies=await readFile(join(project,"fixtures/04_multi_currency.txt"),"utf8");
  await sourceText(twoCurrencies);
  const drafted=await action("#draft");
  assert.equal(drafted.ledger.length,2);
  assert.deepEqual([...new Set(drafted.ledger.map(row=>row.currency))].sort(),["EUR","USD"]);
  const usd=drafted.ledger.find(row=>row.currency==="USD").invoice_id;
  const eur=drafted.ledger.find(row=>row.currency==="EUR").invoice_id;
  assert.match(usd,/^[A-Za-z0-9_-]+$/);assert.match(eur,/^[A-Za-z0-9_-]+$/);
  const sourceRecord=drafted.invoice_details.find(row=>row.invoice_id===usd).record;
  assert.ok(sourceRecord.items.length>0);assert.equal(sourceRecord.status,"DRAFT");
  await openDetail(usd);
  await saveState("original-drafted-snapshot.json",drafted);
  const present=await evaluate("[...document.querySelectorAll('button[data-save-invoice-record]')].map(node=>({id:node.dataset.saveInvoiceRecord,disabled:node.disabled,text:node.textContent}))");
  report.originalBoundary={retainedInvoiceId:usd,retainedRecord:sourceRecord,observedActions:present,
    mechanism:"Actual RulesExtractor/Agent/SandboxMock draft followed by the current ledger DOM."};
  passed("actual two-currency draft retains full original invoice records and explicit pending approvals");
  assert.equal(present.filter(row=>row.id===usd&&!row.disabled).length,1,
    "Missing Save sandbox invoice record action for the retained native invoice");
  assert.equal(present.filter(row=>row.id===eur&&!row.disabled).length,1);
  const original=await receiveDownload(usd,"original-usd-record.html",drafted);
  assert.equal(original.bytes.toString("utf8").includes(twoCurrencies),false,"Do not add the original pasted email");
  passed("explicit keyboard download pins the exact native invoice without a Worker call or state change");

  for(const pendingAction of drafted.pending)
    await action('#approval-list button[data-approve="'+pendingAction.id+'"]');
  await textInput("#payment-amount","100.25");
  const paid=await action('#ledger-list button[data-pay="'+usd+'"]');
  const paidRecord=paid.invoice_details.find(row=>row.invoice_id===usd).record;
  assert.equal(paidRecord.status,"PARTIALLY_PAID");
  assert.deepEqual(paidRecord.items,sourceRecord.items);
  assert.equal(paidRecord.payments.transactions.at(-1).amount.value,"100.25");
  await saveState("paid-native-snapshot.json",paid);
  const paidFile=await receiveDownload(usd,"paid-usd-record.html",paid);
  const euroFile=await receiveDownload(eur,"eur-record.html",paid);
  const replayed=await action("#replay-webhook");
  assert.deepEqual(replayed.invoice_details,paid.invoice_details);
  assert.deepEqual(await readFile(original.file),original.bytes);
  await inspectOffline(paidFile,1280,true);
  await inspectOffline(euroFile,390,false);
  await inspectOffline(original,1280,false);
  passed("downloaded records reopen offline with complete original content, separate currencies and stable earlier snapshots after payment/replay");

  const jpyInput=await readFile(join(project,"fixtures/08_jpy_zero_decimal.txt"),"utf8")+
    "\nPRIVATE PASTE BODY: receiver-only narrative must not be added to the invoice file.\n";
  await sourceText(jpyInput);
  await activate("#review-editor > summary");
  const hostile='Exact "</script><img src=x onerror=window.recordExecuted=1> & 海 😀 \u2028next\u2029line';
  const client='日本語 <b>Client</b> 😀';
  await textInput("#review-client-name",client);
  await textInput("#review-client-email","record-receiver@example.test");
  await textInput("#review-line-0-desc",hostile);
  await click("#review-confirm");
  await action("#review-check");
  const literal=await action("#draft");
  const literalEntry=literal.ledger.find(row=>row.client_email==="record-receiver@example.test");
  assert.equal(literalEntry.currency,"JPY");
  const literalId=literalEntry.invoice_id;
  const literalRecord=literal.invoice_details.find(row=>row.invoice_id===literalId).record;
  assert.equal(literalRecord.items[0].name,hostile);
  assert.ok(!literalRecord.amount.value.includes("."));
  const literalFile=await receiveDownload(literalId,"literal-jpy-record.html",literal);
  assert.equal(literalFile.bytes.toString("utf8").includes("PRIVATE PASTE BODY"),false);
  await saveState("literal-native-snapshot.json",literal);
  await inspectOffline(literalFile,390,true);
  passed("actual corrected Python invoice preserves literal Unicode/markup, line separators and zero-decimal amounts in the reopened printable file");

  const beforeFailureCalls=await calls(),beforeFailureState=await state();
  const priorDownloads=downloads.size;
  await evaluate("(()=>{window.__recordCreateURL=URL.createObjectURL;URL.createObjectURL=function(blob){if(blob.type.startsWith('text/html'))throw new Error('authored invoice URL allocation refusal');return window.__recordCreateURL.call(this,blob);};})()");
  await activate(buttonFor(literalId));
  await waitFor(()=>evaluate("document.querySelector('#status-message').textContent.includes('Could not start')"),"explicit download refusal");
  assert.equal(downloads.size,priorDownloads);
  assert.deepEqual(await state(),beforeFailureState);assert.deepEqual(await calls(),beforeFailureCalls);
  await evaluate("URL.createObjectURL=window.__recordCreateURL");
  const retried=await receiveDownload(literalId,"retried-literal-record.html",beforeFailureState);
  assert.equal(retried.display.note,literalFile.display.note);
  assert.equal(retried.bytes.toString("utf8").includes(hostile),false,"Markup-like source is escaped in HTML bytes");
  passed("download-allocation refusal preserves the accepted snapshot for a later explicit retry");

  await evaluate("window.__invoiceRecordProbe.holdNext=true");
  await activate("#analyze");
  await waitFor(()=>evaluate("!!window.__invoiceRecordProbe.held"),"authored hold of a real Worker reply");
  assert.equal(await evaluate("document.querySelector("+JSON.stringify(buttonFor(literalId))+").disabled"),true);
  const heldDownloads=downloads.size,heldCalls=await calls();
  await evaluate("document.querySelector("+JSON.stringify(buttonFor(literalId))+").dispatchEvent(new MouseEvent('click',{bubbles:true}))");
  await sleep(100);
  assert.equal(downloads.size,heldDownloads);assert.deepEqual(await calls(),heldCalls);
  await evaluate("window.__invoiceRecordProbe.release()");
  await waitFor(()=>evaluate("!document.querySelector('#analyze').disabled"),"real reply delivery resumes");
  assert.equal(await evaluate("document.querySelector("+JSON.stringify(buttonFor(literalId))+").disabled"),false);
  const inactiveState=await state();
  await evaluate("window.__invoiceRecordProbe.workers.at(-1).dispatchEvent(new ErrorEvent('error',{message:'authored terminal Worker failure'}))");
  await waitFor(()=>evaluate("document.querySelector('#engine-status').textContent==='PYTHON UNAVAILABLE'"),"explicit inactive session");
  assert.equal(await evaluate("document.querySelector("+JSON.stringify(buttonFor(literalId))+").disabled"),true);
  const inactiveCalls=await calls(),inactiveDownloads=downloads.size;
  await evaluate("document.querySelector("+JSON.stringify(buttonFor(literalId))+").dispatchEvent(new MouseEvent('click',{bubbles:true}))");
  await sleep(100);
  assert.equal(downloads.size,inactiveDownloads);assert.deepEqual(await calls(),inactiveCalls);
  assert.deepEqual(await state(),inactiveState);
  await action("#engine-start");
  assert.deepEqual((await state()).ledger,[]);
  assert.equal(await evaluate("document.querySelectorAll('[data-save-invoice-record]').length"),0);
  assert.deepEqual(await readFile(original.file),original.bytes);
  assert.deepEqual(await readFile(literalFile.file),literalFile.bytes);
  passed("busy and inactive sessions refuse stale download actions; explicit restart clears availability while existing files remain unchanged");

  assert.deepEqual(report.externalRequests,[]);
  assert.deepEqual(pageErrors,[]);
  report.workerCalls=await calls();report.finalState=await state();
  assert.equal(report.finalState.external_calls,0);
  assert.ok(report.serverRequests.every(request=>request.method==="GET"));
  passed("source/browser flow has no provider requests, runtime exceptions or outbound actions from download/print");
  report.status="passed";
}catch(error){
  report.status="failed";report.error=error.stack??String(error);report.browserLog=browserLog;
  if(sessionId){try{report.lastPage=await evaluate("({url:location.href,focus:document.activeElement?.outerHTML,text:document.body?.innerText.slice(0,9000)})");await screenshot("failed-state.png");}catch{}}
  console.error(report.error);process.exitCode=1;
}finally{
  if(socket?.readyState===WebSocket.OPEN){try{await command("Browser.close",{},false);}catch{}}
  socket?.close();for(const request of pending.values())clearTimeout(request.timer);
  if(browser&&browser.exitCode===null)browser.kill("SIGTERM");
  server.closeAllConnections();await new Promise(resolve_=>server.close(resolve_));
  await sleep(300);await rm(profile,{recursive:true,force:true});await rm(downloadPath,{recursive:true,force:true});
  report.sourceUnchanged=JSON.stringify(await sourceHashes())===JSON.stringify(sourceBefore);
  if(!report.sourceUnchanged){report.status="failed";process.exitCode=1;}
  report.pageErrors=pageErrors;report.totalArtifactBytes=report.artifacts.reduce((sum,item)=>sum+item.bytes,0);
  if(report.totalArtifactBytes>8*1024*1024){report.status="failed";report.artifactLimitExceeded=true;process.exitCode=1;}
  await writeFile(join(output,"receiving-report.json"),JSON.stringify(report,null,2)+"\n");
  try { await printReceivingBundle(); }
  catch (error) {
    report.status="failed";report.bundleError=error.stack??String(error);process.exitCode=1;
    await writeFile(join(output,"receiving-report.json"),JSON.stringify(report,null,2)+"\n");
    console.error(report.bundleError);
  }
  console.log("INVOICE_RECORD_BROWSER_RESULT "+report.status.toUpperCase()+" checks="+report.checks.length+
    " artifacts="+report.artifacts.length+" source_unchanged="+report.sourceUnchanged);
  console.log("INVOICE_RECORD_BROWSER_RECEIPT "+JSON.stringify(report));
}
