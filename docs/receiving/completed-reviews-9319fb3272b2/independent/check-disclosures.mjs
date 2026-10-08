#!/usr/bin/env node
/** Focused independent receiving: unchanged built Ledgerly, real Chromium/Worker. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir, mkdtemp, rm, readdir} from 'node:fs/promises';
import {dirname, join, resolve, extname, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const options={};
const args=process.argv.slice(2);
for(let i=0;i<args.length;i+=2){
  assert.ok(['--source','--dist','--binding','--browser','--output'].includes(args[i])&&args[i+1], 'Explicit source/dist/binding/browser/output required');
  options[args[i].slice(2)]=args[i+1];
}
for(const key of ['source','dist','binding','browser','output'])assert.ok(options[key],key);
const source=resolve(options.source),dist=resolve(options.dist),output=resolve(options.output);
await mkdir(output);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const bindingBytes=await readFile(options.binding),binding=JSON.parse(bindingBytes);
const report={schema:'ledgerly.history-disclosure-independent.v1',reviewer:'hamon-ultra-9319fb3272b2-20261008/native_capability',
 started_at:new Date().toISOString(),source,dist,source_pin:binding.source_pin,source_tree:binding.tree,
 binding_sha256:sha(bindingBytes),driver_sha256:sha(await readFile(fileURLToPath(import.meta.url))),
 node:process.version,status:'running',checks:[],page_errors:[],page_requests:[],served_requests:[],
 source_files:{},dist_files:{},bounds:[
 'Existing built application, an isolated loopback server and a fresh owned native Chromium profile.',
 'Real Worker construction, outgoing messages and actual replies are observed and delegated; no reply is fabricated.',
 'History focus is kept while a DOM-initiated Analyze action produces an ordinary real Worker snapshot.',
 'Only approved-history disclosure/focus is exercised here; no lost-response path, broad suite or live provider is run.',
 'Page-domain network observations are recorded; this receiver does not claim complete independent Worker network interception.',
 ]};
for(const f of binding.files){
 const data=await readFile(join(source,f.path));
 assert.equal(createHash('sha1').update(Buffer.concat([Buffer.from('blob '+data.length+'\0'),data])).digest('hex'),f.git_blob,f.path);
 report.source_files[f.path]=sha(data);
}
async function fileList(root,prefix=''){
 const files=[];
 for(const entry of await readdir(join(root,prefix),{withFileTypes:true})){
  const rel=join(prefix,entry.name);
  if(entry.isDirectory())files.push(...await fileList(root,rel));
  else if(entry.isFile())files.push(rel);
  else throw Error('Unexpected nonregular served entry '+rel);
 }
 return files.sort();
}
for(const f of await fileList(dist))report.dist_files[f]=sha(await readFile(join(dist,f)));
await writeFile(join(output,'source-binding.json'),bindingBytes,{flag:'wx'});
await writeFile(join(output,'review-history.ts'),await readFile(join(source,'web-demo/src/review-history.ts')),{flag:'wx'});
const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.py':'text/plain','.txt':'text/plain','.wasm':'application/wasm','.zip':'application/zip','.svg':'image/svg+xml'};
const server=createServer(async(req,res)=>{
 try{
  const path=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
  const file=resolve(dist,'.'+(path==='/'?'/index.html':path));
  if(!file.startsWith(dist+sep)){res.writeHead(403);res.end();return;}
  const bytes=await readFile(file);
  report.served_requests.push({path,bytes:bytes.length,sha256:sha(bytes)});
  res.writeHead(200,{'Content-Type':mime[extname(file)]||'application/octet-stream','Content-Length':bytes.length,'Cache-Control':'no-store'});
  res.end(bytes);
 }catch(error){res.writeHead(404);res.end('Not found');}
});
await new Promise((done,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',done);});
report.url='http://127.0.0.1:'+server.address().port+'/';
const profile=await mkdtemp(join(output,'profile-'));
report.profile_path=profile;
let browser,socket,sessionId,sequence=0,browserLog='',launchError;
const pending=new Map();
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
async function waitFor(test,label,attempts=400){
 let lastError;
 for(let i=0;i<attempts;i++){
  try{if(await test())return;}catch(error){lastError=error;}
  await sleep(100);
 }
 throw Error('Timed out: '+label+(lastError?' ('+lastError.message+')':''));
}
function command(method,params={},scoped=true){
 const id=++sequence;
 return new Promise((done,reject)=>{
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},10000);
  pending.set(id,{resolve:done,reject,timer});
  socket.send(JSON.stringify({id,method,params,...(scoped&&sessionId?{sessionId}:{})}));
 });
}
async function evaluate(expression){
 const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
 if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description??result.exceptionDetails.text);
 return result.result.value;
}
async function keyEnter(){
 for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13,...(type==='keyDown'?{text:'\r',unmodifiedText:'\r'}:{})});
}
async function activate(selector){
 assert.ok(await evaluate('!!document.querySelector('+JSON.stringify(selector)+')'),selector);
 await evaluate('document.querySelector('+JSON.stringify(selector)+').focus()');
 await keyEnter();
}
const observation=()=>evaluate('structuredClone(window.__historyObservation)');
const state=()=>evaluate('window.__historyObservation.received.filter(x=>x.data?.state).at(-1).data.state');
async function replies(){return evaluate('window.__historyObservation.received.filter(x=>x.data?.state).length');}
async function waitReply(count){await waitFor(()=>evaluate('window.__historyObservation.received.filter(x=>x.data?.state).length==='+count+'&&!document.querySelector("#job-email").disabled'),'real Worker snapshot '+count);}
async function action(selector){
 const count=await replies();
 await activate(selector);
 await waitReply(count+1);
}
function check(name,passed,details){report.checks.push({name,passed:Boolean(passed),details});}
async function capture(name){
 const shot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 const bytes=Buffer.from(shot.data,'base64');
 await writeFile(join(output,name),bytes,{flag:'wx'});
 report[name]={bytes:bytes.length,sha256:sha(bytes)};
}
const OBSERVER=`
window.__historyObservation={sent:[],received:[],workers:0};
const OriginalWorker=window.Worker;
window.Worker=class extends OriginalWorker{
 constructor(url,options){super(url,options);window.__historyObservation.workers++;
  this.addEventListener('message',event=>window.__historyObservation.received.push(structuredClone(event.data)));}
 postMessage(message,...rest){window.__historyObservation.sent.push(structuredClone(message));return super.postMessage(message,...rest);}
};
`;
try{
 browser=spawn(options.browser,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check','--disk-cache-size=1048576','--media-cache-size=1048576','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
 report.browser_pid=browser.pid;
 browser.stderr.on('data',data=>{browserLog=(browserLog+data.toString()).slice(-20000);});
 browser.on('error',error=>{launchError=error;});
 let port,endpoint;
 await waitFor(async()=>{if(launchError)throw launchError;if(browser.exitCode!==null)throw Error('Browser exited '+browser.exitCode);[port,endpoint]=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return Boolean(port&&endpoint);},'browser startup');
 socket=new WebSocket('ws://127.0.0.1:'+port+endpoint);
 socket.addEventListener('message',event=>{
  const message=JSON.parse(event.data);
  if(message.id){const request=pending.get(message.id);if(!request)return;pending.delete(message.id);clearTimeout(request.timer);message.error?request.reject(Error(message.error.message)):request.resolve(message.result);}
  else if(message.method==='Runtime.exceptionThrown')report.page_errors.push(message.params.exceptionDetails.exception?.description??message.params.exceptionDetails.text);
  else if(message.method==='Network.requestWillBeSent')report.page_requests.push({url:message.params.request.url,session:message.sessionId});
 });
 await new Promise((done,reject)=>{socket.addEventListener('open',done,{once:true});socket.addEventListener('error',reject,{once:true});});
 report.browser=await command('Browser.getVersion',{},false);
 const {targetId}=await command('Target.createTarget',{url:'about:blank'},false);
 ({sessionId}=await command('Target.attachToTarget',{targetId,flatten:true},false));
 await command('Page.enable');await command('Runtime.enable');await command('Network.enable');
 await command('Page.addScriptToEvaluateOnNewDocument',{source:OBSERVER});
 await command('Emulation.setDeviceMetricsOverride',{width:1200,height:900,deviceScaleFactor:1,mobile:false});
 await command('Page.navigate',{url:report.url});
 await waitFor(()=>evaluate('document.readyState==="complete"&&!!document.querySelector("#engine-start")'),'application loaded');
 await activate('#engine-start');
 await waitFor(()=>evaluate('document.querySelector("#engine-status").textContent==="PYTHON READY / OFFLINE"'),'real local Python engine');
 await waitReply(1);
 check('actual_empty_python_session',(await state()).completed_reviews.length===0);
 const fixture=await readFile(join(source,'fixtures/01_simple_usd_hourly.txt'),'utf8');
 await evaluate('document.querySelector("#fixture-select").value="01_simple_usd_hourly.txt"');
 await activate('#load-fixture');
 await waitFor(()=>evaluate('document.querySelector("#job-email").value.trim()==='+JSON.stringify(fixture.trim())),'fixture text loaded');
 await action('#analyze');
 await action('#draft');
 const queued=(await state()).pending[0];
 assert.equal(queued.kind,'send_invoice');
 await action('[data-approve="'+queued.id+'"]');
 const approved=await state();
 const retained=approved.completed_reviews.find(r=>r.id===queued.id);
 check('actual_approved_original_proposal_retained',retained?.status==='APPROVED'&&JSON.stringify(retained.payload)===JSON.stringify(queued.payload));
 const select='details.completed-review[data-review-id="'+queued.id+'"]';
 const beforeRead=await observation();
 await activate(select+' > summary');
 const afterRead=await observation();
 const openState=await evaluate('(()=>{const p=document.querySelector('+JSON.stringify(select)+');return {open:p.open,focused:document.activeElement===p.querySelector(":scope > summary"),buttons:p.querySelectorAll("button,a,[data-approve],[data-reject],[data-pay]").length};})()');
 check('keyboard_open_is_read_only',openState.open&&openState.focused&&openState.buttons===0&&JSON.stringify(beforeRead)===JSON.stringify(afterRead),openState);
 for(const nested of [false,true]){
  const count=await replies(),beforeState=await state(),beforeMessages=(await observation()).sent.length;
  const before=await evaluate('('+String(({id,nested})=>{
   const outer=[...document.querySelectorAll('details.completed-review')].find(p=>p.dataset.reviewId===id);
   outer.open=true;
   const target=nested?outer.querySelector('details.approval-preview'):outer;
   target.open=nested;
   const summary=target.querySelector(':scope > summary');
   summary.click();summary.focus();
   const prior={outer_open:outer.open,target_open:target.open,focused:document.activeElement===summary};
   document.querySelector('#analyze').click();
   return prior;
  })+')('+JSON.stringify({id:queued.id,nested})+')');
  await waitReply(count+1);
  const after=await evaluate('('+String(({id,nested})=>{
   const outer=[...document.querySelectorAll('details.completed-review')].find(p=>p.dataset.reviewId===id);
   const target=nested?outer.querySelector('details.approval-preview'):outer;
   const summary=target.querySelector(':scope > summary'),rect=summary.getBoundingClientRect();
   return {outer_open:outer.open,target_open:target.open,focused:document.activeElement===summary,
    summary_visible:summary.getClientRects().length>0&&getComputedStyle(summary).display!=='none'&&getComputedStyle(summary).visibility!=='hidden'&&rect.width>0&&rect.height>0,
    focused_tag:document.activeElement.tagName,focused_id:document.activeElement.id};
  })+')('+JSON.stringify({id:queued.id,nested})+')');
  const afterState=await state(),afterMessages=(await observation()).sent.length;
  check(nested?'nested_disclosure_and_focus_survive_snapshot':'outer_disclosure_and_focus_survive_snapshot',
   before.focused&&after.focused&&after.summary_visible&&after.outer_open===before.outer_open&&after.target_open===before.target_open,
   {before,after,worker_messages_before:beforeMessages,worker_messages_after:afterMessages});
  check(nested?'nested_snapshot_has_only_requested_analysis':'outer_snapshot_has_only_requested_analysis',
   afterMessages===beforeMessages+1&&JSON.stringify(beforeState)===JSON.stringify(afterState),
   {mock_requests_before:beforeState.mock_requests,mock_requests_after:afterState.mock_requests});
 }
 await evaluate('document.querySelector('+JSON.stringify(select)+').scrollIntoView({block:"start"})');
 await capture('disclosure-after-snapshots.png');
 report.worker_observation=await observation();
 check('no_uncaught_page_errors',report.page_errors.length===0);
 report.status=report.checks.every(x=>x.passed)?'passed':'failed';
}catch(error){report.status='failed';report.error=error.stack||String(error);}
finally{
 for(const [path,digest]of Object.entries(report.source_files))if(sha(await readFile(join(source,path)))!==digest){report.source_changed=path;report.status='failed';}
 for(const [path,digest]of Object.entries(report.dist_files))if(sha(await readFile(join(dist,path)))!==digest){report.dist_changed=path;report.status='failed';}
 report.source_unchanged=!report.source_changed;report.dist_unchanged=!report.dist_changed;
 for(const request of pending.values()){clearTimeout(request.timer);request.reject(Error('Receiving browser closed'));}pending.clear();
 if(socket?.readyState===WebSocket.OPEN&&browser?.exitCode===null&&browser?.signalCode===null){
  const closed=new Promise(done=>browser.once('exit',done));
  try{socket.send(JSON.stringify({id:++sequence,method:'Browser.close',params:{}}));report.graceful_close_requested=true;await Promise.race([closed,sleep(4000)]);}catch(error){report.graceful_close_error=String(error);}
 }
 socket?.close();
 if(browser&&browser.exitCode===null&&browser.signalCode===null){const closed=new Promise(done=>browser.once('exit',done));browser.kill('SIGTERM');await Promise.race([closed,sleep(4000)]);if(browser.exitCode===null&&browser.signalCode===null){browser.kill('SIGKILL');await Promise.race([closed,sleep(1000)]);}}
 report.browser_exit={code:browser?.exitCode,signal:browser?.signalCode};
 try{await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:100});report.profile_removed=true;}catch(error){report.profile_removed=false;report.cleanup_error=String(error);report.status='failed';}
 await new Promise(done=>server.close(done));
 report.finished_at=new Date().toISOString();
 await writeFile(join(output,'browser.stderr.log'),browserLog,{flag:'wx'});
 const receipt=Buffer.from(JSON.stringify(report,null,2)+'\n');
 await writeFile(join(output,'receiving.json'),receipt,{flag:'wx'});
 console.log(JSON.stringify({status:report.status,checks:report.checks.length,failed:report.checks.filter(x=>!x.passed),error:report.error,source_unchanged:report.source_unchanged,dist_unchanged:report.dist_unchanged,browser_exit:report.browser_exit,profile_removed:report.profile_removed,receipt:join(output,'receiving.json'),sha256:sha(receipt)}));
 process.exitCode=report.status==='passed'?0:1;
}
