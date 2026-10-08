#!/usr/bin/env node
/** Receive explicit intake files through the real app, Python Worker and installed Chrome.
 * Node 22+, existing locked web-demo dependencies, no extra browser package.
 * The original application is built privately; the candidate checkout is read only.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir,mkdtemp,rm,readdir,symlink} from 'node:fs/promises';
import {dirname,extname,join,resolve,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync} from 'node:zlib';
const argv=process.argv.slice(2);
const option=(key,fallback)=>argv.includes(key)?argv[argv.indexOf(key)+1]:fallback;
const project=resolve(option('--project',join(dirname(fileURLToPath(import.meta.url)),'../..')));
const output=resolve(option('--output',join(project,'intake-file-receiving')));
const build=resolve(option('--build',join(project,'web-demo/dist')));
const executable=option('--browser','google-chrome');
const receiptDir='docs/receipts/intake-files-e3a41d2b3368-20261008';
const capsulePath=join(project,receiptDir,'baseline-source.json');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const blob=bytes=>createHash('sha1').update(Buffer.from('blob '+bytes.length+'\0')).update(bytes).digest('hex');
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
await mkdir(output);
const report={schema:'ledgerly.intake-file-browser/1',status:'running',started_at:new Date().toISOString(),
  project,build,executable,node:process.version,platform:process.platform,checkout:process.env.GITHUB_SHA??null,
  claim:'https://github.com/Jacob-Met/ledgerly/issues/41',checks:[],artifacts:[],requests:[],externalRequests:[],
  serverRequests:[],pageErrors:[],sourceSha256:{},sourceUnchanged:false,buildUnchanged:false,
  observer:'Native Worker requests/replies are copied. One failure control holds a real reply then dispatches an authored Worker error. Delayed file controls call the original File.arrayBuffer only when released; no admitted bytes or Python results are synthesized.',
  boundary:'Actual local downloads, file picker input, Python checks, current ledger and approval controls. No provider, durable sandbox backup, payment or filesystem-watcher claim.'};
let assertions=0;
const eq=(actual,expected,label)=>{assertions++;assert.deepEqual(actual,expected,label);};
const ok=(value,label)=>{assertions++;assert.ok(value,label);};
const matches=(value,pattern,label)=>{assertions++;assert.match(value,pattern,label);};
const passed=name=>{report.checks.push({name,assertions_so_far:assertions});console.log('PASS '+name);};
let browser,socket,sessionId,profile,server,browserLog='',launchError,childClosed=false,sequence=0;
const pending=new Map(),downloads=new Map();
const downloadPath=join(output,'downloads'),baseline=join(output,'original-source');
const fileInputs=join(output,'inputs');
let sourceBefore,buildBefore,baselineBuild,base;
const sourcePaths=new Set();
async function sourceHashes(){
  const result={};for(const name of [...sourcePaths].sort())result[name]=hash(await readFile(join(project,name)));return result;
}
async function treeHashes(directory,prefix=''){
  const result={};
  for(const item of (await readdir(directory,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))){
    const name=prefix+item.name;
    if(item.isDirectory())Object.assign(result,await treeHashes(join(directory,item.name),name+'/'));
    else if(item.isFile())result[name]=hash(await readFile(join(directory,item.name)));
    else throw Error('Nonregular build artifact: '+name);
  }return result;
}
async function artifact(name,bytes,extra={}){
  const data=Buffer.isBuffer(bytes)?bytes:Buffer.from(bytes);
  ok(data.length<=3*1024*1024,'Bounded artifact '+name);
  await writeFile(join(output,name),data,{flag:'wx'});
  report.artifacts.push({name,bytes:data.length,sha256:hash(data),...extra});
}
async function runBuild(){
  let log='';
  const child=spawn(process.execPath,["C:\\Users\\minec\\AppData\\Local\\Hamon\\node\\node-v24.21.0-win-x64\\node_modules\\npm\\bin\\npm-cli.js",'run','build'],
    {cwd:join(baseline,'web-demo'),stdio:['ignore','pipe','pipe'],env:process.env});
  child.stdout.on('data',b=>{log+=b;});child.stderr.on('data',b=>{log+=b;});
  const timer=setTimeout(()=>child.kill('SIGTERM'),180000);
  const exit=await new Promise((done,reject)=>{child.once('error',reject);child.once('close',(code,signal)=>done({code,signal}));}).finally(()=>clearTimeout(timer));
  await artifact('original-build.log',log,{kind:'actual original npm run build',...exit});
  eq(exit.code,0,'Original locked application builds normally');
}
async function waitFor(check,label,attempts=900){
  for(let i=0;i<attempts;i++){if(launchError)throw launchError;if(await check())return;await sleep(100);}
  throw Error('Timed out: '+label);
}
function command(method,params={},scoped=true){
  const id=++sequence;
  return new Promise((done,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},15000);
    pending.set(id,{done,reject,timer});
    socket.send(JSON.stringify({id,method,params,...(scoped&&sessionId?{sessionId:typeof scoped==='string'?scoped:sessionId}:{})}));
  });
}
async function evaluate(expression){
  const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description??value.exceptionDetails.text);
  return value.result.value;
}
const js=JSON.stringify;
async function key(keyValue,code,virtualKey,modifiers=0){
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:keyValue,code,
    windowsVirtualKeyCode:virtualKey,nativeVirtualKeyCode:virtualKey,modifiers,
    ...(type==='keyDown'&&keyValue==='Enter'?{text:'\r',unmodifiedText:'\r'}:{}),
    ...(type==='keyDown'&&keyValue===' '?{text:' ',unmodifiedText:' '}:{} )});
}
async function focus(selector){
  ok(await evaluate('(()=>{const n=document.querySelector('+js(selector)+');if(!n||n.matches(":disabled")||!n.getClientRects().length)return false;n.scrollIntoView({block:"center"});n.focus();return document.activeElement===n;})()'),
    'Available focused control '+selector);
}
async function activate(selector){await focus(selector);await key('Enter','Enter',13);}
async function textInput(selector,value){
  await focus(selector);await key('a','KeyA',65,process.platform==='darwin'?4:2);await key('Backspace','Backspace',8);
  if(value)await command('Input.insertText',{text:value});
  eq(await evaluate('document.querySelector('+js(selector)+').value'),value,'Trusted raw input '+selector);
}
async function confirmReview(){
  await focus('#review-confirm');if(!await evaluate('document.querySelector("#review-confirm").checked'))await key(' ','Space',32);
  eq(await evaluate('document.querySelector("#review-confirm").checked'),true,'Explicit trusted confirmation');
}
const calls=()=>evaluate('window.__intakeProbe.calls');
const state=()=>evaluate('window.__intakeProbe.states.at(-1)');
const replies=()=>evaluate('window.__intakeProbe.replies');
const fieldsExpression='(()=>{const f=document.querySelector("#review-form");if(!f)return null;const v=n=>f.elements.namedItem(n).value;return {client_name:v("client_name"),client_email:v("client_email"),due_days:v("due_days"),amount_paid:v("amount_paid"),line_items:[...f.querySelectorAll("[data-review-line]")].map(row=>Object.fromEntries(["desc","qty","unit_price","currency","unit"].map(k=>[k,row.querySelector("[data-field="+k+"]").value])))};})()';
const inputSnapshot=()=>evaluate('({sourceText:document.querySelector("#job-email").value,fields:'+fieldsExpression+',confirmed:document.querySelector("#review-confirm")?.checked??false,draftDisabled:document.querySelector("#draft").disabled})');
async function action(selector){
  const before=await evaluate('window.__intakeProbe.replies.length');await activate(selector);
  await waitFor(()=>evaluate('window.__intakeProbe.replies.length>'+before+'&&!document.querySelector("#analyze").disabled'),'actual Python action '+selector);
  return (await replies()).at(-1).data;
}
async function analyze(text){
  await textInput('#job-email',text);const result=await action('#analyze');eq(result.ok,true,'Real source analysis succeeds');return result;
}
async function openEditor(){if(!await evaluate('document.querySelector("#review-editor").open'))await activate('#review-editor > summary');}
async function checkFields(){await confirmReview();return action('#review-check');}
async function navigate(kind,width=1280){
  const url=base+'/'+kind+'/';await command('Emulation.setDeviceMetricsOverride',{width,height:width===390?844:1000,deviceScaleFactor:1,mobile:false});
  await command('Page.navigate',{url});
  await waitFor(async()=>{try{return await evaluate('location.href==='+js(url)+'&&document.readyState==="complete"&&!!document.querySelector("#engine-start")');}catch{return false;}},'page '+kind);
}
async function savePageProbe(name){
  await artifact(name,JSON.stringify(await evaluate('({calls:__intakeProbe.calls,replies:__intakeProbe.replies,states:__intakeProbe.states,fileReads:__intakeProbe.fileReads,events:__intakeProbe.events,held:__intakeProbe.held?.data??null})'),null,2)+'\n',
    {kind:'observed actual page/Worker data; authored holds identified'});
}
async function download(name){
  const before=new Set(downloads.keys());await activate('#intake-save');let found;
  await waitFor(()=>{found=[...downloads.values()].find(d=>!before.has(d.guid)&&d.state==='completed');return !!found;},'actual intake download');
  const bytes=await readFile(join(downloadPath,found.guid));
  await artifact(name,bytes,{kind:'actual browser download',suggestedFilename:found.suggestedFilename});
  matches(found.suggestedFilename,/^ledgerly-intake-\d{8}T\d{9}Z\.json$/,'Portable intake filename');
  return {bytes,path:join(output,name),data:JSON.parse(bytes.toString('utf8'))};
}
async function writeInput(name,value){
  const path=join(fileInputs,name);await writeFile(path,Buffer.isBuffer(value)?value:typeof value==='string'?value:JSON.stringify(value)+'\n',{flag:'wx'});return path;
}
async function upload(path){
  const {root}=await command('DOM.getDocument',{depth:0});const {nodeId}=await command('DOM.querySelector',{nodeId:root.nodeId,selector:'#intake-file'});
  ok(nodeId>0,'Actual native file input exists');await command('DOM.setFileInputFiles',{nodeId,files:[path]});
}
async function preview(path){
  await upload(path);await waitFor(()=>evaluate('!document.querySelector("#intake-preview").hidden'),'admitted file preview');
  eq(await evaluate('document.activeElement.id'),'intake-preview-heading','Preview receives focus');
}
async function replacePreview(){
  const before=await calls();await activate('#intake-replace');
  await waitFor(()=>evaluate('document.querySelector("#intake-preview").hidden&&!document.querySelector("#analyze").disabled&&document.querySelector("#intake-file-status").textContent.includes("restored")'),'explicit file replacement');
  eq((await calls()).slice(before.length).map(c=>c.action),['analyze'],'Replacement only asks Python to analyze');
}
const observer='('+function(){
  const NativeWorker=window.Worker,read=File.prototype.arrayBuffer;
  const p=window.__intakeProbe={calls:[],replies:[],states:[],workers:[],holdAction:null,held:null,fileReads:[],slow:[],events:[]};
  window.Worker=class extends NativeWorker{
    constructor(...args){super(...args);p.workers.push(this);this.addEventListener('message',event=>{
      if(event.data?.data){p.replies.push(JSON.parse(JSON.stringify(event.data)));
        if(event.data.data.state)p.states.push(JSON.parse(JSON.stringify(event.data.data.state)));
        const req=p.calls.find(c=>c.id===event.data.id);
        if(p.holdAction&&req?.action===p.holdAction){p.holdAction=null;event.stopImmediatePropagation();p.held={worker:this,data:event.data};}
      }});}
    postMessage(...args){p.calls.push(JSON.parse(JSON.stringify(args[0])));return super.postMessage(...args);}
  };
  File.prototype.arrayBuffer=function(){const file=this;p.fileReads.push({name:file.name,size:file.size});
    if(file.name==='slow-intake.json')return new Promise((resolve,reject)=>p.slow.push(()=>read.call(file).then(resolve,reject)));
    return read.call(file);
  };
  p.releaseFile=async()=>{const fn=p.slow.shift();if(fn)await fn();};
  for(const type of ['keydown','input','change'])document.addEventListener(type,e=>{if(e.isTrusted)p.events.push({type,key:e.key??null,id:e.target?.id??null,trusted:true});},true);
}.toString()+')()';
async function newPage(){
  const {targetId}=await command('Target.createTarget',{url:'about:blank'},false);
  ({sessionId}=await command('Target.attachToTarget',{targetId,flatten:true},false));
  for(const domain of ['Page','Runtime','Network'])await command(domain+'.enable');
  await command('Fetch.enable',{patterns:[{urlPattern:'http*'}]});
  await command('Page.addScriptToEvaluateOnNewDocument',{source:observer});
}
async function screenshot(name){
  const {data}=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await artifact(name,Buffer.from(data,'base64'),{kind:'actual Chrome screenshot'});
}
try{
  const capsuleBytes=await readFile(capsulePath),capsule=JSON.parse(capsuleBytes.toString('utf8'));
  eq(capsule.schema,'ledgerly.intake-baseline-source/1','Frozen baseline format');
  eq(capsule.commit,'fba278f552e868ad2b94b7f1dc309eed6f1e8514','Actual original commit');
  eq(capsule.tree,'ddb2360a65b646a281969fea1abbb3238c154340','Actual original tree');
  eq(capsule.files.length,43,'Complete original build closure');
  report.baseline={commit:capsule.commit,tree:capsule.tree,capsuleSha256:hash(capsuleBytes),files:[]};
  const seen=new Set();
  for(const entry of capsule.files){
    const bytes=Buffer.from(entry.content),destination=resolve(baseline,entry.path);
    ok(destination.startsWith(baseline+sep)&&!seen.has(entry.path),'Unique bounded baseline path');
    ok(['100644','100755'].includes(entry.mode),'Regular Git baseline mode');
    eq(blob(bytes),entry.git_blob,'Exact original Git blob '+entry.path);
    seen.add(entry.path);sourcePaths.add(entry.path);
    await mkdir(dirname(destination),{recursive:true});
    await writeFile(destination,bytes,{flag:'wx',mode:entry.mode==='100755'?0o755:0o644});
    report.baseline.files.push({path:entry.path,git_blob:entry.git_blob,sha256:hash(bytes),bytes:bytes.length,mode:entry.mode});
  }
  eq(await readFile(join(baseline,'web-demo/package-lock.json')),await readFile(join(project,'web-demo/package-lock.json')),'Original and candidate use the same locked dependencies');
  for(const name of ['web-demo/src/intake-file.ts','web-demo/src/intake-file-ui.ts','web-demo/src/intake-file.css',
    'web-demo/tests/intake-file.test.ts','web-demo/tools/check_intake_file_browser.mjs',
    'web-demo/src/receivables.ts','web-demo/src/receivables.css','web-demo/src/rejection-reason.ts',
    'web-demo/src/rejection-reason.css','web-demo/tests/engine-recovery.test.ts','.github/workflows/ci.yml'])sourcePaths.add(name);
  sourceBefore=await sourceHashes();report.sourceSha256=sourceBefore;
  buildBefore=await treeHashes(build);report.buildSha256=buildBefore;
  await symlink(join(project,'web-demo/node_modules'),join(baseline,'web-demo/node_modules'),'dir');
  await runBuild();baselineBuild=join(baseline,'web-demo/dist');
  report.baseline.buildSha256=await treeHashes(baselineBuild);
  await mkdir(downloadPath);await mkdir(fileInputs);profile=await mkdtemp(join(output,'chrome-'));
  server=createServer(async(req,res)=>{
    try{
      const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      report.serverRequests.push({method:req.method,path:pathname});
      if(req.method!=='GET'){res.writeHead(405).end();return;}
      const match=pathname.match(/^\/(baseline|candidate)\/(.*)$/);
      if(!match){res.writeHead(404).end();return;}
      const root=match[1]==='baseline'?baselineBuild:build,file=resolve(root,match[2]||'index.html');
      if(!file.startsWith(root+sep)){res.writeHead(403).end();return;}
      const data=await readFile(file);
      const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css',
        '.json':'application/json','.wasm':'application/wasm','.svg':'image/svg+xml','.zip':'application/zip'}[extname(file)]||'application/octet-stream';
      res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'}).end(data);
    }catch{res.writeHead(404).end('Missing build input.');}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));base='http://127.0.0.1:'+server.address().port;
  const flags=['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',
    '--disable-component-update','--disable-sync','--disable-default-apps',
    '--disable-features=Translate,MediaRouter,OptimizationHints','--metrics-recording-only',
    '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'];
  report.browserFlags=flags;browser=spawn(executable,flags,{stdio:['ignore','ignore','pipe']});
  browser.stderr.on('data',b=>{browserLog=(browserLog+b.toString()).slice(-24000);});
  browser.once('error',error=>{launchError=error;});
  browser.once('close',(code,signal)=>{childClosed=true;report.browserExit={code,signal};});
  let active;
  await waitFor(async()=>{
    if(childClosed)throw Error('Chrome exited before its CDP endpoint: '+browserLog);
    try{active=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return active.length===2;}catch{return false;}
  },'installed Chrome endpoint',200);
  socket=new WebSocket('ws://127.0.0.1:'+active[0]+active[1]);
  socket.addEventListener('message',event=>{
    const message=JSON.parse(event.data);
    if(message.id){
      const request=pending.get(message.id);if(!request)return;pending.delete(message.id);clearTimeout(request.timer);
      if(message.error)request.reject(Error(message.error.message));else request.done(message.result);
    }else if(message.method==='Browser.downloadWillBegin'||message.method==='Browser.downloadProgress'){
      const value=message.params;downloads.set(value.guid,{...downloads.get(value.guid),...value});
    }else if(message.method==='Runtime.exceptionThrown'){
      report.pageErrors.push(message.params.exceptionDetails.exception?.description??message.params.exceptionDetails.text);
    }else if(message.method==='Network.requestWillBeSent'){
      const {url,method}=message.params.request;report.requests.push({url,method});
    }else if(message.method==='Fetch.requestPaused'){
      const request=message.params.request,allowed=request.method==='GET'&&new URL(request.url).origin===base;
      if(!allowed)report.externalRequests.push({url:request.url,method:request.method});
      void command(allowed?'Fetch.continueRequest':'Fetch.failRequest',{requestId:message.params.requestId,
        ...(!allowed?{errorReason:'BlockedByClient'}:{})},message.sessionId).catch(e=>report.pageErrors.push(e.message));
    }
  });
  await new Promise((done,reject)=>{socket.addEventListener('open',done,{once:true});socket.addEventListener('error',reject,{once:true});});
  report.browser=await command('Browser.getVersion',{},false);
  await command('Browser.setDownloadBehavior',{behavior:'allowAndName',downloadPath,eventsEnabled:true},false);
  await newPage();
  const source=await readFile(join(baseline,'fixtures/05_missing_email.txt'),'utf8');
  const literal='<img src=x onerror="globalThis.__intakeLiteralExecuted=true"> fictional 雨';
  async function unfinished(){
    await action('#engine-start');await analyze(source);await openEditor();
    await textInput('#review-client-name',literal);await textInput('#review-client-email','billing@example.test');
    await textInput('#review-due-days','later');await textInput('#review-line-0-qty','');
    await textInput('#review-line-0-price','1,200.00');return inputSnapshot();
  }

  await navigate('baseline');
  const originalInput=await unfinished();
  eq(await evaluate('document.querySelector("#intake-save")'),null,'Original application has no intake download');
  eq(await evaluate('document.querySelector("#intake-open")'),null,'Original application has no intake reopen');
  await savePageProbe('original-worker.json');await navigate('baseline');
  eq((await inputSnapshot()).sourceText,'','A new original page loses source input');
  eq((await inputSnapshot()).fields,null,'A new original page loses unfinished fields');
  report.originalBoundary={input:originalInput,afterReload:await inputSnapshot()};
  passed('original actual application loses unfinished intake across page reload');

  await navigate('candidate');
  const unfinishedInput=await unfinished(),beforeSaveCalls=await calls(),beforeSaveState=await state();
  const partial=await download('actual-unfinished-intake.json');
  eq(partial.data.source_text,unfinishedInput.sourceText,'Actual download retains complete source');
  eq(partial.data.review_fields,unfinishedInput.fields,'Actual download retains unfinished literal fields');
  eq(Object.keys(partial.data),['format','version','saved_at','source_text','review_fields'],'No derived authority in download');
  eq(await calls(),beforeSaveCalls,'Saving sends no Worker request');eq(await state(),beforeSaveState,'Saving preserves the sandbox snapshot');
  await savePageProbe('candidate-unfinished-worker.json');
  passed('actual local download preserves unfinished input without creating validation or invoice state');

  await navigate('candidate');
  const freshInput=await inputSnapshot();await preview(partial.path);
  eq(await inputSnapshot(),freshInput,'Preview does not replace current input');eq(await calls(),[],'Preview before engine start makes no Worker call');
  eq(await evaluate('document.querySelector("#intake-replace").disabled'),true,'Replacing requires the local engine');
  await action('#engine-start');
  eq(await evaluate('document.querySelector("#intake-preview").hidden'),false,'Explicit engine start retains file preview');
  await replacePreview();
  const restored=await inputSnapshot();
  eq(restored.sourceText,unfinishedInput.sourceText,'Reopened source is exact');
  eq(restored.fields,unfinishedInput.fields,'Reopened unfinished fields are exact');
  eq(restored.confirmed,false,'Confirmation is not restored');eq(restored.draftDisabled,true,'No saved approval or valid revision is restored');
  ok(await evaluate('[...document.querySelectorAll("#analysis > .issue-list .issue")].some(n=>n.textContent.toLowerCase().includes("email"))'),'Fresh original missing-email warning remains visible');
  eq(await evaluate('!!globalThis.__intakeLiteralExecuted'),false,'Markup-like field text does not execute');
  const invalid=await checkFields();
  eq(invalid.ok,false,'Original Python rejects unfinished numeric fields');eq((await state()).ledger,[],'Invalid reopened fields create no invoice');
  eq((await inputSnapshot()).draftDisabled,true,'Invalid reopened fields cannot draft');
  passed('fresh-page opening previews first and requires fresh actual Python checks');

  await textInput('#review-line-0-qty','2');await textInput('#review-line-0-price','125.00');await textInput('#review-due-days','15');
  const valid=await checkFields();
  eq(valid.ok,true,'Real corrected review call succeeds');eq(valid.result.valid,true,'Python validates supplied corrections');
  matches(valid.result.review_id,/^[a-f0-9]{32}$/,'Fresh Python one-use revision');
  const firstToken=valid.result.review_id,checkedInput=await inputSnapshot(),checkedCalls=await calls(),checkedState=await state();
  const checked=await download('actual-checked-intake.json');
  eq(checked.data.review_fields,checkedInput.fields,'Checked file still records raw fields');
  eq(Object.keys(checked.data),['format','version','saved_at','source_text','review_fields'],'Checked file still has no revision or confirmation');
  eq(await calls(),checkedCalls,'Saving checked fields does not request another review');eq(await state(),checkedState,'Saving checked fields does not change the ledger');
  const drafted=await action('#draft');
  eq(drafted.ok,true,'Existing reviewed draft handler succeeds');eq(drafted.result.unauthorized_send_blocked,true,'Existing human approval gate still blocks unapproved send');
  eq(drafted.state.ledger.length,1,'Only explicit draft creates one invoice');eq(drafted.state.ledger[0].status,'DRAFT','Invoice remains an unsent draft');
  eq(drafted.state.pending.length,1,'Existing separate send approval remains pending');
  const preserved=await state();await preview(checked.path);await replacePreview();
  const afterOpen=await state();
  for(const field of ['ledger','pending','invoice_details','mock_requests','audit'])eq(afterOpen[field],preserved[field],'Replacing intake preserves '+field);
  eq((await inputSnapshot()).confirmed,false,'Opening checked fields retires confirmation');
  eq((await inputSnapshot()).draftDisabled,true,'Opening checked fields retires the old revision');
  const rechecked=await checkFields();eq(rechecked.result.valid,true,'Explicit recheck succeeds');
  ok(rechecked.result.review_id!==firstToken,'Opening produces a new revision only after recheck');
  const approved=await action('button[data-approve]');
  eq(approved.result.approved,true,'Existing explicit send approval still works');eq(approved.state.ledger.length,1,'Approval does not create another invoice');
  eq(approved.state.ledger[0].status,'SENT','Original pending draft is sent only by explicit approval');
  await screenshot('desktop-restored-intake.png');
  passed('checked files confer no authority; intake replacement preserves existing invoices and separate approval');

  const current=await inputSnapshot(),currentCalls=await calls(),currentState=await state();
  const badVersion=structuredClone(checked.data);badVersion.version=2;
  const extra=structuredClone(checked.data);extra.review_id=firstToken;
  const numeric=structuredClone(checked.data);numeric.review_fields.line_items[0].qty=2;
  const crlf=structuredClone(checked.data);crlf.source_text='source\r\nchanged';
  const nul=structuredClone(checked.data);nul.review_fields.line_items[0].desc='before\0after';
  const refusals=[
    ['malformed.json','{',/valid JSON/],['unsupported.json',badVersion,/supported version/],
    ['authority.json',extra,/unexpected fields/],['numeric.json',numeric,/must be text/],
    ['oversized.json',Buffer.alloc(2*1024*1024+1,32),/2 MiB/],
    ['invalid-utf8.json',Buffer.from([0xff,0xfe,0xfa]),/UTF-8/],
    ['source-normalization.json',crlf,/restored exactly/],['line-normalization.json',nul,/restored exactly/],
  ];
  for(const [name,value,message]of refusals){
    const path=await writeInput(name,value);await upload(path);
    await waitFor(()=>evaluate('!document.querySelector("#intake-file-status").dataset.reading&&document.querySelector("#intake-file-status").textContent.includes("Current intake is unchanged.")'),'file refusal '+name);
    matches(await evaluate('document.querySelector("#intake-file-status").textContent'),message,name+' explains refusal');
    eq(await evaluate('document.querySelector("#intake-preview").hidden'),true,name+' leaves no preview');
    eq(await inputSnapshot(),current,name+' preserves current raw input and review');
    eq(await calls(),currentCalls,name+' creates no Worker call');eq(await state(),currentState,name+' preserves sandbox state');
  }
  passed('malformed, unsupported, oversized and lossy files are refused before current intake changes');

  const slow=await writeInput('slow-intake.json',partial.bytes);
  await upload(slow);await waitFor(()=>evaluate('__intakeProbe.slow.length===1'),'held actual file read');
  const editedSource=current.sourceText+'\nFictional additional note.';
  await textInput('#job-email',editedSource);await evaluate('__intakeProbe.releaseFile()');await sleep(100);
  eq((await inputSnapshot()).sourceText,editedSource,'Current trusted edit wins over delayed read');
  eq(await evaluate('document.querySelector("#intake-preview").hidden'),true,'Retired delayed read cannot expose a preview');
  const raceCalls=await calls();
  await upload(slow);await waitFor(()=>evaluate('__intakeProbe.slow.length===1'),'second held actual file read');
  await preview(checked.path);
  const newest=await evaluate('document.querySelector("#intake-preview-summary").textContent');
  await evaluate('__intakeProbe.releaseFile()');await sleep(100);
  eq(await evaluate('document.querySelector("#intake-preview-summary").textContent'),newest,'Later file selection wins');
  await focus('#intake-cancel');await key('Escape','Escape',27);
  eq(await evaluate('document.querySelector("#intake-preview").hidden'),true,'Escape dismisses preview');
  eq(await evaluate('document.activeElement.id'),'intake-open','Escape returns focus to Open intake');
  eq((await inputSnapshot()).sourceText,editedSource,'Cancellation preserves current source');
  eq(await calls(),raceCalls,'Delayed-read and cancellation controls make no Worker call');
  await preview(checked.path);await activate('#intake-cancel');
  eq((await inputSnapshot()).sourceText,editedSource,'Keep current intake preserves input');
  eq(await evaluate('document.activeElement.id'),'intake-open','Keep returns focus to Open intake');
  passed('actual delayed file reads cannot override a newer edit, selection or cancellation');

  await preview(checked.path);await replacePreview();await checkFields();
  const beforeFailure=await inputSnapshot(),failureCalls=await calls(),failureState=await state();
  await preview(partial.path);await evaluate('__intakeProbe.holdAction="analyze"');await activate('#intake-replace');
  await waitFor(()=>evaluate('!!__intakeProbe.held'),'held actual incoming analysis reply');
  eq((await calls()).slice(failureCalls.length).map(c=>c.action),['analyze'],'Interrupted replacement attempted exactly one analysis');
  eq(await evaluate('document.querySelector("#intake-save").disabled'),true,'Save is unavailable while replacement is busy');
  eq(await evaluate('document.querySelector("#intake-open").disabled'),true,'Open is unavailable while replacement is busy');
  const held=await evaluate('__intakeProbe.held.data');
  eq(held.data.ok,true,'Held reply is a real successful Python result');eq(held.data.state.ledger,failureState.ledger,'Incoming analysis itself preserves invoices');
  await evaluate('__intakeProbe.workers.at(-1).dispatchEvent(new ErrorEvent("error",{message:"authored terminal failure after real incoming analysis"}))');
  await waitFor(()=>evaluate('document.querySelector("#engine-status").textContent==="PYTHON UNAVAILABLE"&&!document.querySelector("#intake-save").disabled'),'explicit failed replacement retains export');
  const failed=await inputSnapshot();
  eq(failed.sourceText,beforeFailure.sourceText,'Failed replacement retains previous source');
  eq(failed.fields,beforeFailure.fields,'Failed replacement retains previous raw fields');
  eq(failed.confirmed,false,'Failed replacement retires old confirmation');eq(failed.draftDisabled,true,'Failed replacement retires old revision');
  const failedCalls=await calls(),recoveryFile=await download('actual-retained-after-failure.json');
  eq(recoveryFile.data.source_text,beforeFailure.sourceText,'Unavailable-session download retains actual old source');
  eq(recoveryFile.data.review_fields,beforeFailure.fields,'Unavailable-session download retains actual old fields');
  eq(await calls(),failedCalls,'Unavailable-session Save does not replay an action');
  await savePageProbe('interrupted-replacement-worker.json');await activate('#intake-cancel');await action('#engine-start');
  eq((await state()).ledger,[],'Existing explicit restart contract starts an empty sandbox');
  eq((await inputSnapshot()).fields,beforeFailure.fields,'Explicit restart retains raw input');
  const restartCalls=await calls(),recovered=await checkFields();
  eq((await calls()).slice(restartCalls.length).map(c=>c.action),['analyze','review'],'Explicit check reanalyzes retained source in new sandbox');
  eq(recovered.result.valid,true,'Retained corrections can be checked in the new Python session');
  eq((await state()).ledger,[],'Recovery check still creates no invoice');
  passed('failed replacement preserves recoverable input, retires authority and composes with explicit Worker restart');

  await textInput('#job-email','Unfinished fictional source only.');
  const sourceOnlyCalls=await calls(),sourceOnly=await download('actual-source-only-intake.json');
  eq(sourceOnly.data.review_fields,null,'Source-only save does not invent editable fields');
  eq(await calls(),sourceOnlyCalls,'Source-only save does not analyze automatically');
  await preview(sourceOnly.path);await replacePreview();
  eq((await inputSnapshot()).sourceText,sourceOnly.data.source_text,'Source-only reopen restores exact text');
  eq((await inputSnapshot()).draftDisabled,true,'Fresh low-confidence source remains blocked by original analysis');
  eq((await state()).ledger,[],'Source-only reopen creates no invoice');
  const validSource=await readFile(join(baseline,'fixtures/01_simple_usd_hourly.txt'),'utf8');
  await textInput('#job-email',validSource);
  const validSourceFile=await download('actual-valid-source-only-intake.json');
  eq(validSourceFile.data.review_fields,null,'Unanalyzed valid source is also source-only');
  await preview(validSourceFile.path);await replacePreview();
  eq((await inputSnapshot()).draftDisabled,false,'Fresh valid extraction enables only the existing explicit raw draft');
  eq((await state()).ledger,[],'Fresh valid extraction still creates no invoice');
  const rawCalls=await calls(),rawDraft=await action('#draft'),newRawCalls=(await calls()).slice(rawCalls.length);
  eq(newRawCalls.map(c=>c.action),['draft'],'Only explicit draft creates a source-only invoice');
  eq(Object.hasOwn(newRawCalls[0].payload,'review_id'),false,'Source-only draft uses ordinary extraction, not an invented review token');
  eq(rawDraft.state.ledger.length,1,'Explicit source-only draft creates one invoice');
  eq(rawDraft.state.ledger[0].status,'DRAFT','Fresh source-only invoice is unsent');
  eq(rawDraft.state.pending.length,1,'Source-only send still needs separate approval');
  eq(rawDraft.result.unauthorized_send_blocked,true,'Original approval guard applies to source-only files');
  passed('source-only files use fresh extraction: invalid input stays blocked and valid input keeps explicit draft plus send approval');

  await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
  await preview(checked.path);
  eq(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),true,'Mobile document has no horizontal overflow');
  eq(await evaluate('document.activeElement.id'),'intake-preview-heading','Mobile preview retains keyboard focus');
  await screenshot('mobile-intake-preview.png');await replacePreview();
  eq((await inputSnapshot()).fields,checked.data.review_fields,'Mobile explicit replacement preserves raw fields');
  eq(await evaluate('!!globalThis.__intakeLiteralExecuted'),false,'Literal text remains nonexecuting');
  const trusted=await evaluate('__intakeProbe.events');
  ok(trusted.some(e=>e.type==='keydown'&&e.key==='Enter'&&e.id==='intake-save'),'Download exercised trusted keyboard activation');
  ok(trusted.some(e=>e.type==='keydown'&&e.key==='Enter'&&e.id==='intake-replace'),'Replacement exercised trusted keyboard activation');
  ok(trusted.some(e=>e.type==='keydown'&&e.key===' '&&e.id==='review-confirm'),'Confirmation exercised trusted Space');
  ok(trusted.some(e=>e.type==='keydown'&&e.key==='Escape'),'Preview exercised trusted Escape');
  eq(report.externalRequests,[],'No observed off-origin or non-GET browser request');
  eq(report.pageErrors,[],'No page runtime exception');eq((await state()).external_calls,0,'Actual final sandbox reports zero external calls');
  ok(report.serverRequests.every(r=>r.method==='GET'),'Static app receiver handled only GET requests');
  await savePageProbe('final-worker-and-keyboard.json');
  passed('mobile and trusted keyboard flow preserves literal input without external application actions');
  report.status='passed';
}catch(error){
  report.status='failed';report.error=error.stack??String(error);report.browserLog=browserLog;process.exitCode=1;
  if(sessionId&&socket?.readyState===WebSocket.OPEN){
    try{report.lastPage=await evaluate('({url:location.href,focus:document.activeElement?.outerHTML,text:document.body?.innerText.slice(0,10000)})');
      await savePageProbe('failed-worker.json');await screenshot('failed-page.png');}catch{}
  }console.error(report.error);
}finally{
  if(socket?.readyState===WebSocket.OPEN){try{await command('Browser.close',{},false);}catch{}}
  socket?.close();for(const item of pending.values())clearTimeout(item.timer);
  if(browser&&!childClosed){
    for(let i=0;i<30&&!childClosed;i++)await sleep(100);
    if(!childClosed){browser.kill('SIGTERM');for(let i=0;i<20&&!childClosed;i++)await sleep(100);}
  }
  if(browser&&!childClosed){report.status='failed';report.cleanupError='Browser did not confirm exit; private profile retained.';process.exitCode=1;}
  else if(profile)await rm(profile,{recursive:true,force:true});
  if(server){server.closeAllConnections();await new Promise(done=>server.close(done));}
  try{
    if(sourceBefore){report.sourceUnchanged=JSON.stringify(await sourceHashes())===JSON.stringify(sourceBefore);ok(report.sourceUnchanged,'Candidate source closure unchanged');}
    if(buildBefore){report.buildUnchanged=JSON.stringify(await treeHashes(build))===JSON.stringify(buildBefore);ok(report.buildUnchanged,'Candidate build closure unchanged');}
  }catch(error){report.status='failed';report.preservationError=error.stack??String(error);process.exitCode=1;}
  if(!report.sourceUnchanged||!report.buildUnchanged){report.status='failed';process.exitCode=1;}
  report.assertions=assertions;report.completed_at=new Date().toISOString();
  await writeFile(join(output,'receiving-report.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  if(argv.includes('--emit-bundle')){
    const names=report.artifacts.filter(a=>!a.name.endsWith('.png')).map(a=>a.name).concat('receiving-report.json'),files=[];
    for(const name of names){const bytes=await readFile(join(output,name));files.push({path:name,bytes:bytes.length,sha256:hash(bytes),base64:bytes.toString('base64')});}
    const bytes=gzipSync(Buffer.from(JSON.stringify({schema:'ledgerly.intake-receiving-bundle/1',files})));
    assert.ok(bytes.length<=1024*1024,'Bounded non-image receiving bundle');
    const text=bytes.toString('base64'),chunks=Math.ceil(text.length/4096);
    console.log('LEDGERLY_INTAKE_BUNDLE_BEGIN '+JSON.stringify({bytes:bytes.length,sha256:hash(bytes),encoding:'gzip+base64',chunks}));
    for(let i=0;i<chunks;i++)console.log('LEDGERLY_INTAKE_BUNDLE_CHUNK '+i+' '+text.slice(i*4096,(i+1)*4096));
    console.log('LEDGERLY_INTAKE_BUNDLE_END');
  }
  console.log('LEDGERLY_INTAKE_RESULT '+JSON.stringify({status:report.status,groups:report.checks.length,assertions,
    sourceUnchanged:report.sourceUnchanged,buildUnchanged:report.buildUnchanged,receipt:join(output,'receiving-report.json')}));
}
