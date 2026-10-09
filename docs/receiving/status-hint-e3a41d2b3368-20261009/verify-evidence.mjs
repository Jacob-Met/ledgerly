#!/usr/bin/env node
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
const dir=dirname(fileURLToPath(import.meta.url)),root=resolve(dir,'../../..');
const sha=b=>createHash('sha256').update(b).digest('hex');
const m=JSON.parse(await readFile(join(dir,'EVIDENCE-MANIFEST.json'),'utf8'));
const compressed=await readFile(join(dir,m.archive.path));
assert.equal(compressed.length,m.archive.bytes);assert.equal(sha(compressed),m.archive.sha256);
const bytes=gunzipSync(compressed);
assert.equal(bytes.length,m.archive.uncompressed_bytes);assert.equal(sha(bytes),m.archive.uncompressed_sha256);
const bundle=JSON.parse(bytes),expected=new Map(m.members.map(x=>[x.path,x])),seen=new Map();
assert.equal(expected.size,m.members.length);
for(const f of bundle.files){
 assert.ok(!f.path.startsWith('/')&&!f.path.split('/').includes('..')&&!seen.has(f.path));
 const e=expected.get(f.path);assert.ok(e);
 const data=Buffer.from(f.base64,'base64');
 assert.equal(data.length,f.bytes);assert.equal(data.length,e.bytes);
 assert.equal(sha(data),f.sha256);assert.equal(sha(data),e.sha256);seen.set(f.path,data);
}
assert.equal(seen.size,expected.size);
for(const f of m.candidate_files)assert.equal(sha(await readFile(join(root,f.path))),f.sha256);
const prefix='web-demo/status-receiving/';
const baseline=JSON.parse(seen.get(prefix+'baseline-vitest.json'));
const candidate=JSON.parse(seen.get(prefix+'candidate-vitest.json'));
assert.equal(baseline.testResults.length,1);assert.equal(candidate.testResults.length,1);
assert.equal(baseline.numPassedTests,5);assert.equal(baseline.numFailedTests,6);
assert.equal(candidate.success,true);assert.equal(candidate.numPassedTests,11);assert.equal(candidate.numFailedTests,0);
assert.deepEqual(await readFile(join(dir,'NATIVE-GATES.json')),seen.get(prefix+'NATIVE-GATES.json'));
assert.deepEqual(await readFile(join(dir,'BUILD-MANIFEST.json')),seen.get(prefix+'BUILD-MANIFEST.json'));
const gates=JSON.parse(seen.get(prefix+'NATIVE-GATES.json'));assert.equal(gates.status,'pass');
assert.equal(gates.borrowed_dependencies_unchanged,true);
console.log(JSON.stringify({status:'pass',members:seen.size,baseline:{passed:5,failed:6},candidate:{passed:11,failed:0},source_files:m.candidate_files.length,browser_acceptance:false,public_deployment:false,claim:'Evidence content and source custody only; no runtime tests or deployment performed by this verifier.'}));
