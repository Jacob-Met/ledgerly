// Read-only custody verifier; no browser invocation or reclassification of the original failed run.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
const root=dirname(fileURLToPath(import.meta.url));
const sha=b=>createHash('sha256').update(b).digest('hex');
const m=JSON.parse(readFileSync(resolve(root,'RAIDER-ARCHIVE-MANIFEST.json'),'utf8'));
const packed=readFileSync(resolve(root,m.archive));assert.equal(packed.length,98635);assert.equal(sha(packed),'56881f8685374992210a663301a96f0f8f2b7068ca8ce2da54e8a6ed6c7f0e90');
const raw=gunzipSync(packed,{maxOutputLength:289978});assert.equal(raw.length,289978);assert.equal(sha(raw),'faad13a633b5a105c5a0b4c8412ac287f09ea9bef4930e0b424602da65256aa6');
const p=JSON.parse(raw),files=new Map();assert.equal(p.entries.length,16);assert.equal(m.entries.length,16);
for(const e of p.entries){assert(!files.has(e.path));const b=Buffer.from(e.base64,'base64');assert.equal(b.length,e.bytes);assert.equal(sha(b),e.sha256);const x=m.entries.find(x=>x.path===e.path);assert(x);assert.equal(x.bytes,b.length);assert.equal(x.sha256,sha(b));files.set(e.path,b);}
assert.equal([...files.values()].reduce((n,b)=>n+b.length,0),215647);
for(const[n,native]of[['raider-receive-status.mjs','receive-status.mjs'],['raider-receive-supervised.py','receive-supervised.py']])assert.deepEqual(readFileSync(resolve(root,n)),files.get(native));
const s=JSON.parse(files.get('SUPERVISOR.json'));assert.equal(s.supervision_passed,false);assert.equal(s.node_exit_code,1);assert(s.node_handle_signaled&&s.job_closed);assert.deepEqual(Buffer.from(s.stdout_base64,'base64'),files.get('node.stdout.txt'));assert.deepEqual(Buffer.from(s.stderr_base64,'base64'),files.get('node.stderr.txt'));
const r=JSON.parse(files.get('run-20261009T062423116Z/RESULTS.json'));assert.equal(r.status,'failed');assert.equal(r.groups.length,0);assert.equal(r.preflightAssets.length,31);assert.equal(r.browserAssets.length,0);assert(r.sourceUnchanged&&r.buildUnchanged&&r.runtimeUnchanged);
console.log(JSON.stringify({custody:'pass',files:16,memberBytes:215647,originalApplicationResult:'failed',browserGroups:0,actualBrowserResponses:0,preflightPrivateHttpAssets:31,rawOriginalFilesPreserved:true}));
