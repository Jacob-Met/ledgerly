#!/usr/bin/env node
/** Actual built UI -> Pyodide Worker -> explicit rejection with a selected note.
 * Node 22 and an installed Chrome. No browser library or replacement engine.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir,mkdtemp,rm,readdir,statfs} from 'node:fs/promises';
import {dirname,extname,join,resolve,sep} from 'node:path';
import {freemem} from 'node:os';

const args=process.argv.slice(2);
const option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const project=resolve(option('--project','.'));
const build=resolve(option('--build',join(project,'web-demo/dist')));
const output=resolve(option('--output',join(project,'rejection-reason-receiving')));
const executable=option('--browser','chromium');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const storage=await statfs(dirname(output));
const available=process.platform==='linux'
 ? Number((await readFile('/proc/meminfo','utf8')).match(/^MemAvailable:\s+(\d+)/m)[1])*1024 : freemem();
assert.ok(storage.bavail*storage.bsize>=805306368,'768 MiB disk reserve');
assert.ok(available>=1610612736,'1.5 GiB memory reserve');
await mkdir(output);
const profile=await mkdtemp(join(output,'chrome-profile-'));
const sourcePaths=[
 'ledgerly/__init__.py','ledgerly/agent.py','ledgerly/extract.py','ledgerly/paypal.py',
 'web-demo/python/bridge.py','web-demo/python/review.py','web-demo/python/invoice_details.py',
 'web-demo/src/main.ts','web-demo/src/approval-preview.ts',
 'web-demo/src/engine.worker.ts','web-demo/src/worker-client.ts',
 'web-demo/src/rejection-reason.ts','web-demo/src/rejection-reason.css',
 'web-demo/package.json','web-demo/package-lock.json','web-demo/tsconfig.json',
 'web-demo/vite.config.ts','web-demo/scripts/stage-python.mjs',
];
async function sourceHashes(){
 const result={};
 for(const path of sourcePaths){
  try{result[path]=hash(await readFile(join(project,path)));}
  catch(error){if(error.code==='ENOENT'&&path.includes('/rejection-reason.'))result[path]=null;else throw error;}
 }
 return result;
}
async function buildHashes(directory,prefix=''){
 const result={};
 for(const entry of await readdir(directory,{withFileTypes:true})){
  if(entry.isDirectory())Object.assign(result,await buildHashes(join(directory,entry.name),prefix+entry.name+'/'));
  else if(entry.isFile())result[prefix+entry.name]=hash(await readFile(join(directory,entry.name)));
  else throw new Error('Unexpected build entry');
 }
 return result;
}
const sourceBefore=await sourceHashes();
const report={schema:'ledgerly.rejection-reason-browser/1',status:'running',project,build,
 node:process.version,browserExecutable:executable,checks:[],artifacts:[],requests:[],
 externalRequests:[],serverRequests:[],sourceBefore,buildHashes:await buildHashes(build),
 guard:{diskFree:storage.bavail*storage.bsize,memoryAvailable:available},
 instrumentation:'Real Worker subclass records requests/replies; one real reply is delayed for busy-state receiving and one outgoing reject ID is replaced with an unknown ID to obtain an actual bridge refusal. No Python result, Agent or provider is replaced.'};
let browser,socket,sessionId,sequence=0,browserLog='',pageRequests=[];
const pending=new Map(),pageErrors=[];
const sleep=ms=>new Promise(resolve_=>setTimeout(resolve_,ms));
const server=createServer(async(request,response)=>{
 try{
  const pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);
  report.serverRequests.push({method:request.method,path:pathname});
  if(request.method!=='GET'){response.writeHead(405).end();return;}
  const file=resolve(build,pathname==='/'?'index.html':'.'+pathname);
  if(!file.startsWith(build+sep)){response.writeHead(403).end();return;}
  const bytes=await readFile(file);
  const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json',
   '.wasm':'application/wasm','.svg':'image/svg+xml','.zip':'application/zip'}[extname(file)]||'application/octet-stream';
  response.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'}).end(bytes);
 }catch{response.writeHead(404).end('Missing build file.');}
});
await new Promise(resolve_=>server.listen(0,'127.0.0.1',resolve_));
const base='http://127.0.0.1:'+server.address().port;

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

const OBSERVER=String.raw`(()=>{
 const NativeWorker=window.Worker;
 const p=window.__reasonProbe={workers:[],calls:[],replies:[],delivered:[],holdNext:false,held:null,refuseNextReject:false};
 window.Worker=class extends NativeWorker {
  constructor(...args){
   super(...args);p.workers.push(this);
   this.addEventListener('message',event=>{
    if(!event.data?.data?.state)return;
    if(p.holdNext){p.holdNext=false;event.stopImmediatePropagation();p.held={worker:this,data:event.data};return;}
    p.replies.push(structuredClone(event.data.data));
   });
  }
  postMessage(...args){
   p.calls.push(structuredClone(args[0]));
   if(p.refuseNextReject&&args[0].action==='reject'){
    p.refuseNextReject=false;
    args[0]={...args[0],payload:{...args[0].payload,action_id:'missing-authored-receiver-action'}};
    p.delivered.push(structuredClone(args[0]));
   }
   return super.postMessage(...args);
  }
 };
 p.release=()=>{const held=p.held;p.held=null;if(held)held.worker.dispatchEvent(new MessageEvent('message',{data:held.data}));};
})();`;
const state=()=>evaluate('window.__reasonProbe.replies.at(-1).state');
const calls=()=>evaluate('window.__reasonProbe.calls');
async function action(selector){
 const count=await evaluate('window.__reasonProbe.replies.length');
 await activate(selector);
 await waitFor(()=>evaluate('window.__reasonProbe.replies.length>'+count+
  '&&!document.querySelector("#analyze").disabled'),'actual Python action '+selector,400);
 return state();
}
async function draft(text){
 await textInput('#job-email',text);
 await action('#analyze');
 return action('#draft');
}
const reasonFor=id=>'textarea[data-rejection-reason="'+id+'"]';
const rejectFor=id=>'button[data-reject="'+id+'"]';
const approveFor=id=>'button[data-approve="'+id+'"]';
const value=selector=>evaluate('document.querySelector('+JSON.stringify(selector)+')?.value??null');
const passed=name=>{report.checks.push(name);console.log('PASS '+name);};
async function screenshot(name){
 const result=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 const bytes=Buffer.from(result.data,'base64');
 assert.ok(bytes.length<=2*1024*1024);
 await writeFile(join(output,name),bytes);
 report.artifacts.push({name,bytes:bytes.length,sha256:hash(bytes)});
}
try{
 browser=spawn(executable,['--headless=new','--no-first-run',
  '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
 browser.stderr.on('data',chunk=>{browserLog=(browserLog+chunk.toString()).slice(-16000);});
 browser.on('error',error=>{browserLog+=String(error);});
 let active;
 await waitFor(async()=>{active=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return active.length===2;},'installed Chrome',150);
 socket=new WebSocket('ws://127.0.0.1:'+active[0]+active[1]);
 socket.addEventListener('message',event=>{
  const message=JSON.parse(event.data);
  if(message.id){
   const request=pending.get(message.id);if(!request)return;
   pending.delete(message.id);clearTimeout(request.timer);
   if(message.error)request.reject(new Error(message.error.message));else request.resolve(message.result);
  }else if(message.method==='Runtime.exceptionThrown'){
   pageErrors.push(message.params.exceptionDetails.exception?.description??message.params.exceptionDetails.text);
  }else if(message.method==='Fetch.requestPaused'){
   const request=message.params.request;
   const allowed=request.method==='GET'&&new URL(request.url).origin===base;
   if(!allowed)report.externalRequests.push({url:request.url,method:request.method});
   void command(allowed?'Fetch.continueRequest':'Fetch.failRequest',
    {requestId:message.params.requestId,...(!allowed?{errorReason:'BlockedByClient'}:{})},message.sessionId)
    .catch(error=>pageErrors.push(error.message));
  }else if(message.method==='Network.requestWillBeSent'){
   pageRequests.push(message.params.request.url);
   report.requests.push({url:message.params.request.url,method:message.params.request.method});
  }else if(message.method==='Page.javascriptDialogOpening'){
   void command('Page.handleJavaScriptDialog',{accept:true},message.sessionId).catch(error=>pageErrors.push(error.message));
  }else if(message.method==='Target.attachedToTarget'&&message.params.targetInfo.type==='worker'){
   const workerSession=message.params.sessionId;
   void command('Network.enable',{},workerSession).catch(error=>pageErrors.push(error.message));
  }
 });
 await new Promise((resolve_,reject)=>{socket.addEventListener('open',resolve_,{once:true});socket.addEventListener('error',reject,{once:true});});
 report.browser=await command('Browser.getVersion',{},false);
 const {targetId}=await command('Target.createTarget',{url:'about:blank'},false);
 ({sessionId}=await command('Target.attachToTarget',{targetId,flatten:true},false));
 await command('Page.enable');await command('Runtime.enable');await command('Network.enable');
 await command('Fetch.enable',{patterns:[{urlPattern:'http*'}]});
 await command('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:false,flatten:true});
 await command('Page.addScriptToEvaluateOnNewDocument',{source:OBSERVER});
 await navigate(base+'/','#engine-start');
 await action('#engine-start');
 const empty=await state();
 assert.deepEqual(empty.pending,[]);assert.equal(empty.external_calls,0);
 const fixture=await readFile(join(project,'fixtures/04_multi_currency.txt'),'utf8');
 const drafted=await draft(fixture);
 assert.equal(drafted.pending.length,2);
 const [first,second]=drafted.pending;
 report.originalPending=drafted.pending.map(row=>({id:row.id,kind:row.kind,invoice_id:row.invoice_id}));
 passed('actual current Python engine creates two independently gated currency actions');

 assert.equal(await evaluate('document.querySelectorAll("textarea[data-rejection-reason]").length'),2,
  'each actual pending action must expose its own optional rejection reason');
 const firstReason='  Wrong <milestone> & recipient — 🧾\nPlease revise, then ask again.  ';
 const secondReason='Other currency: keep this independent note.';
 const initialCalls=await calls();
 await textInput(reasonFor(first.id),firstReason);
 await textInput(reasonFor(second.id),secondReason);
 assert.deepEqual(await calls(),initialCalls);
 assert.deepEqual(await state(),drafted);
 assert.equal(await evaluate('document.querySelector('+JSON.stringify(reasonFor(first.id))+').labels[0].querySelector("span").textContent'),'Reason for rejecting (optional)');
 assert.equal(await evaluate('document.querySelectorAll(".rejection-reason script,.rejection-reason img").length'),0);
 passed('literal notes and labels are action-bound; typing sends no Worker request or approval');

 await evaluate('window.__reasonProbe.holdNext=true');
 await activate('#advance-clock');
 await waitFor(()=>evaluate('window.__reasonProbe.held!==null'),'real delayed clock reply',200);
 assert.equal(await evaluate('[...document.querySelectorAll("#approval-list textarea,#approval-list button")].every(node=>node.disabled)'),true);
 await evaluate('window.__reasonProbe.release()');
 await waitFor(()=>evaluate('!document.querySelector("#analyze").disabled'),'busy release',100);
 assert.equal(await value(reasonFor(first.id)),firstReason);
 assert.equal(await value(reasonFor(second.id)),secondReason);
 passed('busy state disables notes and controls; unrelated native snapshot retains both exact drafts');

 const beforeRefusal=await state();
 await evaluate('window.__reasonProbe.refuseNextReject=true');
 await action(rejectFor(first.id));
 const refusal=await evaluate('window.__reasonProbe.replies.at(-1)');
 assert.equal(refusal.ok,false);assert.equal(refusal.error,'KeyError');
 assert.deepEqual(refusal.state,beforeRefusal);
 assert.equal(await value(reasonFor(first.id)),firstReason);
 assert.equal(await value(reasonFor(second.id)),secondReason);
 assert.equal((await evaluate('window.__reasonProbe.delivered')).length,1);
 passed('actual bridge refusal preserves both pending actions and their exact local notes');

 const rejected=await action(rejectFor(first.id));
 const rejectedReply=await evaluate('window.__reasonProbe.replies.at(-1)');
 assert.deepEqual(rejectedReply.result,{rejected:true,reason:firstReason});
 assert.deepEqual(rejected.pending.map(row=>row.id),[second.id]);
 assert.equal(rejected.mock_requests,beforeRefusal.mock_requests);
 assert.equal(await value(reasonFor(first.id)),null);
 assert.equal(await value(reasonFor(second.id)),secondReason);
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Rejected; nothing was sent. Reason: '+firstReason);
 const sentReject=(await calls()).at(-1);
 assert.deepEqual(sentReject.payload,{action_id:first.id,reason:firstReason});
 passed('explicit keyboard rejection receives the exact selected note, leaves the other note intact and makes no provider request');

 await textInput(reasonFor(second.id),'🧾'.repeat(501));
 const beforeInvalid=await calls();
 await activate(rejectFor(second.id));
 assert.deepEqual(await calls(),beforeInvalid);
 assert.equal(await evaluate('document.activeElement.dataset.rejectionReason'),second.id);
 assert.match(await evaluate('document.querySelector('+JSON.stringify(reasonFor(second.id))+').validationMessage'),/500/);
 assert.equal((await state()).pending.length,1);
 const approved=await action(approveFor(second.id));
 const sentApproval=(await calls()).at(-1);
 assert.deepEqual(sentApproval.payload,{action_id:second.id});
 assert.equal(approved.pending.length,0);
 assert.equal(approved.ledger.find(row=>row.invoice_id===second.invoice_id).status,'SENT');
 assert.equal(await evaluate('document.querySelectorAll("textarea[data-rejection-reason]").length'),0);
 passed('501 Unicode characters refuse locally without consumption; the separate approval path ignores an unfinished rejection note');

 const invoice=approved.ledger.find(row=>row.invoice_id===second.invoice_id);
 const date=new Date(invoice.due_on+'T00:00:00Z');date.setUTCDate(date.getUTCDate()+2);
 const dueDay=date.toISOString().slice(0,10);
 await evaluate('document.querySelector("#demo-date").value='+JSON.stringify(dueDay));
 assert.equal(await value('#demo-date'),dueDay);
 await action('#advance-clock');
 const chased=await action('#run-chase');
 const reminder=chased.pending.find(row=>row.kind==='send_reminder');
 assert.ok(reminder);
 await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
 const reminderReason='Client asked for a pause.\nNo reminder this week.';
 await textInput(reasonFor(reminder.id),reminderReason);
 assert.equal(await evaluate('document.documentElement.scrollWidth>innerWidth'),false);
 await screenshot('phone-reminder-note.png');
 const reminderRejected=await action(rejectFor(reminder.id));
 assert.equal((await evaluate('window.__reasonProbe.replies.at(-1)')).result.reason,reminderReason);
 assert.equal(reminderRejected.mock_requests,chased.mock_requests);
 assert.deepEqual(reminderRejected.ledger,chased.ledger);
 passed('narrow-layout reminder note reaches the same real rejection path without sending the reminder');

 const single=await readFile(join(project,'fixtures/01_simple_usd_hourly.txt'),'utf8');
 const next=await draft(single);
 const defaultAction=next.pending[0];
 await action(rejectFor(defaultAction.id));
 assert.equal((await evaluate('window.__reasonProbe.replies.at(-1)')).result.reason,'Rejected by the browser visitor');
 const last=await draft(single.replaceAll('Maya','Rina').replaceAll('maya.chen','rina.chen'));
 const lastId=last.pending[0].id;
 await textInput(reasonFor(lastId),'Draft note before an explicit reset');
 await action('#reset-sandbox');
 assert.equal((await state()).pending.length,0);
 assert.equal(await evaluate('document.querySelectorAll("textarea[data-rejection-reason]").length'),0);
 assert.equal(await evaluate('document.querySelector("#job-email").value'),'');
 passed('empty note keeps the legacy reason; explicit reset clears action-bound notes and sandbox state');

 report.workerCalls=await calls();
 report.workerReplies=await evaluate('window.__reasonProbe.replies');
 assert.ok(report.workerReplies.every(reply=>reply.state.external_calls===0));
 assert.deepEqual(report.externalRequests,[]);
 assert.ok(report.requests.every(request=>request.method==='GET'&&(
  new URL(request.url).origin===base||request.url.startsWith('data:image/svg+xml;base64,'))),
  'observed page and Worker HTTP requests stay local; embedded browser SVG resources make no network request');
 report.embeddedBrowserResources=report.requests.filter(request=>request.url.startsWith('data:image/svg+xml;base64,'));
 assert.deepEqual(pageErrors,[]);
 assert.ok(report.serverRequests.every(request=>request.method==='GET'));
 await screenshot('completed-reset.png');
 report.status='passed';
}catch(error){
 report.status='failed';report.error=error.stack??String(error);process.exitCode=1;
 try{if(socket&&sessionId)await screenshot('failed-state.png');}catch{}
 console.error(report.error);
}finally{
 report.browserLog=browserLog;
 try{if(socket?.readyState===WebSocket.OPEN)await command('Browser.close',{},false);}catch{}
 socket?.close();for(const request of pending.values())clearTimeout(request.timer);
 if(browser&&browser.exitCode===null)browser.kill('SIGTERM');
 server.closeAllConnections();await new Promise(resolve_=>server.close(resolve_));
 await sleep(300);
 await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
 report.sourceAfter=await sourceHashes();
 report.sourceUnchanged=JSON.stringify(report.sourceAfter)===JSON.stringify(sourceBefore);
 if(!report.sourceUnchanged){report.status='failed';process.exitCode=1;}
 report.pageErrors=pageErrors;
 const bytes=Buffer.from(JSON.stringify(report,null,2)+'\n');
 assert.ok(bytes.length+report.artifacts.reduce((sum,item)=>sum+item.bytes,0)<33554432,'bounded retained browser output');
 await writeFile(join(output,'browser-results.json'),bytes);
 console.log('REJECTION_REASON_BROWSER_RESULT '+JSON.stringify({status:report.status,checks:report.checks.length,
  sourceUnchanged:report.sourceUnchanged,reportBytes:bytes.length,reportSHA256:hash(bytes)}));
}
