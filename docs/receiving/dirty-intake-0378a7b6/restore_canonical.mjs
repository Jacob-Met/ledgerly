import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=path.resolve(process.argv[2]);
const proof=path.join(root,'docs/receiving/dirty-intake-0378a7b6');
const sha=b=>createHash('sha256').update(b).digest('hex');
const git=(...args)=>execFileSync('git',['-C',root,...args],{maxBuffer:32*1024*1024});
const owned=new Set(['web-demo/src/main.ts','web-demo/tests/engine-recovery.test.ts','web-demo/README.md']);
const rows=[],changes=[];
for(const entry of git('ls-tree','-rz','HEAD').toString().split('\0').filter(Boolean)){
 const split=entry.indexOf('\t'),[mode,type,blob]=entry.slice(0,split).split(' '),name=entry.slice(split+1);
 if(type!=='blob'||owned.has(name))continue;
 const file=path.join(root,name),current=fs.readFileSync(file),canonical=git('cat-file','blob',blob);
 if(current.equals(canonical)){rows.push({path:name,mode,blob,unchanged:true,sha256:sha(canonical)});continue;}
 if(!Buffer.from(current.toString('utf8'),'utf8').equals(current)||!Buffer.from(current.toString('utf8').replaceAll('\r\n','\n'),'utf8').equals(canonical))throw Error('Non-newline difference at '+name);
 changes.push({name,file,current,canonical});
 rows.push({path:name,mode,blob,beforeSha256:sha(current),canonicalSha256:sha(canonical),transformation:'replace CRLF with LF only'});
}
const receipt={head:git('rev-parse','HEAD').toString().trim(),at:new Date().toISOString(),ownedExcluded:[...owned],unownedCount:rows.length,newlineConverted:changes.length,records:rows};
fs.writeFileSync(path.join(proof,'original-checkout-line-endings.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
for(const c of changes)fs.writeFileSync(c.file,c.canonical);
const doc=path.join(root,'web-demo/README.md');fs.writeFileSync(doc,fs.readFileSync(doc,'utf8').replaceAll('\r\n','\n'));
for(const row of rows){const b=fs.readFileSync(path.join(root,row.path));if(sha(b)!==(row.canonicalSha256??row.sha256))throw Error('Final mismatch '+row.path);}
console.log(JSON.stringify({unownedCount:rows.length,newlineConverted:changes.length,unownedCanonical:true,manifestSha256:sha(fs.readFileSync(path.join(proof,'original-checkout-line-endings.json')))}));
