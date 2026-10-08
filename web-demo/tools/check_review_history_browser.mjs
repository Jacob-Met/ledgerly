#!/usr/bin/env node
/** Node 22 and installed Chromium: actual UI, Worker and Python receiving.
 * New output/profile only. A labeled fault changes only served bridge bytes.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn,execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir,mkdtemp,rm,readdir} from 'node:fs/promises';
import {join,resolve,extname} from 'node:path';
import {fileURLToPath} from 'node:url';
const options={};
for(let i=2;i<process.argv.length;i+=2){
 const key=process.argv[i];assert.ok(['--source','--dist','--chrome','--output','--source-manifest'].includes(key)&&process.argv[i+1]);
 options[key.slice(2)]=process.argv[i+1];
}
for(const key of ['source','dist','chrome','output'])assert.ok(options[key],key);
const source=resolve(options.source),dist=resolve(options.dist),output=resolve(options.output);
await mkdir(output);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function checkoutBinding(){
 const sourcePin=execFileSync('git',['-C',source,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
 const raw=execFileSync('git',['-C',source,'ls-tree','-rz','HEAD','--','ledgerly','fixtures','web-demo/src',
  'web-demo/python','web-demo/index.html','web-demo/package.json','web-demo/package-lock.json',
  'web-demo/vite.config.ts','web-demo/tsconfig.json','web-demo/scripts/stage-python.mjs'],{encoding:'utf8'});
 const files=raw.split('\0').filter(Boolean).map(line=>{
  const [header,path]=line.split('\t'),[mode,type,git_blob]=header.split(' ');
  return {path,mode,type,git_blob};
 }).filter(row=>row.type==='blob'&&!row.path.includes('__pycache__'));
 return {schema:'hamon.ledgerly.history-source-binding.v1',source_pin:sourcePin,scope:'Tracked application inputs from this exact checkout',files};
}
const bindingBytes=options['source-manifest']?await readFile(options['source-manifest']):
 Buffer.from(JSON.stringify(checkoutBinding(),null,2)+'\n');
const binding=JSON.parse(bindingBytes);
const observer="\nwindow.__historyObservation = {sent: [], received: [], workerCount: 0};\nwindow.__historyWorkers = [];\nconst NativeWorker = window.Worker;\nwindow.Worker = class extends NativeWorker {\n  constructor(url, options) {\n    super(url, options);\n    window.__historyWorkers.push(this);\n    window.__historyObservation.workerCount++;\n    this.addEventListener('message', event => {\n      window.__historyObservation.received.push(structuredClone(event.data));\n    });\n  }\n  postMessage(message, ...rest) {\n    window.__historyObservation.sent.push(structuredClone(message));\n    return super.postMessage(message, ...rest);\n  }\n};\n";
const faultSuffix="\n# Receiving-only injection: the real mock send succeeds before its response is lost.\n_history_original_handle_json = handle_json\n_history_lost_response_used = False\ndef handle_json(raw):\n    global _history_lost_response_used\n    request = json.loads(raw)\n    if request.get(\"action\") != \"approve\" or _history_lost_response_used:\n        return _history_original_handle_json(raw)\n    _history_lost_response_used = True\n    original_send = SESSION.mock.send_invoice\n    def send_then_lose_response(*args, **kwargs):\n        original_send(*args, **kwargs)\n        raise TimeoutError(\"Receiving-only lost response after the real mock send\")\n    SESSION.mock.send_invoice = send_then_lose_response\n    try:\n        return _history_original_handle_json(raw)\n    finally:\n        SESSION.mock.send_invoice = original_send\n";
const report={format:'ledgerly-completed-review-receiving/1',startedAt:new Date().toISOString(),
 source,dist,sourcePin:binding.source_pin,bindingSha256:sha(bindingBytes),driverSha256:sha(await readFile(fileURLToPath(import.meta.url))),
 node:process.version,checks:[],pageErrors:[],offOrigin:[],networkRequests:[],attachedTargets:[],sourceFiles:{},distFiles:{},servedPython:{},screenshots:[],phases:[],
 fault:{kind:'Real SandboxMock send followed by authored lost response',bridgeServed:0,suffixSha256:sha(Buffer.from(faultSuffix))},
 bounds:['Declared source inputs are Git-blob bound; this is not a full checkout.',
 'Actual Worker construction, requests, and Python replies remain in use.',
 'Page requests use Fetch interception. Worker requests use Network observation; served worker scripts enforce connect-src self through CSP.',
 'The failure context serves exact bridge bytes plus the recorded receiving-only suffix.',
 'Unavailability is an authored ErrorEvent on the actual Worker, not a spontaneous crash.'],ok:false};
for(const row of binding.files){
 const bytes=await readFile(join(source,row.path));
 assert.equal(createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex'),row.git_blob,row.path);
 report.sourceFiles[row.path]=sha(bytes);
}
async function walk(path,prefix=''){
 for(const entry of await readdir(path,{withFileTypes:true})){
  const name=prefix+entry.name,child=join(path,entry.name);
  if(entry.isDirectory())await walk(child,name+'/');else if(entry.isFile())report.distFiles[name]=sha(await readFile(child));
 }
}
await walk(dist);
const pythonAssets={'python/ledgerly/__init__.py':'ledgerly/__init__.py',
 'python/ledgerly/agent.py':'ledgerly/agent.py','python/ledgerly/extract.py':'ledgerly/extract.py',
 'python/ledgerly/paypal.py':'ledgerly/paypal.py','python/bridge.py':'web-demo/python/bridge.py',
 'python/review.py':'web-demo/python/review.py','python/invoice_details.py':'web-demo/python/invoice_details.py',
 'python/review_history.py':'web-demo/python/review_history.py'};
for(const [asset,path] of Object.entries(pythonAssets))assert.equal(report.distFiles[asset],report.sourceFiles[path],asset+' binds actual source');
await writeFile(join(output,'source-binding.json'),bindingBytes,{flag:'wx'});
await writeFile(join(output,'lost-response-suffix.py'),faultSuffix,{flag:'wx'});
async function save(){await writeFile(join(output,'browser.json'),JSON.stringify(report,null,2)+'\n');}
async function emitBundle(){
 if(process.env.LEDGERLY_HISTORY_EMIT_BUNDLE!=='1')return;
 // Only this exclusive output's top-level regular receipts and captures; never profiles or links.
 const files=[];let total=0;
 for(const entry of (await readdir(output,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))){
  if(!entry.isFile())continue;
  assert.match(entry.name,/^[A-Za-z0-9._-]+$/);
  const bytes=await readFile(join(output,entry.name));total+=bytes.length;
  assert.ok(total<=8*1024*1024,'receiving bundle exceeds bounded 8 MiB raw size');
  const encoded=bytes.toString('base64'),chunks=[];
  for(let at=0;at<encoded.length;at+=4096)chunks.push(encoded.slice(at,at+4096));
  files.push({name:entry.name,bytes:bytes.length,sha256:sha(bytes),
   git_blob:createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex'),chunks});
 }
 const manifest=JSON.stringify({format:'ledgerly-history-log-bundle/1',rawBytes:total,
  files:files.map(({chunks,...item})=>({...item,chunks:chunks.length}))});
 console.log('LEDGERLY_HISTORY_BUNDLE_BEGIN '+manifest);
 for(const file of files)for(let i=0;i<file.chunks.length;i++)
  console.log('LEDGERLY_HISTORY_DATA '+file.name+' '+i+'/'+file.chunks.length+' '+file.chunks[i]);
 console.log('LEDGERLY_HISTORY_BUNDLE_END '+sha(Buffer.from(manifest)));
}
async function check(name,condition=true,detail){
 report.checks.push({name,passed:Boolean(condition),...(detail===undefined?{}:{detail})});
 await save();assert.ok(condition,name);console.log('PASS '+name);
}
let phase='healthy';
const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.wasm':'application/wasm',
 '.json':'application/json','.py':'text/plain','.txt':'text/plain','.zip':'application/zip','.png':'image/png'};
const server=createServer(async(req,res)=>{
 try{
  const name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).replace(/^\/+/,'')||'index.html';
  const path=resolve(dist,name);assert.ok(path.startsWith(dist+'/'));
  let bytes=await readFile(path);
  if(name.startsWith('python/')&&name.endsWith('.py'))report.servedPython[phase+':'+name]=sha(bytes);
  if(name==='python/bridge.py'&&phase==='lost-response'){
   report.fault.bridgeServed++;report.fault.originalBridgeSha256=sha(bytes);
   bytes=Buffer.concat([bytes,Buffer.from(faultSuffix)]);report.fault.servedBridgeSha256=sha(bytes);
  }
  res.writeHead(200,{'Content-Type':mime[extname(path)]||'application/octet-stream','Cache-Control':'no-store',
   'Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' blob:; worker-src 'self' blob:; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:"});
  res.end(bytes);
 }catch{res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='http://127.0.0.1:'+server.address().port;report.origin=origin;
class Browser{
 constructor(label){this.label=label;this.seq=0;this.pending=new Map();this.log='';this.asyncErrors=[];this.acceptDialog=false;}
 command(method,params={},session=this.session){
  const id=++this.seq;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('CDP timeout '+method));},20000);
   this.pending.set(id,{resolve,reject,timer});
   this.socket.send(JSON.stringify({id,method,params,...(session?{sessionId:session}:{})}));
  });
 }
 async evaluate(expression){
  const out=await this.command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(out.exceptionDetails)throw new Error(out.exceptionDetails.exception?.description||out.exceptionDetails.text);
  return out.result.value;
 }
 async waitFor(fn,label,timeout=60000){
  const deadline=Date.now()+timeout;let error;
  while(Date.now()<deadline){if(this.asyncErrors.length)throw new Error(this.asyncErrors.join('\n'));
   try{if(await fn())return;}catch(e){error=e;}await sleep(100);}
  throw new Error('Timed out '+label+(error?': '+error.message:''));
 }
 async key(name){
  const code={Enter:13,Tab:9,Escape:27}[name];
  for(const type of ['keyDown','keyUp'])await this.command('Input.dispatchKeyEvent',
   {type,key:name,code:name,windowsVirtualKeyCode:code,nativeVirtualKeyCode:code,
    ...(name==='Enter'&&type==='keyDown'?{text:'\r',unmodifiedText:'\r'}:{})});
 }
 async activate(selector){
  assert.ok(await this.evaluate('!!document.querySelector('+JSON.stringify(selector)+')'),'Missing '+selector);
  await this.evaluate('document.querySelector('+JSON.stringify(selector)+').focus()');await this.key('Enter');
 }
 async fill(selector,value){
  await this.evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.focus();e.select();})()');
  await this.command('Input.insertText',{text:value});
 }
 async select(selector,value){
  await this.evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.value='+JSON.stringify(value)+';e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}));})()');
 }
 async idle(){await this.waitFor(()=>this.evaluate('!document.querySelector("#job-email").disabled'),'UI idle');}
 async action(selector){await this.activate(selector);await this.idle();}
 async state(){return this.evaluate('window.__historyObservation.received.filter(x=>x.data?.state).at(-1).data.state');}
 async messages(){return this.evaluate('window.__historyObservation.sent.length');}
 async text(selector){return this.evaluate('document.querySelector('+JSON.stringify(selector)+').textContent');}
 async count(selector){return this.evaluate('document.querySelectorAll('+JSON.stringify(selector)+').length');}
 async visible(selector){return this.evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e)return false;const r=e.getBoundingClientRect();return e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight;})()');}
 async capture(name,selector){
  const clip=await this.evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.scrollIntoView({block:"start"});const r=e.getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1};})()');
  const {data}=await this.command('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip});
  const bytes=Buffer.from(data,'base64');await writeFile(join(output,name),bytes,{flag:'wx'});
  report.screenshots.push({path:name,bytes:bytes.length,sha256:sha(bytes)});
 }
 async launch(){
  this.profile=await mkdtemp(join(output,'profile-'+this.label+'-'));
  this.child=spawn(options.chrome,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking',
   '--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check',
   '--disk-cache-size=1048576','--media-cache-size=1048576','--remote-debugging-address=127.0.0.1',
   '--remote-debugging-port=0','--user-data-dir='+this.profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
  this.child.stderr.on('data',data=>{this.log=(this.log+data).slice(-24000);});
  let launchError;this.child.on('error',e=>{launchError=e;});let port,endpoint;
  await this.waitFor(async()=>{
   if(launchError)throw launchError;if(this.child.exitCode!==null)throw new Error('Browser exited '+this.child.exitCode+': '+this.log);
   [port,endpoint]=(await readFile(join(this.profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return Boolean(port&&endpoint);
  },'Chromium startup',20000);
  this.socket=new WebSocket('ws://127.0.0.1:'+port+endpoint);
  this.socket.addEventListener('message',event=>{
   const m=JSON.parse(event.data);
   if(m.id){const p=this.pending.get(m.id);if(!p)return;this.pending.delete(m.id);clearTimeout(p.timer);
    if(m.error)p.reject(new Error(m.error.message));else p.resolve(m.result);
   }else if(m.method==='Runtime.exceptionThrown'){
    report.pageErrors.push({phase:this.label,error:m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text});
   }else if(m.method==='Target.attachedToTarget'){
    const session=m.params.sessionId,type=m.params.targetInfo.type;
    report.attachedTargets.push({phase:this.label,sessionId:session,type,url:m.params.targetInfo.url});
    if(type==='worker'){
     // Worker targets expose Network, but not the page Fetch interception domain.
     // The served worker response has the same-origin connect-src CSP; observe every request before resuming it.
     (async()=>{await this.command('Runtime.enable',{},session);await this.command('Network.enable',{},session);
      await this.command('Runtime.runIfWaitingForDebugger',{},session);
     })().catch(e=>this.asyncErrors.push(e.message));
    }
   }else if(m.method==='Network.requestWillBeSent'){
    const url=m.params.request.url;
    report.networkRequests.push({phase:this.label,sessionId:m.sessionId,url,type:m.params.type});
    if(!url.startsWith(origin+'/')&&!url.startsWith('data:')&&!url.startsWith('blob:'))
     report.offOrigin.push({phase:this.label,url,observedBy:'Network'});
   }else if(m.method==='Fetch.requestPaused'){
    const url=m.params.request.url,allowed=url.startsWith(origin+'/')||url.startsWith('data:')||url.startsWith('blob:');
    if(!allowed)report.offOrigin.push({phase:this.label,url});
    this.command(allowed?'Fetch.continueRequest':'Fetch.failRequest',
     {requestId:m.params.requestId,...(!allowed?{errorReason:'BlockedByClient'}:{})},m.sessionId)
     .catch(e=>this.asyncErrors.push(e.message));
   }else if(m.method==='Page.javascriptDialogOpening'){
    report.dialog={type:m.params.type,message:m.params.message,accepted:this.acceptDialog};
    this.command('Page.handleJavaScriptDialog',{accept:this.acceptDialog},m.sessionId).catch(e=>this.asyncErrors.push(e.message));
   }
  });
  await new Promise((r,j)=>{this.socket.addEventListener('open',r,{once:true});this.socket.addEventListener('error',j,{once:true});});
  this.version=await this.command('Browser.getVersion',{},null);
  const {targetId}=await this.command('Target.createTarget',{url:'about:blank'},null);this.targetId=targetId;
  this.session=(await this.command('Target.attachToTarget',{targetId,flatten:true},null)).sessionId;
  for(const method of ['Page.enable','Runtime.enable','Network.enable'])await this.command(method);
  await this.command('Fetch.enable',{patterns:[{urlPattern:'*'}]});
  await this.command('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:true,flatten:true});
  await this.command('Page.addScriptToEvaluateOnNewDocument',{source:observer});
  await this.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await this.command('Page.navigate',{url:origin+'/'});
  await this.waitFor(()=>this.evaluate('document.readyState==="complete"&&!!document.querySelector("#engine-start")'),'app');
  await this.activate('#engine-start');
  await this.waitFor(()=>this.evaluate('document.querySelector("#engine-status").textContent==="PYTHON READY / OFFLINE"'),'real Python ready',90000);
 }
 async close(){
  if(this.closed)return;this.closed=true;
  const cleanup={phase:this.label,pid:this.child?.pid,requestedClose:false,fallbackSignals:[],profileRemoved:false};
  try{if(this.socket?.readyState===WebSocket.OPEN){await this.command('Browser.close',{},null);cleanup.requestedClose=true;}}catch{}
  if(this.child){const exited=()=>this.child.exitCode!==null||this.child.signalCode!==null;
   for(let i=0;i<30&&!exited();i++)await sleep(100);
   if(!exited()){cleanup.fallbackSignals.push('SIGTERM');this.child.kill('SIGTERM');for(let i=0;i<20&&!exited();i++)await sleep(100);}
   if(!exited()){cleanup.fallbackSignals.push('SIGKILL');this.child.kill('SIGKILL');await this.waitFor(exited,'owned browser exit',5000);}
  }
  this.socket?.close();
  for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error('Receiver closed'));}
  this.pending.clear();
  if(this.profile){await rm(this.profile,{recursive:true,maxRetries:5,retryDelay:100});cleanup.profileRemoved=true;}
  cleanup.exitCode=this.child?.exitCode;cleanup.signal=this.child?.signalCode;
  (report.cleanup??=[]).push(cleanup);
  await writeFile(join(output,this.label+'-chromium.log'),this.log,{flag:'wx'});
 }
}
const s=q=>'document.querySelector('+JSON.stringify(q)+')';
const history=id=>'details.completed-review[data-review-id="'+id+'"]';
async function fixture(b,name){await b.select('#fixture-select',name);await b.action('#load-fixture');await b.action('#analyze');}
async function row(b,id){return (await b.state()).completed_reviews.find(r=>r.id===id);}
async function proposal(b,queued,status){
 const r=await row(b,queued.id),q=history(queued.id);
 await check('retained original '+status.toLowerCase(),r?.status===status&&JSON.stringify(r.payload)===JSON.stringify(queued.payload)&&r.created_at===queued.created_at,{actionId:queued.id});
 if(!await b.evaluate(s(q)+'.open'))await b.activate(q+' > summary');
 assert.ok((await b.text(q)).includes(queued.created_at));assert.ok((await b.text(q)).includes('Queued at'));
 assert.deepEqual(JSON.parse(await b.text(q+' [data-review-result]')),r.result);
 assert.equal(await b.count(q+' button,'+q+' a,'+q+' [data-approve],'+q+' [data-reject],'+q+' [data-pay]'),0);
 return q;
}
async function focusSnapshot(b,id,nested){
 const before=await b.state(),count=await b.messages(),args=JSON.stringify({id,nested});
 const prior=await b.evaluate('(({id,nested})=>{const outer=[...document.querySelectorAll("details.completed-review")].find(x=>x.dataset.reviewId===id);outer.open=true;const target=nested?outer.querySelector("details.approval-preview"):outer;const summary=target.querySelector(":scope > summary");if(nested){target.open=true;summary.click();}summary.focus();const before={outerOpen:outer.open,targetOpen:target.open,focused:document.activeElement===summary};document.querySelector("#analyze").click();return before;})('+args+')');
 await b.idle();
 const after=await b.evaluate('(({id,nested})=>{const outer=[...document.querySelectorAll("details.completed-review")].find(x=>x.dataset.reviewId===id);const target=nested?outer.querySelector("details.approval-preview"):outer;return {outerOpen:outer.open,targetOpen:target.open,focused:document.activeElement===target.querySelector(":scope > summary")};})('+args+')');
 const current=await b.state();
 await check((nested?'nested':'outer')+' disclosure and focus survive immediate snapshot',
  prior.focused&&after.outerOpen&&after.focused&&after.targetOpen===prior.targetOpen
  &&await b.messages()===count+1&&current.mock_requests===before.mock_requests
  &&JSON.stringify(current.completed_reviews)===JSON.stringify(before.completed_reviews),
  {before:prior,after,workerMessagesBefore:count,workerMessagesAfter:await b.messages()});
}
let current;
try{
 for(phase of ['healthy','lost-response']){
  const b=current=new Browser(phase);
  try{
   await b.launch();report.phases.push({name:phase,pid:b.child.pid,browser:b.version});
   let state=await b.state();
   await check(phase+' actual empty Python session',state.completed_reviews.length===0&&state.external_calls===0);
   await fixture(b,'01_simple_usd_hourly.txt');await b.action('#draft');
   state=await b.state();const queued=state.pending[0];
   await check(phase+' pending stays out of history',state.completed_reviews.length===0&&queued.kind==='send_invoice');
   await b.action('[data-approve="'+queued.id+'"]');
   if(phase==='lost-response'){
    state=await b.state();const closed=await row(b,queued.id);
    const provider=state.invoice_details.find(x=>x.invoice_id===queued.invoice_id).record;
    const ledger=state.ledger.find(x=>x.invoice_id===queued.invoice_id);
    await check('real send then lost response reaches FAILED UNKNOWN',
     closed.status==='FAILED'&&closed.result.outcome==='UNKNOWN'&&closed.result.error_type==='TimeoutError'
     &&provider.status==='SENT'&&ledger.status==='DRAFT'&&state.pending.length===0,
     {actionId:queued.id,recordedResult:closed.result,mockStatus:provider.status,ledgerStatus:ledger.status});
    const q=history(queued.id),summary=q+' > summary';
    await b.evaluate(s(summary)+'.scrollIntoView({block:"center"})');
    await check('UNKNOWN label is visibly rendered while collapsed',
     (await b.text(summary)).includes('FAILED · OUTCOME UNKNOWN')&&!await b.evaluate(s(q)+'.open')&&await b.visible(summary));
    const before=await b.state(),count=await b.messages();await proposal(b,queued,'FAILED');
    assert.ok((await b.text(q)).includes('Check the invoice before creating another approval.'));
    assert.ok((await b.text(q)).includes(queued.payload.invoice.items[0].name));
    await b.command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await b.capture('phone-outcome-unknown.png',q);
    await check('reading FAILED history does not retry or change provider state',
     await b.messages()===count&&JSON.stringify(await b.state())===JSON.stringify(before)
     &&!await b.evaluate('document.documentElement.scrollWidth>innerWidth'));
    continue;
   }
   let q=await proposal(b,queued,'APPROVED');const invoice=queued.payload.invoice;
   assert.ok((await b.text(q)).includes(invoice.items[0].name));assert.ok((await b.text(q)).includes(invoice.items[0].unit_amount.value));
   let before=await b.state(),count=await b.messages();
   await b.activate(q+' > summary');await b.key('Enter');
   const selected=await b.evaluate('(()=>{const e='+s(q+' [data-review-result]')+';const r=document.createRange();r.selectNodeContents(e);const selection=getSelection();selection.removeAllRanges();selection.addRange(r);return selection.toString();})()');
   await b.evaluate('getSelection().removeAllRanges()');
   await check('keyboard disclosure and result selection are read only',
    JSON.stringify(JSON.parse(selected))===JSON.stringify((await row(b,queued.id)).result)
    &&JSON.stringify(await b.state())===JSON.stringify(before)&&await b.messages()===count);
   await focusSnapshot(b,queued.id,false);await focusSnapshot(b,queued.id,true);
   await b.activate(q+' details.approval-preview > summary');
   const sibling='details.invoice-details[data-invoice-detail-id="'+queued.invoice_id+'"]';await b.activate(sibling+' > summary');
   await check('existing invoice details remain independently usable',
    await b.evaluate(s(sibling)+'.open')&&(await b.text(sibling)).includes(invoice.items[0].name));
   await fixture(b,'05_missing_email.txt');await b.activate('#review-editor > summary');
   const name='Zoë <img src=x onerror=window.historyInjected=1>',description='Révision <script>literal()</script> — خدمة';
   for(const [selector,value] of [['#review-client-name',name],['#review-client-email','history-receiver@example.test'],
    ['#review-due-days','30'],['#review-amount-paid','0'],['#review-line-0-desc',description],
    ['#review-line-0-qty','1.50'],['#review-line-0-price','80.00'],['#review-line-0-unit','hours']])await b.fill(selector,value);
   await b.select('#review-line-0-currency','EUR');await b.evaluate('document.querySelector("#review-confirm").click()');
   await b.action('#review-check');assert.ok(await b.evaluate('!document.querySelector("#draft").disabled'));
   await b.action('#draft');const rejected=(await b.state()).pending[0];
   await b.action('[data-reject="'+rejected.id+'"]');q=await proposal(b,rejected,'REJECTED');
   const literalText=await b.text(q),item=rejected.payload.invoice.items[0];
   await check('reviewed literal fields and rejection reason stay exact',
    [name,description,item.unit_amount.currency_code+' '+item.unit_amount.value,item.quantity].every(x=>literalText.includes(x))
    &&await b.count(q+' img,'+q+' script,'+q+' svg')===0&&await b.evaluate('window.historyInjected')===undefined
    &&JSON.stringify((await row(b,rejected.id)).result)===JSON.stringify({reason:'Rejected by the browser visitor'}));
   const due=(await b.state()).ledger.find(x=>x.invoice_id===queued.invoice_id).due_on;
   const day=n=>new Date(Date.parse(due+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
   await b.select('#demo-date',day(1));await b.action('#advance-clock');await b.action('#run-chase');
   const reminder=(await b.state()).pending.find(x=>x.kind==='send_reminder');
   await b.select('#demo-date',day(2));const priorRequests=(await b.state()).mock_requests;
   await b.action('#advance-clock');q=await proposal(b,reminder,'REJECTED');
   await check('automatic rejection retains its original message and actual reason',
    (await row(b,reminder.id)).result.reason.startsWith('auto:')&&await b.text(q+' [data-preview-reminder-note]')===reminder.payload.note
    &&(await b.text(q)).includes(reminder.payload.subject)&&(await b.state()).mock_requests===priorRequests,
    {recordedResult:(await row(b,reminder.id)).result});
   await b.action('#run-chase');const finalReminder=(await b.state()).pending.find(x=>x.kind==='send_reminder');
   await b.action('[data-approve="'+finalReminder.id+'"]');q=await proposal(b,finalReminder,'APPROVED');
   await check('explicit reminder approval retains its separate identity',
    finalReminder.id!==reminder.id&&JSON.stringify((await row(b,finalReminder.id)).result)===JSON.stringify({reminded:true})
    &&(await b.state()).pending.length===0);
   await b.capture('desktop-completed-reviews.png','#completed-reviews-list');before=await b.state();count=await b.messages();
   await b.command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
   await b.capture('phone-completed-reminder.png',q);await b.capture('phone-literal-invoice.png',history(rejected.id));
   await check('phone history has no horizontal overflow or Worker effect',
    !await b.evaluate('document.documentElement.scrollWidth>innerWidth')&&await b.messages()===count
    &&JSON.stringify(await b.state())===JSON.stringify(before));
   const retained=(await b.state()).completed_reviews,sourceEmail=await b.evaluate('document.querySelector("#job-email").value');count=await b.messages();
   await b.evaluate('window.__historyWorkers.at(-1).dispatchEvent(new ErrorEvent("error",{message:"Authored receiving-only worker unavailable event"}))');
   assert.equal(await b.text('#engine-status'),'PYTHON UNAVAILABLE');assert.ok((await b.text('#completed-reviews-note')).includes('last received reviews'));
   await b.activate(q+' > summary');
   await check('authored unavailable event labels retained history without replay',
    await b.messages()===count&&JSON.stringify((await b.state()).completed_reviews)===JSON.stringify(retained)
    &&await b.evaluate('window.__historyObservation.workerCount')===1,{injection:'Synthetic ErrorEvent on actual Worker'});
   await b.activate('#engine-start');
   await b.waitFor(()=>b.evaluate('document.querySelector("#engine-status").textContent==="PYTHON READY / OFFLINE"'),'explicit restart',90000);
   state=await b.state();
   await check('explicit restart opens empty history and retains source email',
    state.completed_reviews.length===0&&state.ledger.length===0&&state.pending.length===0
    &&await b.evaluate('document.querySelector("#job-email").value')===sourceEmail
    &&await b.messages()===count+1&&await b.evaluate('window.__historyObservation.workerCount')===2);
   await fixture(b,'01_simple_usd_hourly.txt');await b.action('#draft');await b.action('[data-reject="'+(await b.state()).pending[0].id+'"]');
   await check('fresh session retains its own completed review',(await b.state()).completed_reviews.length===1);
   b.acceptDialog=true;await b.action('#reset-sandbox');b.acceptDialog=false;state=await b.state();
   await check('explicit confirmed Reset clears history',state.completed_reviews.length===0&&state.ledger.length===0
    &&(await b.text('#completed-reviews-list')).includes('No completed reviews')&&report.dialog?.accepted===true);
  }catch(error){
   try{if(b.socket?.readyState===WebSocket.OPEN)await b.capture(phase+'-failure.png','#completed-reviews-list');}catch(e){report.captureError=String(e);}
   throw error;
  }finally{
   try{if(b.socket?.readyState===WebSocket.OPEN)await writeFile(join(output,phase+'-worker-observation.json'),
    JSON.stringify(await b.evaluate('window.__historyObservation'),null,2)+'\n',{flag:'wx'});
   }finally{try{await b.close();}finally{current=null;}}
  }
 }
 await check('both browser contexts requested the exact staged Python modules',
  ['healthy','lost-response'].every(label=>Object.entries(pythonAssets).every(([asset,path])=>report.servedPython[label+':'+asset]===report.sourceFiles[path])));
 await check('page and Worker requests remained on loopback',report.offOrigin.length===0
  &&['healthy','lost-response'].every(label=>report.attachedTargets.some(x=>x.phase===label&&x.type==='worker')
   &&report.networkRequests.some(x=>x.phase===label&&x.url===origin+'/python/bridge.py')));
 await check('no uncaught page or Worker exceptions',report.pageErrors.length===0);
 await check('exactly one labeled fault bridge served',report.fault.bridgeServed===1);
 await check('both owned browsers exited and profiles were removed',report.cleanup?.length===2&&report.cleanup.every(x=>x.exitCode===0&&x.signal===null&&x.profileRemoved));report.ok=true;
}catch(error){report.error=String(error);report.stack=error.stack;}
finally{
 if(current)await current.close().catch(error=>{report.cleanupError=String(error);});
 await new Promise(r=>server.close(r));report.sourceUnchanged=true;report.distUnchanged=true;
 for(const [path,digest] of Object.entries(report.sourceFiles))if(sha(await readFile(join(source,path)))!==digest)report.sourceUnchanged=false;
 for(const [path,digest] of Object.entries(report.distFiles))if(sha(await readFile(join(dist,path)))!==digest)report.distUnchanged=false;
 report.ok=report.ok&&report.sourceUnchanged&&report.distUnchanged&&!report.cleanupError;
 report.finishedAt=new Date().toISOString();await save();
 try{await emitBundle();}catch(error){report.bundleError=String(error);report.ok=false;await save();}
 console.log(JSON.stringify({ok:report.ok,checks:report.checks.length,sourceUnchanged:report.sourceUnchanged,distUnchanged:report.distUnchanged,error:report.error,output}));
}
process.exitCode=report.ok?0:1;
