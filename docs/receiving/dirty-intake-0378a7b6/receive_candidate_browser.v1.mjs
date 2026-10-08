import assert from 'node:assert/strict';
import {chromium} from 'file:///C:/hamon-receiving-b47cbcf18759/dependencies/playwright-core-1.62.1/index.mjs';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root=resolve(process.argv[2]),out=resolve(process.argv[3]),build=join(root,'web-demo/dist');
await mkdir(out);
const hash=b=>createHash('sha256').update(b).digest('hex');
const git=(...args)=>execFileSync('git',['-C',root,...args],{encoding:'utf8'}).trim();
assert.equal(git('rev-parse','HEAD'),'c498f55883c755553b59921199d54689d99c9730');
const sourcePaths=git('ls-tree','-r','--name-only','HEAD').split('\n').filter(p=>p.startsWith('web-demo/src/')||p.startsWith('ledgerly/')&&p.endsWith('.py')||['web-demo/index.html','web-demo/package.json','web-demo/package-lock.json'].includes(p));
sourcePaths.push('web-demo/src/intake-replacement.ts','web-demo/src/intake-replacement.css');
const source=Object.fromEntries(await Promise.all(sourcePaths.map(async p=>[p,hash(await readFile(join(root,p)))])));
async function hashes(dir,prefix=''){const result={};for(const e of await readdir(dir,{withFileTypes:true})){const p=prefix+e.name;if(e.isDirectory())Object.assign(result,await hashes(join(dir,e.name),p+'/'));else if(e.isFile())result[p]=hash(await readFile(join(dir,e.name)));}return result;}
const buildHashes=await hashes(build);
const report={head:git('rev-parse','HEAD'),tree:git('rev-parse','HEAD^{tree}'),at:new Date().toISOString(),driverSha256:hash(await readFile(new URL(import.meta.url))),source,buildHashes,cases:[],external:[],pageErrors:[],serverRequests:[]};
let failFixture=false;
const server=createServer(async(req,res)=>{try{const p=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname),file=resolve(build,'.'+(p==='/'?'/index.html':p));if(!file.startsWith(build+sep))throw Error('path');if(failFixture&&p.includes('/fixtures/')){res.writeHead(503).end('authored fixture failure');return;}const data=await readFile(file);report.serverRequests.push({path:p,sha256:hash(data)});res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.svg':'image/svg+xml','.zip':'application/zip'})[extname(file)]||'application/octet-stream'}).end(data);}catch{res.writeHead(404).end();}});
await new Promise(done=>server.listen(0,'127.0.0.1',done));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',args:['--disable-background-networking']});
report.browser=browser.version();
const fields=page=>page.evaluate(()=>{const f=document.querySelector('#review-form');if(!f)return null;const v=n=>f.elements.namedItem(n).value;return {client_name:v('client_name'),client_email:v('client_email'),due_days:v('due_days'),amount_paid:v('amount_paid'),line_items:[...f.querySelectorAll('[data-review-line]')].map(row=>Object.fromEntries(['desc','qty','unit_price','currency','unit'].map(k=>[k,row.querySelector('[data-field="'+k+'"]').value])))};});
const probe=page=>page.evaluate(()=>({calls:__dirtyProbe.calls,replies:__dirtyProbe.replies,states:__dirtyProbe.states}));
async function action(page,selector){const before=await page.evaluate(()=>__dirtyProbe.replies.length);await page.locator(selector).click();await page.waitForFunction(n=>__dirtyProbe.replies.length>n&&!document.querySelector('#analyze').disabled,before,{timeout:90000});return (await probe(page)).replies.at(-1).data;}
async function setup(){
 const context=await browser.newContext({viewport:{width:1280,height:1000},serviceWorkers:'block'});
 await context.route('**/*',route=>{const u=route.request().url();if(u.startsWith(origin+'/'))return route.continue();if(u.startsWith('http')){report.external.push(u);return route.abort();}return route.continue();});
 const page=await context.newPage();
 page.on('pageerror',e=>report.pageErrors.push(String(e)));
 const dialogs=[];page.on('dialog',async d=>{dialogs.push({type:d.type(),message:d.message()});await d.dismiss();});
 await page.addInitScript(()=>{const N=Worker,p=window.__dirtyProbe={calls:[],replies:[],states:[],workers:[],failNextAnalyze:false};window.Worker=class extends N{constructor(...a){super(...a);p.workers.push(this);this.addEventListener('message',e=>{if(e.data?.data){p.replies.push(JSON.parse(JSON.stringify(e.data)));if(e.data.data.state)p.states.push(JSON.parse(JSON.stringify(e.data.data.state)));const request=p.calls.find(c=>c.id===e.data.id);if(p.failNextAnalyze&&request?.action==='analyze'){p.failNextAnalyze=false;e.stopImmediatePropagation();this.dispatchEvent(new Event('error'));}}});}postMessage(...a){p.calls.push(JSON.parse(JSON.stringify(a[0])));return super.postMessage(...a);}};});
 await page.goto(origin);
 assert.equal((await action(page,'#engine-start')).ok,true);
 await page.locator('#load-fixture').click();
 await page.waitForFunction(()=>!document.querySelector('#analyze').disabled&&document.querySelector('#job-email').value.length>0);
 assert.equal((await action(page,'#analyze')).ok,true);
 await page.locator('#review-editor > summary').click();
 return {page,context,dialogs};
}
async function edit(page){await page.locator('#review-client-name').fill('Edited recipient Ω');await page.locator('#review-client-email').fill('reviewed@example.test');await page.locator('#review-due-days').fill('45');await page.locator('#review-line-0-desc').fill('Corrected <work> & revision');await page.locator('#review-line-0-qty').fill('7');return fields(page);}
const dialog='#intake-replacement-dialog';
async function begin(page,selector){await page.locator(selector).click();await page.locator(dialog).waitFor({state:'visible'});}
async function sameIntake(page,snapshot){assert.deepEqual(await fields(page),snapshot.fields);assert.equal(await page.locator('#job-email').inputValue(),snapshot.source);}
async function record(page,id){report.cases.push({id,pass:true});await writeFile(join(out,id+'-probe.json'),JSON.stringify(await probe(page),null,2)+'\n');console.log('PASS '+id);}
try{
 {
  const {page,context}=await setup(),corrected=await edit(page),text=await page.locator('#job-email').inputValue(),before=await probe(page);
  await page.locator('#review-confirm').check();assert.equal((await action(page,'#review-check')).result.valid,true);
  assert.equal(await page.locator('#draft').isEnabled(),true);
  await page.locator('#job-email').fill(text+'\nPlease verify this edited source.');
  assert.deepEqual(await fields(page),corrected);assert.equal(await page.locator('#review-confirm').isChecked(),false);assert.equal(await page.locator('#review-check').isDisabled(),true);assert.equal(await page.locator('#draft').isDisabled(),true);
  assert.match(await page.locator('#intake-source-notice').textContent(),/Earlier analysis.*source text has changed/);
  const calls=(await probe(page)).calls.length;
  await begin(page,'#analyze');assert.equal(await page.locator('#intake-keep-corrections').evaluate(e=>document.activeElement===e),true);
  await page.keyboard.press('Escape');await page.locator(dialog).waitFor({state:'hidden'});assert.deepEqual(await fields(page),corrected);assert.equal((await probe(page)).calls.length,calls);
  await begin(page,'#analyze');const analyzed=await action(page,'#intake-keep-corrections');assert.equal(analyzed.ok,true);
  assert.deepEqual(await fields(page),corrected);assert.equal(await page.locator('#intake-source-notice').count(),0);assert.equal(await page.locator('#review-confirm').isChecked(),false);
  for(const issue of analyzed.result.issues??[])assert.ok((await page.locator('#analysis > .issue-list').textContent()).includes(issue.message));
  assert.equal(await page.locator('#draft').isDisabled(),true);
  await page.locator('#review-confirm').check();assert.equal((await action(page,'#review-check')).result.valid,true);
  assert.equal((await action(page,'#draft')).ok,true);
  const state=(await probe(page)).states.at(-1);assert.equal(state.ledger.length,1);assert.equal(state.ledger[0].status,'DRAFT');assert.equal(state.pending.length,1);
  assert.equal(await page.locator('#draft').isDisabled(),true);
  assert.equal((await action(page,'button[data-approve]')).result.approved,true);
  assert.equal((await probe(page)).states.at(-1).ledger[0].status,'SENT');
  await record(page,'source-change-keep-fresh-check-separate-approval');await context.close();
 }
 {
  const {page,context}=await setup(),extracted=await fields(page);await edit(page);
  const snap={fields:await fields(page),source:await page.locator('#job-email').inputValue()},before=await probe(page);
  await begin(page,'#analyze');await page.locator('#intake-cancel-replacement').click();await sameIntake(page,snap);assert.deepEqual(await probe(page),before);
  await begin(page,'#analyze');assert.equal((await action(page,'#intake-use-extraction')).ok,true);assert.deepEqual(await fields(page),extracted);
  assert.equal(await page.locator('#review-confirm').isChecked(),false);await record(page,'reanalyze-cancel-and-explicit-extraction');await context.close();
 }
 {
  const {page,context}=await setup();await edit(page);const snap={fields:await fields(page),source:await page.locator('#job-email').inputValue()},before=await probe(page);
  await page.locator('#fixture-select').selectOption({index:1});await begin(page,'#load-fixture');
  assert.equal(await page.locator('#intake-cancel-replacement').evaluate(e=>document.activeElement===e),true);assert.equal(await page.locator('#intake-keep-corrections').isVisible(),false);
  await page.keyboard.press('Escape');await sameIntake(page,snap);assert.deepEqual(await probe(page),before);
  failFixture=true;await begin(page,'#load-fixture');await page.locator('#intake-use-extraction').click();
  await page.waitForFunction(()=>document.querySelector('#status-message').textContent.includes('Fixture HTTP 503'));
  await sameIntake(page,snap);assert.deepEqual(await probe(page),before);
  failFixture=false;await begin(page,'#load-fixture');await page.locator('#intake-use-extraction').click();
  await page.waitForFunction(()=>!document.querySelector('#load-fixture').disabled&&document.querySelector('#review-form')===null);
  assert.notEqual(await page.locator('#job-email').inputValue(),snap.source);assert.deepEqual((await probe(page)).states.at(-1).ledger,before.states.at(-1).ledger);
  await record(page,'fixture-cancel-failure-and-explicit-replacement');await context.close();
 }
 {
  const {page,context}=await setup();const corrected=await edit(page),text=await page.locator('#job-email').inputValue();
  await page.locator('#job-email').fill(text+'\nFresh source before a simulated worker failure.');
  await page.evaluate(()=>__dirtyProbe.failNextAnalyze=true);await begin(page,'#analyze');await action(page,'#intake-keep-corrections');
  await page.waitForFunction(()=>document.querySelector('#engine-status').textContent==='PYTHON UNAVAILABLE');
  assert.deepEqual(await fields(page),corrected);assert.equal(await page.locator('#draft').isDisabled(),true);
  assert.equal((await action(page,'#engine-start')).ok,true);assert.deepEqual(await fields(page),corrected);
  await begin(page,'#analyze');assert.equal((await action(page,'#intake-keep-corrections')).ok,true);
  assert.deepEqual(await fields(page),corrected);assert.equal(await page.locator('#review-confirm').isChecked(),false);assert.equal((await probe(page)).states.at(-1).ledger.length,0);
  await record(page,'real-analysis-reply-then-authored-worker-failure');await context.close();
 }
 {
  const {page,context}=await setup();const corrected=await edit(page),text=(await page.locator('#job-email').inputValue())+'\nUnfinished source revision.';
  await page.locator('#job-email').fill(text);const saved=page.waitForEvent('download');await page.locator('#intake-save').click();const download=await saved,path=join(out,'retained-intake.json');await download.saveAs(path);
  const payload=JSON.parse(await readFile(path,'utf8'));assert.equal(payload.source_text,text);assert.deepEqual(payload.review_fields,corrected);
  const {page:receiving,context:receivingContext}=await setup();const before=(await probe(receiving)).states.at(-1).ledger;
  await receiving.locator('#intake-file').setInputFiles(path);await receiving.locator('#intake-preview').waitFor({state:'visible'});
  await action(receiving,'#intake-replace');assert.deepEqual(await fields(receiving),corrected);
  assert.equal(await receiving.locator('#job-email').inputValue(),text);assert.equal(await receiving.locator('#review-confirm').isChecked(),false);assert.equal(await receiving.locator('#draft').isDisabled(),true);assert.deepEqual((await probe(receiving)).states.at(-1).ledger,before);
  await record(receiving,'portable-intake-keeps-unfinished-fields-fresh-review');await receivingContext.close();await context.close();
 }
 {
  const {page,context}=await setup();const before=await fields(page);await action(page,'#analyze');assert.deepEqual(await fields(page),before);assert.equal(await page.locator(dialog).isVisible(),false);
  await page.locator('#review-editor > summary').click();await edit(page);const corrected=await fields(page),text=await page.locator('#job-email').inputValue();
  await page.locator('#job-email').fill(text+'\n');await page.locator('#job-email').fill(text);assert.deepEqual(await fields(page),corrected);assert.equal(await page.locator('#intake-source-notice').count(),0);
  await page.locator('#review-confirm').check();assert.equal((await action(page,'#review-check')).result.valid,true);
  await record(page,'clean-reanalysis-and-exact-source-restoration');await context.close();
 }
 {
  const {page,context}=await setup();await edit(page);await page.setViewportSize({width:390,height:844});
  await page.locator('#analyze').focus();await page.keyboard.press('Enter');await page.locator(dialog).waitFor({state:'visible'});
  assert.equal(await page.locator('#intake-keep-corrections').evaluate(e=>document.activeElement===e),true);
  await page.keyboard.press('Tab');assert.equal(await page.locator('#intake-use-extraction').evaluate(e=>document.activeElement===e),true);
  await page.keyboard.press('Tab');assert.equal(await page.locator('#intake-cancel-replacement').evaluate(e=>document.activeElement===e),true);
  assert.ok(await page.locator(dialog).evaluate(e=>e.getBoundingClientRect().left>=0&&e.getBoundingClientRect().right<=innerWidth&&e.scrollWidth<=e.clientWidth+1));
  await page.screenshot({path:join(out,'phone-analyze-dialog.png')});
  await page.keyboard.press('Escape');assert.equal(await page.locator('#analyze').evaluate(e=>document.activeElement===e),true);
  await page.locator('#load-fixture').focus();await page.keyboard.press('Enter');await page.locator(dialog).waitFor({state:'visible'});
  await page.screenshot({path:join(out,'phone-fixture-dialog.png')});await page.keyboard.press('Escape');
  await record(page,'phone-keyboard-modal-focus-and-layout');await context.close();
 }
 assert.equal(report.external.length,0);assert.equal(report.pageErrors.length,0);
 assert.deepEqual(Object.fromEntries(await Promise.all(sourcePaths.map(async p=>[p,hash(await readFile(join(root,p)))]))),source);
 assert.deepEqual(await hashes(build),buildHashes);report.sourceAndBuildUnchanged=true;report.pass=true;
}catch(e){report.pass=false;report.failure=String(e.stack||e);throw e;}
finally{await writeFile(join(out,'receipt.json'),JSON.stringify(report,null,2)+'\n');await browser.close();await new Promise(done=>server.close(done));}
console.log(JSON.stringify({pass:report.pass,cases:report.cases.map(c=>c.id),external:report.external.length,pageErrors:report.pageErrors.length}));
