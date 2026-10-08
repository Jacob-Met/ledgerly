import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const app=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.resolve(app,'..');
const copy=(source,target)=>{fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(source,target);};
for(const name of ['__init__.py','agent.py','extract.py','paypal.py'])copy(path.join(root,'ledgerly',name),path.join(app,'public','python','ledgerly',name));
for(const name of ['bridge.py','review.py','invoice_details.py','review_history.py'])copy(path.join(app,'python',name),path.join(app,'public','python',name));
for(const name of ['pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json'])copy(path.join(app,'node_modules','pyodide',name),path.join(app,'public','pyodide',name));
fs.cpSync(path.join(root,'fixtures'),path.join(app,'public','fixtures'),{recursive:true});

console.log('Staged the real Python core, fictional fixtures and self-hosted Pyodide assets.');
