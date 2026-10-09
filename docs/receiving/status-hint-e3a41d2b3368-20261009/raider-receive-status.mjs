// Raider adaptation: current edc registration and runtime pins; prior public evidence is an immutable source reference.
// New status-only receiving derived from the exact retained Windows public driver.
// This does not replay the old public groups or make any public request.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,existsSync,rmSync,statfsSync,openSync,readSync,closeSync} from 'node:fs';
import {resolve,dirname,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {freemem,cpus} from 'node:os';
const root=dirname(fileURLToPath(import.meta.url)),build=resolve(root,'dist');
const chrome='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const historicalPublicEvidence={repository:'Jacob-Met/ledgerly',commit:'ac4ee6a5c3c7a20e28c44a7a6f973ea62da50c06',nativeDevice:'DESKTOP-LA7CMTA',scope:'Immutable historical source references only. No original-public or LA7 file access occurs on this receiver.'};
const runtimePins={'C:\\Program Files\\nodejs\\node.exe':'63c259c81e5d472b5f11c8d506070130cb04a1ecf84b80377a34ed6ec9048088','C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe':'977d6483df6c457eab24a3241b44645c66067f52b73bc2c8dbd7e6469bf15d1f'};
const originalPins={'receive-public.mjs':'ddb7673c1d3b4c622151a66c6f10ac4939b5dcfc27390a5fbfb4d8cd524f2a90','ACCEPTANCE.json':'731ec7f8ac24ed231877c3f676b6418b04c1dbfea86eaa6b45e736b8573d6864','ADMISSION.json':'3a8d2ef82d46179734a229f07efe6f42a9c89dc4913cbdaf6a81c179fc9258bc'};
const sourcePins={'source/main.ts':'f478fa3ccbf8d0f75e4a150a23e13fcb6acf8656608944e9584fb3bdd6e5d34c','source/engine-recovery.test.ts':'03a250b265a1b570fb04ad662e689fe196551053033a02cc92592393c0198339'};
const sha=b=>createHash('sha256').update(b).digest('hex');
function fileSha(path){const fd=openSync(path,'r'),buffer=Buffer.alloc(65536),hash=createHash('sha256');try{let n;while((n=readSync(fd,buffer,0,buffer.length,null))>0)hash.update(buffer.subarray(0,n));return hash.digest('hex');}finally{closeSync(fd);}}
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
const sourceText='Subject: Fictional receiving example - logo work\n\n3 x Logo concepts @ $250 each\n1 x Brand colour guide @ $180\n\nPlease invoice within 7 days. This is fictional test input, with no recipient email.\n';
const referenceBytes=readFileSync(resolve(root,'BUILD-MANIFEST.json'));
assert.equal(sha(referenceBytes),'af1676d4f243a56be6921c2b1a6706947f8d3bdc654c7b671bba8b556f4186da');
const manifest=JSON.parse(referenceBytes);
const reference={assets:Object.fromEntries(manifest.map(x=>[x.path,x.sha256])),source_merge:'ada2658b0291f094d4786aeec346b072fe357be4',source_tree:'b66e37bcae50c8493f137631f38d92044e59b808',qualified_head:'ada2658b0291f094d4786aeec346b072fe357be4'};
assert.equal(manifest.length,31);assert.equal(Object.keys(reference.assets).length,31);
for(const f of manifest){
 assert(/^[A-Za-z0-9_.\/-]+$/.test(f.path)&&!f.path.split('/').includes('..'));
 const bytes=readFileSync(resolve(build,f.path));assert.equal(bytes.length,f.bytes);assert.equal(sha(bytes),f.sha256);
}
for(const[p,h]of Object.entries(sourcePins))assert.equal(sha(readFileSync(resolve(root,p))),h);
for(const[p,h]of Object.entries(runtimePins))assert.equal(fileSha(p),h,'Exact existing runtime '+p);
assert.equal(process.execPath.toLowerCase(),'c:\\program files\\nodejs\\node.exe');
assert.equal(process.version,'v24.14.0','Pinned existing Raider Node runtime');
if(process.argv[2]==='--validate-only'){
 assert.equal(process.argv.length,3);
 console.log(JSON.stringify({status:'native-preparation-valid',assets:31,sourceFiles:2,historicalPublicReferenceOnly:true,existingRuntimePins:2,node:process.version,browserInvocations:0,networkRequests:0}));process.exit(0);
}
assert.equal(process.argv[2],'--run');assert.equal(process.argv.length,3);
const allowedActions=new Set(['init','analyze','review']);
const stamp=new Date().toISOString().replace(/[-:.]/g,'');
const out=resolve(root,'run-'+stamp),downloads=resolve(out,'downloads'),inputs=resolve(out,'inputs'),profile=resolve(out,'profile');
mkdirSync(out);mkdirSync(downloads);mkdirSync(inputs);
const started=Date.now(),deadline=started+60000;
let fatal=null,browser,cdp,exited=false,exitInfo=null,browserLog='',sessionId,server,documentURL,baseURL;
const urls=new Map(),interceptionTasks=new Set();
const report={schema:'ledgerly.actual-native-status-hint/1',status:'running',started_at:new Date().toISOString(),source_commit:reference.source_merge,source_tree:reference.source_tree,referenceSha256:sha(referenceBytes),node:process.version,
 originalDriverSha256:originalPins['receive-public.mjs'],sourcePins,historicalPublicEvidence,originalPins,runtimePins,public_deployment:false,
 observer:'Passive copies of actual native Worker requests/replies, request-time DOM status and trusted input events. No synthetic Python reply, callback, file read or failure injection.',
 browserAssetBinding:'The known Windows page-target Fetch stream verifies actual page and worker HTTP response bodies before continuation; dedicated workers resume without duplicate network-domain observation.',
 targetAttachments:[],noInvoicesOrProviderActions:true,preflightAssets:[],browserAssets:[],serverRequests:[],groups:[],screenshots:[],networkRefusals:[],downloads:[],pageErrors:[],cleanup:{},preflightBound:false,sourceBound:false};
function save(name, value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value,null,2)+'\n');
  assert(bytes.length<=2*1024*1024,'Bounded receiving artifact '+name);writeFileSync(resolve(out,name), bytes, {flag:'wx'});
  return {name,bytes:bytes.length,sha256:sha(bytes)};
}
function guard() {
  if (fatal) throw fatal;
  if (Date.now() > deadline) throw Error('Bounded receiving deadline exceeded.');
}
async function until(fn, label, ms = 20000) {
  const end = Math.min(deadline, Date.now()+ms);
  while (Date.now()<end) { guard(); const value=await fn(); if(value)return value; await sleep(100); }
  throw Error('Timed out: '+label);
}
function group(name, details) { guard(); report.groups.push({name,status:'pass',details}); }
function checkBody(path, bytes) {
  const actual = sha(bytes), expected=reference.assets[path];
  if (actual !== expected) throw Error('NATIVE_ASSET_MISMATCH '+path+' expected='+expected+' actual='+actual);
  return actual;
}
async function fetchAsset(path) {
  guard();
  const url=path==='index.html'?documentURL.href:new URL(path,baseURL).href;
  const response=await fetch(url,{redirect:'manual',signal:AbortSignal.timeout(25000),cache:'no-store'});
  const rec={path,url,status:response.status,finalURL:response.url,
    etag:response.headers.get('etag'),lastModified:response.headers.get('last-modified'),
    contentType:response.headers.get('content-type'),date:response.headers.get('date')};
  report.preflightAssets.push(rec);
  assert.equal(response.status,200,'Public response must be successful without an unreviewed redirect: '+path);
  const chunks=[];let total=0;
  for await(const chunk of response.body) {
    total+=chunk.length;assert(total<=64*1024*1024,'Bounded native asset '+path);chunks.push(chunk);guard();
  }
  const bytes=Buffer.concat(chunks);rec.bytes=bytes.length;rec.sha256=sha(bytes);
  checkBody(path,bytes);
  if(path==='index.html') save('native-index.html',bytes);
}
class CDP {
  constructor(ws) {
    this.ws=ws;this.next=1;this.pending=new Map();this.events=[];
    ws.addEventListener('message',event=>{
      const message=JSON.parse(event.data);
      if(message.id) {
        const p=this.pending.get(message.id);if(!p)return;
        clearTimeout(p.timer);this.pending.delete(message.id);
        message.error?p.reject(Error(JSON.stringify(message.error))):p.resolve(message.result);
      } else {this.events.push(message);this.onEvent?.(message);}
    });
  }
  static async open(url) {
    const ws=new WebSocket(url);
    await new Promise((done,reject)=>{
      const timer=setTimeout(()=>reject(Error('Private CDP connection timeout')),10000);
      ws.addEventListener('open',()=>{clearTimeout(timer);done();},{once:true});
      ws.addEventListener('error',()=>{clearTimeout(timer);reject(Error('Private CDP connection failed'));},{once:true});
    });
    return new CDP(ws);
  }
  send(method,params={},sid) {
    const id=this.next++;
    return new Promise((done,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method));},15000);
      this.pending.set(id,{resolve:done,reject,timer});
      this.ws.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}));
    });
  }
  close(){this.ws.close();}
}
const observer='('+function(){
  const NativeWorker=window.Worker;
  const p=window.__publicIntake={calls:[],replies:[],states:[],events:[],requestStatuses:[]};
  window.Worker=class extends NativeWorker {
    constructor(...args){
      super(...args);
      this.addEventListener('message',event=>{
        if(event.data?.data){
          p.replies.push(JSON.parse(JSON.stringify(event.data)));
          if(event.data.data.state)p.states.push(JSON.parse(JSON.stringify(event.data.data.state)));
        }
      });
    }
    postMessage(...args){p.calls.push(JSON.parse(JSON.stringify(args[0])));p.requestStatuses.push({id:args[0]?.id,action:args[0]?.action,status:document.querySelector('#status-message')?.textContent,kind:document.querySelector('#status-message')?.dataset.kind});return super.postMessage(...args);}
  };
  for(const type of ['keydown','input','change'])document.addEventListener(type,event=>{
    if(event.isTrusted)p.events.push({type,key:event.key??null,id:event.target?.id??null,trusted:true});
  },true);
}.toString()+')()';
const fieldsExpression='(()=>{const f=document.querySelector("#review-form");if(!f)return null;const v=n=>f.elements.namedItem(n).value;return {client_name:v("client_name"),client_email:v("client_email"),due_days:v("due_days"),amount_paid:v("amount_paid"),line_items:[...f.querySelectorAll("[data-review-line]")].map(row=>Object.fromEntries(["desc","qty","unit_price","currency","unit"].map(k=>[k,row.querySelector("[data-field="+k+"]").value])))};})()';
let evaluate, send;
const calls=()=>evaluate('window.__publicIntake.calls');
const replies=()=>evaluate('window.__publicIntake.replies');
const snapshot=()=>evaluate('({source:document.querySelector("#job-email").value,fields:'+fieldsExpression+',confirmed:document.querySelector("#review-confirm")?.checked??false,draftDisabled:document.querySelector("#draft").disabled})');
async function focus(selector) {
  const ok=await evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e||e.disabled||!e.getClientRects().length)return false;e.scrollIntoView({block:"center"});e.focus();return document.activeElement===e;})()');
  assert(ok,'Available focused control '+selector);
}
async function key(key,code,keyCode,modifiers=0) {
  await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:keyCode,nativeVirtualKeyCode:keyCode,modifiers,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{}),...(key===' '?{text:' ',unmodifiedText:' '}:{})});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:keyCode,nativeVirtualKeyCode:keyCode,modifiers});
}
async function activate(selector){await focus(selector);await key('Enter','Enter',13);}
async function input(selector,value) {
  await focus(selector);await key('a','KeyA',65,2);await key('Backspace','Backspace',8);
  if(value)await send('Input.insertText',{text:value});
  assert.equal(await evaluate('document.querySelector('+JSON.stringify(selector)+').value'),value);
}
async function action(selector, expectedOK=true) {
  const before=(await replies()).length;
  await activate(selector);
  await until(()=>evaluate('window.__publicIntake.replies.length>'+before+'&&!document.querySelector("#analyze").disabled'),'real Python reply '+selector,90000);
  const reply=(await replies()).at(-1).data;assert.equal(reply.ok,expectedOK);return reply;
}
async function noRecords() {
  const states=await evaluate('window.__publicIntake.states');
  assert(states.length>0);
  for(const state of states){
    assert.deepEqual(state.ledger??[],[]);assert.deepEqual(state.pending??[],[]);
    assert.equal(state.external_calls??0,0);assert.equal(state.mock_requests??0,0);
  }
  assert((await calls()).every(call=>allowedActions.has(call.action)));
  assert.equal(await evaluate('document.querySelector("#external-calls").textContent'),'0');
}
async function screenshot(name) {
  const data=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  report.screenshots.push(save(name,Buffer.from(data.data,'base64')));
}
async function openFile(path,admit=true) {
  const before=cdp.events.length;
  await activate('#intake-open');
  await until(()=>cdp.events.slice(before).some(e=>e.sessionId===sessionId&&e.method==='Page.fileChooserOpened'),'real Open intake chooser');
  const dom=await send('DOM.getDocument',{depth:0});
  const {nodeId}=await send('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#intake-file'});
  assert(nodeId>0);await send('DOM.setFileInputFiles',{nodeId,files:[path]});
  if(admit)await until(()=>evaluate('!document.querySelector("#intake-preview").hidden'),'saved file preview');
  else await until(()=>evaluate('document.querySelector("#intake-file-status").textContent.includes("not valid JSON")'),'malformed file refusal');
}
async function replaceFile() {
  const before=(await calls()).length;
  await activate('#intake-replace');
  await until(()=>evaluate('document.querySelector("#intake-preview").hidden&&!document.querySelector("#analyze").disabled&&document.querySelector("#intake-file-status").textContent.includes("restored")'),'fresh replacement analysis',90000);
  assert.deepEqual((await calls()).slice(before).map(x=>x.action),['analyze']);
}
async function checkFields(expectedOK=true) {
  await focus('#review-confirm');
  if(!await evaluate('document.querySelector("#review-confirm").checked'))await key(' ','Space',32);
  return action('#review-check',expectedOK);
}
try{
 const disk=statfsSync(root),free=freemem();
 report.admission={freeBytes:disk.bavail*disk.bsize,freeMemory:free,cpus:cpus().length,memoryFloor:2*1024**3};
 assert(disk.bavail*disk.bsize>=256*1024**2);assert(free>=2*1024**3,'Fresh2GiB browser admission');
 server=createServer((req,res)=>{
  try{
   const u=new URL(req.url,'http://localhost'),match=decodeURIComponent(u.pathname).match(/^\/candidate\/(.*)$/);
   report.serverRequests.push({method:req.method,path:u.pathname});
   if(req.method!=='GET'||!match){res.writeHead(405).end();return;}
   const path=match[1]||'index.html';if(!Object.hasOwn(reference.assets,path)){res.writeHead(404).end();return;}
   const file=resolve(build,path);assert(file.startsWith(build+sep));
   const data=readFileSync(file);checkBody(path,data);
   const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.svg':'image/svg+xml','.zip':'application/zip'}[extname(file)]||'application/octet-stream';
   res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'}).end(data);
  }catch(error){fatal=error;res.writeHead(500).end('Native source binding failed');}
 });
 await new Promise(done=>server.listen(0,'127.0.0.1',done));
 documentURL=new URL('http://127.0.0.1:'+server.address().port+'/candidate/');baseURL=new URL('./',documentURL);
 for(const path of Object.keys(reference.assets))urls.set(new URL(path,baseURL).href,path);
 urls.set(documentURL.href,'index.html');report.localURL=documentURL.href;
 await fetchAsset('index.html');
 for(const path of Object.keys(reference.assets).filter(p=>p!=='index.html'))await fetchAsset(path);
 report.preflightBound=true;
  const args=['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-default-apps','--disable-sync','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'--window-size=1280,1000','about:blank'];
  assert(!existsSync(profile));
  report.browserCommand={executable:chrome,args};
  browser=spawn(chrome,args,{stdio:['ignore','pipe','pipe'],windowsHide:true});
  report.browserPid=browser.pid;
  browser.stdout.on('data',b=>{browserLog=(browserLog+b).slice(-32768);});browser.stderr.on('data',b=>{browserLog=(browserLog+b).slice(-32768);});
  browser.once('exit',(code,signal)=>{exited=true;exitInfo={code,signal};});
  browser.once('error',error=>{fatal=error;});
  const active=await until(()=>{const p=resolve(profile,'DevToolsActivePort');if(existsSync(p))return readFileSync(p,'utf8').trim().split(/\r?\n/);if(exited)throw Error('Chrome exited before private debugger admission');return null;},'private Chrome debugger',25000);
  cdp=await CDP.open('ws://127.0.0.1:'+active[0]+active[1]);
  report.browser=await cdp.send('Browser.getVersion');assert.equal(report.browser.product,'Chrome/154.0.8037.97','Actual existing Raider Chrome generation');
  await cdp.send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads,eventsEnabled:true});
  const {targetId}=await cdp.send('Target.createTarget',{url:'about:blank'});
  ({sessionId}=await cdp.send('Target.attachToTarget',{targetId,flatten:true}));
  send=(method,params={})=>{guard();return cdp.send(method,params,sessionId);};
  evaluate=async expression=>{
    const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(value.exceptionDetails)throw Error('Page evaluation: '+JSON.stringify(value.exceptionDetails));
    return value.result.value;
  };
  async function guardPage(sid) {
    await cdp.send('Network.enable',{},sid);
    await cdp.send('Network.setCacheDisabled',{cacheDisabled:true},sid);
    await cdp.send('Fetch.enable',{patterns:[{urlPattern:'http*',requestStage:'Request'},{urlPattern:'http*',requestStage:'Response'}]},sid);
  }
  async function intercept(event) {
    if(event.method==='Target.attachedToTarget'){
      const sid=event.params.sessionId;
      assert.equal(event.params.targetInfo.type,'worker','Only the expected dedicated worker is admitted.');
      report.targetAttachments.push({sessionId:sid,type:event.params.targetInfo.type,url:event.params.targetInfo.url});
      await cdp.send('Runtime.runIfWaitingForDebugger',{},sid);
      return;
    }
    if(event.method!=='Fetch.requestPaused')return;
    const p=event.params,sid=event.sessionId,path=urls.get(p.request.url);
    if(!path||p.request.method!=='GET'){
      report.networkRefusals.push({url:p.request.url,method:p.request.method});
      await cdp.send('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'},sid);
      throw Error('Unqualified native request refused: '+p.request.url);
    }
    if(p.responseStatusCode!==undefined){
      assert.equal(p.responseStatusCode,200,'Actual browser asset status '+path);
      const body=await cdp.send('Fetch.getResponseBody',{requestId:p.requestId},sid);
      const bytes=Buffer.from(body.body,body.base64Encoded?'base64':'utf8');
      const hash=checkBody(path,bytes);
      report.browserAssets.push({path,url:p.request.url,bytes:bytes.length,sha256:hash,sessionId:sid});
    }
    await cdp.send('Fetch.continueRequest',{requestId:p.requestId},sid);
  }
  cdp.onEvent=event=>{
    if(event.method==='Runtime.exceptionThrown')report.pageErrors.push(event.params);
    if(event.method!=='Fetch.requestPaused'&&event.method!=='Target.attachedToTarget')return;
    const task=intercept(event).catch(error=>{fatal=error;}).finally(()=>interceptionTasks.delete(task));
    interceptionTasks.add(task);
  };
  await send('Page.enable');await send('Runtime.enable');await guardPage(sessionId);
  await send('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:true,flatten:true});
  await send('Page.setInterceptFileChooserDialog',{enabled:true});
  await send('Page.addScriptToEvaluateOnNewDocument',{source:observer});
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:documentURL.href});
  await until(()=>evaluate('document.readyState==="complete"&&!!document.querySelector("#intake-open")'),'native status candidate page');
  assert.equal(await evaluate('location.href'),documentURL.href);
  await action('#engine-start');await noRecords();


 await input('#job-email',sourceText);const analyzed=await action('#analyze');
 assert(analyzed.result.issues.some(x=>x.severity==='error'));
 if(!await evaluate('document.querySelector("#review-editor").open'))await activate('#review-editor > summary');
 await input('#review-client-name','Fictional Cedar Studio');await input('#review-client-email','billing@example.test');
 await input('#review-due-days','7');await input('#review-amount-paid','0');await input('#review-line-0-qty','2');
 let reviewed=await checkFields();assert.equal(reviewed.result.valid,true);
 assert.match(await evaluate('document.querySelector("#status-message").textContent'),/^Fields checked\./);
 const checkedInput=await snapshot();assert.equal(checkedInput.draftDisabled,false);
  const downloadBefore=cdp.events.length;
  await activate('#intake-save');
  const completed=await until(()=>{
    const events=cdp.events.slice(downloadBefore);
    const start=events.find(e=>e.method==='Browser.downloadWillBegin');
    if(!start)return null;
    const done=events.find(e=>e.method==='Browser.downloadProgress'&&e.params.guid===start.params.guid&&e.params.state==='completed');
    return done&&existsSync(resolve(downloads,start.params.suggestedFilename))?{...start.params,completion:done.params}:null;
  },'actual saved intake download');
  assert.match(completed.suggestedFilename,/^ledgerly-intake-\d{8}T\d{9}Z\.json$/);
  const savedPath=resolve(downloads,completed.suggestedFilename),savedBytes=readFileSync(savedPath),saved=JSON.parse(savedBytes);
  assert.deepEqual(Object.keys(saved).sort(),['format','version','saved_at','source_text','review_fields'].sort());
  assert.equal(saved.format,'ledgerly-intake');assert.equal(saved.version,1);
  assert.equal(saved.source_text,sourceText);assert.deepEqual(saved.review_fields,checkedInput.fields);
  report.downloads.push({filename:completed.suggestedFilename,bytes:savedBytes.length,sha256:sha(savedBytes),event:completed});
  save('saved-intake.json',savedBytes);await noRecords();


 const beforeEdit=await calls();await input('#review-client-name','Fictional Cedar Studio revised');
 assert.deepEqual(await calls(),beforeEdit);assert.equal((await snapshot()).confirmed,false);assert.equal((await snapshot()).draftDisabled,true);
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Fields changed. Confirm your review and check them again.');
 reviewed=await checkFields();assert.equal(reviewed.result.valid,true);
 const beforeUncheck=await calls();await focus('#review-confirm');await key(' ','Space',32);
 assert.deepEqual(await calls(),beforeUncheck);assert.equal((await snapshot()).confirmed,false);assert.equal((await snapshot()).draftDisabled,true);
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Confirm your review before checking the fields.');
 await noRecords();await screenshot('confirmation-removed-status.png');
 group('checked-status-retires-after-actual-field-edit-and-unconfirmation',{fieldEditRequestCount:0,unconfirmationRequestCount:0,draftDisabled:true});
 reviewed=await checkFields();assert.equal(reviewed.result.valid,true);
 const beforePreview=await calls();await openFile(savedPath);assert.deepEqual(await calls(),beforePreview);await replaceFile();
 const restored=await snapshot();
 assert.equal(restored.source,sourceText);assert.deepEqual(restored.fields,saved.review_fields);
 assert.equal(restored.confirmed,false);assert.equal(restored.draftDisabled,true);
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Restored unfinished fields. Read the current original warnings, confirm your review and check these fields with Python.');
 assert.equal(await evaluate('window.__publicIntake.requestStatuses.at(-1).status'),'Checking the opened intake with Python. Any previous review is retired.');
 assert((await replies()).at(-1).data.result.issues.some(x=>x.severity==='error'));
 await noRecords();await screenshot('restored-unchecked-status.png');
 save('restored-status-and-authority.json',{snapshot:restored,status:await evaluate('document.querySelector("#status-message").textContent'),reviewMessage:await evaluate('document.querySelector("#review-result").textContent'),observation:await evaluate('window.__publicIntake')});
 group('actual-downloaded-intake-restores-unchecked-fields-with-current-global-status',{restoredFieldsExact:true,confirmationRestored:false,draftDisabled:true});
 const sourceOnlyPath=resolve(inputs,'source-only-intake.json');writeFileSync(sourceOnlyPath,JSON.stringify({...saved,review_fields:null})+'\n',{flag:'wx'});
 await openFile(sourceOnlyPath);await replaceFile();
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Source restored and freshly analyzed. Review the current Python result before drafting.');
 assert.equal((await snapshot()).confirmed,false);
 const beforeSourceEdit=await calls();await input('#job-email',sourceText+'\nFictional note.');
 assert.deepEqual(await calls(),beforeSourceEdit);assert.equal((await snapshot()).draftDisabled,true);
 assert.equal(await evaluate('document.querySelector("#status-message").textContent'),'Source text changed. Analyze it again before reviewing or drafting.');
 await noRecords();await screenshot('source-edited-status.png');
 group('source-only-restoration-and-actual-source-edit-describe-current-analysis',{sourceEditRequestCount:0,draftDisabledAfterEdit:true});
 report.workerActions=(await calls()).reduce((a,x)=>(a[x.action]=(a[x.action]||0)+1,a),{});
 assert.deepEqual(report.workerActions,{init:1,analyze:3,review:3},'Only the three new status groups');
  save('actual-worker-and-input-observation.json',await evaluate('window.__publicIntake'));
  await until(async()=>{await Promise.all([...interceptionTasks]);return interceptionTasks.size===0;},'all intercepted response bodies verified');guard();
  const observed=new Set(report.browserAssets.map(x=>x.path));
  for(const path of ['index.html','assets/index-B2j3K_eH.js','assets/engine.worker-B5Sd8fS4.js','python/bridge.py','python/ledgerly/extract.py','python/review.py'])assert(observed.has(path),'Actual browser bytes bound: '+path);
  assert.deepEqual(report.networkRefusals,[]);assert.deepEqual(report.pageErrors,[]);
  report.sourceBound=true;
  report.status='pass';
} catch(error) {
  report.status=String(error).includes('NATIVE_ASSET_MISMATCH')?'asset-mismatch-stop':'failed';
  report.error=error.stack??String(error);
} finally {
  if(cdp&&sessionId){
    try{
      const observed=await cdp.send('Runtime.evaluate',{expression:'window.__publicIntake',returnByValue:true},sessionId);
      if(observed.result?.value)report.finalObservation=save('final-passive-observation.json',observed.result.value);
    }catch(error){report.finalObservationDiagnostic=error.message;}
  }
  if(cdp){try{await cdp.send('Browser.close');}catch(error){report.cleanup.closeDiagnostic=error.message;}cdp.close();}
  if(browser&&!exited){
    const end=Date.now()+10000;while(!exited&&Date.now()<end)await sleep(100);
    if(!exited){report.cleanup.termination='Owned child handle only';browser.kill();const until=Date.now()+5000;while(!exited&&Date.now()<until)await sleep(100);}
  }
  report.cleanup.browserStarted=Boolean(browser);report.cleanup.browserExited=exited;report.cleanup.exit=exitInfo;
  if(browser&&exited&&existsSync(profile)){
    try{rmSync(profile,{recursive:true,force:false,maxRetries:3,retryDelay:250});}
    catch(error){report.cleanup.profileError=error.message;}
  }
  report.cleanup.profileAbsent=!existsSync(profile);
  if(browser&&(!exited||!report.cleanup.profileAbsent))report.status='failed-cleanup';
  if(server){server.closeAllConnections();await new Promise(done=>server.close(done));report.cleanup.serverClosed=true;}
  save('browser.log',browserLog);
  report.referenceUnchanged=sha(readFileSync(resolve(root,'BUILD-MANIFEST.json')))===sha(referenceBytes);
  report.sourceUnchanged=Object.entries(sourcePins).every(([p,h])=>sha(readFileSync(resolve(root,p)))===h);
  report.buildUnchanged=Object.entries(reference.assets).every(([p,h])=>sha(readFileSync(resolve(build,p)))===h);
  report.historicalPublicAccessed=false;
  report.runtimeUnchanged=Object.entries(runtimePins).every(([p,h])=>fileSha(p)===h);
  if(!report.sourceUnchanged||!report.buildUnchanged||!report.runtimeUnchanged)report.status='failed-preservation';
  if(!report.referenceUnchanged)report.status='failed';
  report.finished_at=new Date().toISOString();
  save('RESULTS.json',report);
  console.log(JSON.stringify({status:report.status,groups:report.groups.length,preflightAssets:report.preflightAssets.length,browserAssets:report.browserAssets.length,sourceBound:report.sourceBound,cleanup:report.cleanup,error:report.error??null,receipt:resolve(out,'RESULTS.json')},null,2));
  process.exitCode=report.status==='pass'?0:1;
}
