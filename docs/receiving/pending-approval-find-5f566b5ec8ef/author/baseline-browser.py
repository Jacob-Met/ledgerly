from pathlib import Path
import json,datetime,threading,http.server,functools,hashlib,traceback
from playwright.sync_api import sync_playwright,expect
root=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');source=root/'source';out=root/'evidence/browser-baseline';out.mkdir()
receipt={'phase':'unchanged original with actual staged Python Worker','calls':[],'replies':[],'pageErrors':[],'external':[]}
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',18875),functools.partial(Quiet,directory=str(source/'web-demo/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();pw=None;context=None
try:
 pw=sync_playwright().start();context=pw.chromium.launch_persistent_context(str(out/'profile'),executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,viewport={'width':1440,'height':1000})
 context.add_init_script("""(()=>{const Native=Worker;window.__approvalProbe={calls:[],replies:[],states:[],workers:[]};
 window.Worker=class extends Native{constructor(...args){super(...args);__approvalProbe.workers.push(this);this.addEventListener('message',e=>{const m=structuredClone(e.data);if(m.id){__approvalProbe.replies.push(m);if(m.data?.state)__approvalProbe.states.push(m.data.state);}});}
 postMessage(m,...args){__approvalProbe.calls.push(structuredClone(m));return super.postMessage(m,...args);}};})()""")
 def route(r):
  if r.request.url.startswith('http://127.0.0.1:18875/'):r.continue_()
  else:receipt['external'].append(r.request.url);r.abort()
 context.route('**/*',route)
 page=context.pages[0];page.on('pageerror',lambda e:receipt['pageErrors'].append(str(e)))
 page.goto('http://127.0.0.1:18875/');page.set_default_timeout(15000)
 def state():return page.evaluate('__approvalProbe.states.at(-1)')
 def action(selector):
  n=page.evaluate('__approvalProbe.replies.length');page.locator(selector).click()
  page.wait_for_function("n=>__approvalProbe.replies.length>n&&!document.querySelector('#analyze').disabled",arg=n,timeout=90000)
  v=page.evaluate('__approvalProbe.replies.at(-1)');assert v['ok'] and v['data']['ok'],v;return v['data']
 action('#engine-start')
 inputs=json.loads((root/'evidence/baseline-native.json').read_text())['inputs']
 for i,text in enumerate(inputs):
  page.locator('#job-email').fill(text);action('#analyze');action('#draft')
  if i==0:
   a=state()['pending'][0];action('[data-approve="'+a['id']+'"]')
   day=(datetime.date.fromisoformat(state()['today'])+datetime.timedelta(days=8)).isoformat()
   page.locator('#demo-date').fill(day);action('#advance-clock');action('#run-chase')
 pending=state()['pending'];assert len(pending)==3
 assert [v['kind'] for v in pending].count('send_invoice')==2
 assert [v['kind'] for v in pending].count('send_reminder')==1
 assert page.locator('.approval-card').count()==3
 assert page.locator('.approval-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.approvalId)')==[a['id'] for a in pending]
 assert page.locator('#approval-search,#approval-kind').count()==0
 snap=state();calls=page.evaluate('__approvalProbe.calls.length')
 page.locator('.approval-panel').scroll_into_view_if_needed();page.screenshot(path=str(out/'original-queue.png'),full_page=True)
 assert state()==snap and page.evaluate('__approvalProbe.calls.length')==calls
 receipt.update(page.evaluate('({calls:__approvalProbe.calls,replies:__approvalProbe.replies,states:__approvalProbe.states})'))
 receipt['success']=True;receipt['witness']='Three exact native pending cards, no pending query/type control, no extra calls on read.'
 assert not receipt['pageErrors'] and not receipt['external']
except Exception as e:
 receipt['success']=False;receipt['error']=repr(e);receipt['traceback']=traceback.format_exc()
 if context and context.pages:
  try:context.pages[-1].screenshot(path=str(out/'failure.png'),full_page=True)
  except Exception:pass
finally:
 if context:context.close()
 if pw:pw.stop()
 server.shutdown();server.server_close()
 receipt['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 receipt['source']={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ['web-demo/src/main.ts','web-demo/src/approval-preview.ts','web-demo/python/bridge.py','ledgerly/agent.py']}
 print(json.dumps({'exit':0 if receipt.get('success') else 1,'witness':receipt.get('witness'),'error':receipt.get('error'),'pageErrors':receipt['pageErrors'],'external':receipt['external']}),flush=True)
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
raise SystemExit(0 if receipt['success'] else 1)
