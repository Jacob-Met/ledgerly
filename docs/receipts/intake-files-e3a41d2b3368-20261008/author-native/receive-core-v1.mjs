import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, openSync, closeSync, fsyncSync, statfsSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {stripTypeScriptTypes} from 'node:module';
import vm from 'node:vm';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const paths = ['src/intake-file.ts', 'src/intake-file-ui.ts', 'src/main.ts', 'src/review.ts', 'src/intake-file.css', 'tests/intake-file.test.ts', 'index.html'];
const hash = value => createHash('sha256').update(value).digest('hex');
const sources = () => Object.fromEntries(paths.map(path => [path, hash(readFileSync(resolve(root, 'candidate/web-demo', path)))]));
const before = sources();
const receipt = {schema:'ledgerly.intake-native-core/1',status:'running',at:new Date().toISOString(),node:process.version,platform:process.platform,arch:process.arch,sourceBefore:before,groups:[],assertions:0,limits:'Native exact TypeScript codec and source syntax receiving only. Full Vite semantic build, Python Worker and browser behavior are separate gates.'};
const ok = (condition, label) => { receipt.assertions++; assert.ok(condition,label); };
const eq = (a,b,label) => { receipt.assertions++; assert.deepEqual(a,b,label); };
const refuses = (fn,label) => { receipt.assertions++; assert.throws(fn,label); };
const group = (name, fn) => { const begin=receipt.assertions;try{fn();receipt.groups.push({name,status:'pass',assertions:receipt.assertions-begin});}catch(error){receipt.groups.push({name,status:'fail',assertions:receipt.assertions-begin,error:String(error),stack:error.stack});} };
const {encodeIntakeFile:encode,decodeIntakeFile:decode,MAX_INTAKE_BYTES:limit,MAX_INTAKE_LINES:lines} =
  await import(pathToFileURL(resolve(root, 'candidate/web-demo/src/intake-file.ts')).href);
const at='2026-10-08T16:00:00.000Z';
const fields=()=>({client_name:'<img src=x onerror=fictional()> 雨',client_email:'',due_days:'unfinished',amount_paid:'-0.001',line_items:[{desc:'Résumé & work',qty:'',unit_price:'1,200.00',currency:'ZZZ',unit:''}]});
const value=()=>JSON.parse(encode({sourceText:'Fictional email\n🙂',fields:fields()},at).text);
group('source-only exact round trip and bounded filename',()=>{
 const artifact=encode({sourceText:'Original\nsource & <text> 雨\n',fields:null},at);
 eq(decode(artifact.text),{format:'ledgerly-intake',version:1,saved_at:at,source_text:'Original\nsource & <text> 雨\n',review_fields:null});
 eq(artifact.filename,'ledgerly-intake-20261008T160000000Z.json');
 ok(artifact.text.endsWith('\n'));
});
group('unfinished strings remain literal and no derived authority enters the format',()=>{
 const original=fields(),data=decode(encode({sourceText:'Source',fields:original},at).text);
 eq(data.review_fields,original);
 eq(Object.keys(data),['format','version','saved_at','source_text','review_fields']);
 eq(Object.keys(data.review_fields),['client_name','client_email','due_days','amount_paid','line_items']);
 eq(data.review_fields.line_items[0].unit_price,'1,200.00');
});
group('caller and decoded object mutations do not cross file boundaries',()=>{
 const input=fields(),artifact=encode({sourceText:'Source',fields:input},at);
 input.line_items[0].qty='changed';
 const first=decode(artifact.text);first.review_fields.line_items[0].qty='second change';
 eq(decode(artifact.text).review_fields,fields());
});
group('strict outer shape and version admission',()=>{
 for(const bad of [null,[],true,7,'file'])refuses(()=>decode(JSON.stringify(bad)));
 for(const [key,bad] of [['format','invoice'],['version','1'],['version',2],['source_text',1]]){
  const data=value();data[key]=bad;refuses(()=>decode(JSON.stringify(data)));
 }
});
group('no saved review, confirmation, invoice, ledger or unknown metadata can be admitted',()=>{
 for(const key of ['review_id','confirmed','invoice_id','pending','ledger','confidence','__proto__']){
  const data=value();Object.defineProperty(data,key,{value:'forged',enumerable:true});refuses(()=>decode(JSON.stringify(data)));
 }
 const data=value();data.review_fields.confidence=1;refuses(()=>decode(JSON.stringify(data)));
});
group('strict raw field and line item shape',()=>{
 for(const key of ['client_name','client_email','due_days','amount_paid']){
  const data=value();data.review_fields[key]=1;refuses(()=>decode(JSON.stringify(data)));
 }
 for(const bad of [null,[],true,'item',{desc:'partial'}]){
  const data=value();data.review_fields.line_items=[bad];refuses(()=>decode(JSON.stringify(data)));
 }
 const data=value();data.review_fields.line_items[0].total='3.00';refuses(()=>decode(JSON.stringify(data)));
});
group('saved time describes a valid exact UTC instant',()=>{
 for(const bad of ['2026-02-30T00:00:00.000Z','2026-10-08T16:00:00Z','2026-10-08T09:00:00.000-07:00','not a date',null]){
  const data=value();data.saved_at=bad;refuses(()=>decode(JSON.stringify(data)));
 }
});
group('line count and original ordering remain bounded',()=>{
 const f=fields();f.line_items=[];eq(decode(encode({sourceText:'',fields:f},at).text).review_fields.line_items,[]);
 f.line_items=Array.from({length:lines},(_,i)=>({desc:String(i),qty:'1',unit_price:'001.00',currency:'USD',unit:''}));
 eq(decode(encode({sourceText:'',fields:f},at).text).review_fields.line_items,f.line_items);
 f.line_items.push({...f.line_items[0]});refuses(()=>encode({sourceText:'',fields:f},at));
 const data=value();data.review_fields=f;refuses(()=>decode(JSON.stringify(data)));
});
group('UTF-8 limit admits exact boundary and refuses overflow before parsing',()=>{
 const base=encode({sourceText:'',fields:null},at).text;
 const remaining=limit-Buffer.byteLength(base);
 const exact=encode({sourceText:'a'.repeat(remaining),fields:null},at).text;
 eq(Buffer.byteLength(exact),limit);
 eq(decode(exact).source_text.length,remaining);
 refuses(()=>encode({sourceText:'a'.repeat(remaining+1),fields:null},at));
 refuses(()=>decode(exact+' '));
 refuses(()=>encode({sourceText:'🙂'.repeat(Math.ceil(remaining/4)+1),fields:null},at));
});
group('JSON key order does not alter values and malformed JSON fails closed',()=>{
 const data=value();eq(decode(JSON.stringify(Object.fromEntries(Object.entries(data).reverse()))),data);
 for(const bad of ['','{','undefined','{"format":'])refuses(()=>decode(bad));
});
group('all candidate TypeScript source parses under native type erasure',()=>{
 for(const name of ['src/intake-file.ts','src/intake-file-ui.ts','src/main.ts','tests/intake-file.test.ts']){
  const source=readFileSync(resolve(root,'candidate/web-demo',name),'utf8');
  const js=stripTypeScriptTypes(source,{mode:'strip'});
  ok(new vm.SourceTextModule(js,{identifier:name}));
 }
});
receipt.sourceAfter=sources();
eq(receipt.sourceAfter,before,'all frozen source bytes unchanged');
receipt.status=receipt.groups.every(g=>g.status==='pass')?'pass':'fail';
receipt.passed=receipt.groups.filter(g=>g.status==='pass').length;
receipt.failed=receipt.groups.filter(g=>g.status==='fail').length;
receipt.driverSha256=hash(readFileSync(fileURLToPath(import.meta.url)));
const output=resolve(root,'receiving/native-core-v1.json');
const fd=openSync(output,'wx',0o600);
try{writeFileSync(fd,JSON.stringify(receipt,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}
console.log(JSON.stringify(receipt));
if(receipt.failed)process.exitCode=1;
