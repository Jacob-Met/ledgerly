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
const source=Object.fromEntries(await Promise.all(sourcePaths.map(async p=>[p,hash(await readFile(join(root,p)))])));
async function hashes(dir,prefix=''){const result={};for(const e of await readdir(dir,{withFileTypes:true})){const p=prefix+e.name;if(e.isDirectory())Object.assign(result,await hashes(join(dir,e.name),p+'/'));else if(e.isFile())result[p]=hash(await readFile(join(dir,e.name)));}return result;}
const buildHashes=await hashes(build);
const report={head:git('rev-parse','HEAD'),tree:git('rev-parse','HEAD^{tree}'),at:new Date().toISOString(),driverSha256:hash(await readFile(new URL(import.meta.url))),source,buildHashes,cases:[],external:[],pageErrors:[],serverRequests:[]};
const server=createServer(async(req,res)=>{try{const p=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname),file=resolve(build,'.'+(p==='/'?'/index.html':p));if(!file.startsWith(build+sep))throw Error('path');const data=await readFile(file);report.serverRequests.push({path:p,sha256:hash(data)});res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.svg':'image/svg+xml','.zip':'application/zip'})[extname(file)]||'application/octet-stream'}).end(data);}catch{res.writeHead(404).end();}});
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
 await page.addInitScript(()=>{const N=Worker,p=window.__dirtyProbe={calls:[],replies:[],states:[]};window.Worker=class extends N{constructor(...a){super(...a);this.addEventListener('message',e=>{if(e.data?.data){p.replies.push(JSON.parse(JSON.stringify(e.data)));if(e.data.data.state)p.states.push(JSON.parse(JSON.stringify(e.data.data.state)));}});}postMessage(...a){p.calls.push(JSON.parse(JSON.stringify(a[0])));return super.postMessage(...a);}};});
 await page.goto(origin);
 assert.equal((await action(page,'#engine-start')).ok,true);
 await page.locator('#load-fixture').click();
 await page.waitForFunction(()=>!document.querySelector('#analyze').disabled&&document.querySelector('#job-email').value.length>0);
 assert.equal((await action(page,'#analyze')).ok,true);
 await page.locator('#review-editor > summary').click();
 return {page,context,dialogs};
}
async function edit(page){await page.locator('#review-client-name').fill('Edited recipient Ω');await page.locator('#review-client-email').fill('reviewed@example.test');await page.locator('#review-due-days').fill('45');await page.locator('#review-line-0-desc').fill('Corrected <work> & revision');await page.locator('#review-line-0-qty').fill('7');return fields(page);}
try{
 for(const mode of ['source-edit','reanalyze','fixture-load']){
  const {page,context,dialogs}=await setup();const before=await edit(page),originalSource=await page.locator('#job-email').inputValue(),beforeProbe=await probe(page);
  if(mode==='source-edit')await page.locator('#job-email').fill(originalSource+'\nA reviewed spelling correction.');
  else if(mode==='reanalyze')await action(page,'#analyze');
  else {await page.locator('#fixture-select').selectOption({index:1});await page.locator('#load-fixture').click();await page.waitForFunction(()=>!document.querySelector('#analyze').disabled);}
  const after=await fields(page),afterProbe=await probe(page);
  assert.notDeepEqual(after,before,'Original app demonstrates destructive replacement '+mode);
  assert.equal(dialogs.length,0,'No original discard decision');
  assert.deepEqual(afterProbe.states.at(-1).ledger,beforeProbe.states.at(-1).ledger,'Intake did not change existing ledger');
  const row={id:mode,expectedPreservation:false,baselineFailureObserved:true,before,after,dialogs,originalSource,afterSource:await page.locator('#job-email').inputValue(),callsBefore:beforeProbe.calls.length,callsAfter:afterProbe.calls.length};
  report.cases.push(row);await writeFile(join(out,mode+'-probe.json'),JSON.stringify(afterProbe,null,2)+'\n');
  await page.screenshot({path:join(out,mode+'.png'),fullPage:true});await context.close();console.log('EXPECTED LOSS '+mode);
 }
 {
  const {page,context,dialogs}=await setup();const before=await fields(page);await action(page,'#analyze');assert.deepEqual(await fields(page),before);assert.equal(dialogs.length,0);
  report.cases.push({id:'ordinary-clean-reanalysis',pass:true});await context.close();console.log('PASS ordinary clean reanalysis');
 }
 {
  const {page,context}=await setup();const corrected=await edit(page);await page.locator('#review-confirm').check();
  const checked=await action(page,'#review-check');assert.equal(checked.ok,true);assert.equal(checked.result.valid,true);assert.deepEqual(await fields(page),corrected);
  const drafted=await action(page,'#draft');assert.equal(drafted.ok,true);
  const current=(await probe(page)).states.at(-1);assert.equal(current.ledger.length,1);assert.equal(current.pending.length,1);assert.equal(current.ledger[0].status,'DRAFT');
  assert.equal(await page.locator('#draft').isDisabled(),true);
  const approved=await action(page,'button[data-approve]');assert.equal(approved.ok,true);assert.equal(approved.result.approved,true);
  assert.equal((await probe(page)).states.at(-1).ledger[0].status,'SENT');
  report.cases.push({id:'real-correct-check-draft-separate-approval',pass:true});await writeFile(join(out,'ordinary-draft-probe.json'),JSON.stringify(await probe(page),null,2)+'\n');await context.close();console.log('PASS corrected native workflow');
 }
 assert.equal(report.external.length,0);assert.equal(report.pageErrors.length,0);
 assert.deepEqual(Object.fromEntries(await Promise.all(sourcePaths.map(async p=>[p,hash(await readFile(join(root,p)))]))),source);
 assert.deepEqual(await hashes(build),buildHashes);
 report.sourceAndBuildUnchanged=true;report.pass=true;
}catch(e){report.pass=false;report.failure=String(e.stack||e);throw e;}
finally{await writeFile(join(out,'receipt.json'),JSON.stringify(report,null,2)+'\n');await browser.close();await new Promise(done=>server.close(done));}
console.log(JSON.stringify({pass:report.pass,cases:report.cases.map(c=>({id:c.id,pass:c.pass,baselineFailureObserved:c.baselineFailureObserved})),external:report.external.length,pageErrors:report.pageErrors.length}));
