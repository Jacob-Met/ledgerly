from pathlib import Path
import hashlib,json,subprocess,datetime,time,traceback
from playwright.sync_api import sync_playwright
root=Path('/Users/me/ledgerly-approval-find-peer-20261009-5f566b5ec8ef')
owner=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef/source/web-demo')
out=root/'controller-literal-fixed';out.mkdir(exist_ok=False)
pins={'src/approval-filter.ts':'2297f6a5550ddf0bdfccd4eb56ce3839d29f8f9626a879226b1fd7f46ef568f7'}
files=[owner/'src/approval-filter.ts',owner/'src/approval-preview.ts',root/'blind-expectations.json',root/'controller-literal-fixed.js']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
assert before[str(owner/'src/approval-filter.ts')]==pins['src/approval-filter.ts']
assert before[str(root/'blind-expectations.json')]=='cbe55c5df514f15c090c6a0c9860df12cfa6203d4db51784eed9d3760bed25bd'
node="""const fs=require('node:fs');const ts=require(process.argv[1]);for(const p of process.argv.slice(2)){const s=ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;console.log(JSON.stringify({path:p,source:s}));}"""
comp=subprocess.run(['/opt/homebrew/bin/node','-e',node,str(owner/'node_modules/typescript'),str(files[0]),str(files[1])],capture_output=True,text=True,timeout=30)
(out/'transpile.log').write_text(comp.stdout+comp.stderr)
assert comp.returncode==0,comp.stderr
compiled=[json.loads(x) for x in comp.stdout.splitlines()]
receipt={'actor':'chatgpt:5f566b5ec8ef:coordination','boundary':'Independent real DOM controller on exact module and unchanged real renderer; no Python/Agent/app integration or provider action','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'transpileExit':comp.returncode,'pageErrors':[],'requests':[]}
start=time.monotonic();pw=None;context=None
try:
 pw=sync_playwright().start()
 context=pw.chromium.launch_persistent_context(str(out/'profile'),executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,viewport={'width':900,'height':700})
 context.route('**/*',lambda r:(receipt['requests'].append(r.request.url),r.abort()))
 page=context.pages[0];page.on('pageerror',lambda e:receipt['pageErrors'].append(str(e)))
 page.set_content('<!doctype html><html><body></body></html>')
 for name,c in zip(['peerFilter','peerRenderer'],compiled):
  page.add_script_tag(content='window.'+name+'=(()=>{const exports={};'+c['source']+';return exports;})();')
 receipt['browser']=context.browser.version if context.browser else 'persistent Chrome'
 result=page.evaluate((root/'controller-literal-fixed.js').read_text())
 receipt['result']=result;receipt['success']=result['passed']==result['total'] and not receipt['pageErrors'] and not receipt['requests']
except Exception as e:
 receipt['success']=False;receipt['error']=repr(e);receipt['traceback']=traceback.format_exc()
finally:
 if context:context.close();receipt['contextClosed']=True
 if pw:pw.stop()
 receipt['seconds']=time.monotonic()-start
 receipt['after']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 receipt['unchanged']=before==receipt['after']
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
raise SystemExit(0 if receipt['success'] and receipt['unchanged'] else 1)
