from pathlib import Path
import argparse,json,datetime,threading,http.server,functools,hashlib,traceback
from playwright.sync_api import sync_playwright,expect
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--browser',required=True);parser.add_argument('--port',type=int,default=18876)
args=parser.parse_args();source=Path(__file__).resolve().parents[2];out=Path(args.output);out.mkdir()
receipt={'phase':'candidate actual staged Python Worker; explicit terminal fault and delayed-send probes','checks':[],'pageErrors':[],'external':[]}
inputs=[
'From: Alpha Client <alpha@example.test>\nSubject: Alpha research\n\n2 hours of Alpha research at $40/hr\nNet 7.',
'From: Beta Client <beta@example.test>\nSubject: Beta design\n\n3 hours of Beta design at £25/hr\nNet 15.',
'From: Gamma Client <gamma@example.test>\nSubject: Gamma copy\n\n4 hours of Gamma writing at $30/hr\nNet 30.']
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
origin='http://127.0.0.1:'+str(args.port)+'/'
server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Quiet,directory=str(source/'web-demo/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();pw=None;context=None
try:
 pw=sync_playwright().start();context=pw.chromium.launch_persistent_context(str(out/'profile'),executable_path=args.browser,headless=True,viewport={'width':1440,'height':1000})
 context.add_init_script("""(()=>{const Native=Worker;window.__approvalProbe={calls:[],replies:[],states:[],workers:[],fault:null,hold:null,release:null};
 window.Worker=class extends Native{constructor(...args){super(...args);__approvalProbe.workers.push(this);this.addEventListener('message',e=>{const m=structuredClone(e.data);if(m.id){__approvalProbe.replies.push(m);if(m.data?.state)__approvalProbe.states.push(m.data.state);}});}
 postMessage(m,...args){const p=__approvalProbe;p.calls.push(structuredClone(m));if(p.fault===m.action){p.fault=null;queueMicrotask(()=>this.dispatchEvent(new ErrorEvent('error',{message:'Authored terminal transport fault before '+m.action})));return;}
 if(p.hold===m.action){p.hold=null;p.release=()=>{p.release=null;super.postMessage(m,...args);};return;}return super.postMessage(m,...args);}};})()""")
 def route(r):
  if r.request.url.startswith(origin):r.continue_()
  else:receipt['external'].append(r.request.url);r.abort()
 context.route('**/*',route)
 page=context.pages[0];page.on('pageerror',lambda e:receipt['pageErrors'].append(str(e)));page.on('dialog',lambda d:d.accept())
 page.goto(origin);page.set_default_timeout(15000)
 def check(name,detail=None):receipt['checks'].append({'name':name,'pass':True,'detail':detail})
 def state():return page.evaluate('__approvalProbe.states.at(-1)')
 def visible():return page.locator('.approval-card:visible').evaluate_all('(xs)=>xs.map(x=>x.dataset.approvalId)')
 def action(selector):
  n=page.evaluate('__approvalProbe.replies.length');page.locator(selector).click()
  page.wait_for_function("n=>__approvalProbe.replies.length>n&&!document.querySelector('#analyze').disabled",arg=n,timeout=90000)
  v=page.evaluate('__approvalProbe.replies.at(-1)');assert v['ok'] and v['data']['ok'],v;return v['data']
 def search(text):
  box=page.locator('#approval-search');box.click();box.press('Meta+A');box.press('Backspace');box.press_sequentially(text)
 def unchanged(snap,calls):assert state()==snap and page.evaluate('__approvalProbe.calls.length')==calls
 expect(page.locator('#approval-search')).to_be_disabled();action('#engine-start')
 for i,text in enumerate(inputs):
  page.locator('#job-email').fill(text);action('#analyze');action('#draft')
  if i==0:
   a=state()['pending'][0];action('[data-approve="'+a['id']+'"]')
   day=(datetime.date.fromisoformat(state()['today'])+datetime.timedelta(days=8)).isoformat()
   page.locator('#demo-date').fill(day);action('#advance-clock');action('#run-chase')
 pending=state()['pending'];assert len(pending)==3
 reminder=next(a for a in pending if a['kind']=='send_reminder')
 beta=next(a for a in pending if 'beta@' in a['summary'].lower())
 gamma=next(a for a in pending if 'gamma@' in a['summary'].lower())
 assert visible()==[a['id'] for a in pending];check('Actual Python produces one reminder and two original invoice cards')
 snapshot=state();calls=page.evaluate('__approvalProbe.calls.length')
 page.evaluate("window.__originalCards=[...document.querySelectorAll('.approval-card')];window.__originalProposalText=__originalCards.map(x=>x.querySelector('.approval-preview').textContent)")
 page.locator('[data-rejection-reason="'+beta['id']+'"]').fill('Authored reason stays on this action')
 search('  BETA@EXAMPLE.TEST  ');assert visible()==[beta['id']];unchanged(snapshot,calls)
 assert page.evaluate("__originalCards.every(x=>x.isConnected)&&__originalCards.every((x,i)=>x.querySelector('.approval-preview').textContent===__originalProposalText[i])")
 check('Real-key literal case-insensitive recipient search preserves card nodes, payloads and Worker state')
 page.locator('#approval-kind').select_option('send_reminder');assert visible()==[];expect(page.locator('#approval-filter-empty')).to_be_visible();unchanged(snapshot,calls)
 check('Type/text intersection shows an explicit no-match state without queue removal')
 page.locator('#approval-filter-clear').click();assert visible()==[a['id'] for a in pending]
 expect(page.locator('[data-rejection-reason="'+beta['id']+'"]')).to_have_value('Authored reason stays on this action')
 unchanged(snapshot,calls);check('Clear restores original order and unsent rejection reason without effects')
 search(beta['id']);assert visible()==[beta['id']];search(gamma['invoice_id']);assert visible()==[gamma['id']]
 search('.*');assert visible()==[];unchanged(snapshot,calls);check('Exact action/invoice IDs are searchable and regex metacharacters stay literal')
 page.locator('#approval-filter-clear').click();page.locator('#approval-kind').select_option('send_reminder');assert visible()==[reminder['id']]
 page.locator('.approval-panel').scroll_into_view_if_needed();page.screenshot(path=str(out/'desktop-reminder.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.locator('.approval-filters').scroll_into_view_if_needed();page.screenshot(path=str(out/'phone-reminder.png'),full_page=True)
 assert page.locator('.approval-filters').evaluate('e=>e.scrollWidth<=e.clientWidth') and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 unchanged(snapshot,calls);check('Desktop and 390px complete filter/card layout has no horizontal overflow')
 page.set_viewport_size({'width':1440,'height':1000})
 page.evaluate("__approvalProbe.hold='chase'");page.locator('#run-chase').click()
 page.wait_for_function('__approvalProbe.release!==null');expect(page.locator('#approval-search')).to_be_disabled();expect(page.locator('#approval-kind')).to_be_disabled()
 expect(page.locator('#approval-filter-note')).to_contain_text('Python is working');assert page.locator('#approval-kind').input_value()=='send_reminder'
 n=page.evaluate('__approvalProbe.replies.length');page.evaluate('__approvalProbe.release()')
 page.wait_for_function("n=>__approvalProbe.replies.length>n&&!document.querySelector('#analyze').disabled",arg=n)
 assert visible()==[reminder['id']];assert page.locator('#approval-kind').input_value()=='send_reminder'
 check('Held real chase send disables controls; accepted snapshot rebinds while retaining selected type')
 page.locator('#approval-filter-clear').click();search('beta@example.test');page.locator('#approval-kind').select_option('send_invoice')
 action('[data-approve="'+beta['id']+'"]')
 last=page.evaluate('__approvalProbe.calls.at(-1)');assert last['action']=='approve' and last['payload']['action_id']==beta['id']
 assert beta['id'] not in [x['id'] for x in state()['pending']]
 assert page.locator('#approval-search').input_value()=='beta@example.test' and visible()==[]
 check('Filtered approval submits the exact original ID and retains filters after accepted removal')
 search('gamma@example.test');expect(page.locator('[data-rejection-reason="'+gamma['id']+'"]')).to_be_visible()
 page.locator('[data-rejection-reason="'+gamma['id']+'"]').fill('Fictional recipient review, not sent')
 action('[data-reject="'+gamma['id']+'"]')
 last=page.evaluate('__approvalProbe.calls.at(-1)');assert last['action']=='reject' and last['payload']=={'action_id':gamma['id'],'reason':'Fictional recipient review, not sent'}
 assert [a['id'] for a in state()['pending']]==[reminder['id']];check('Filtered rejection uses unchanged reason/ID handler and preserves the hidden reminder')
 page.locator('#approval-filter-clear').click();search('alpha');page.locator('#approval-kind').select_option('send_reminder')
 page.evaluate("__approvalProbe.fault='reset'");page.locator('#reset-sandbox').click()
 page.wait_for_function("document.querySelector('#engine-status').textContent==='PYTHON UNAVAILABLE'")
 assert page.locator('#approval-search').input_value()=='alpha' and page.locator('#approval-kind').input_value()=='send_reminder'
 expect(page.locator('#approval-search')).to_be_disabled();expect(page.locator('#approval-filter-note')).to_contain_text('inactive')
 assert state()['pending'][0]['id']==reminder['id'];check('Failed reset transport retains the query/type and marks the last queue inactive')
 page.evaluate("__approvalProbe.fault='init'");page.locator('#engine-start').click()
 page.wait_for_function("!document.querySelector('#engine-start').disabled&&document.querySelector('#engine-status').textContent==='PYTHON UNAVAILABLE'")
 assert page.locator('#approval-search').input_value()=='alpha' and page.locator('#approval-kind').input_value()=='send_reminder'
 check('Failed explicit restart keeps both filters without replay')
 action('#engine-start');assert state()['pending']==[] and state()['ledger']==[]
 assert page.locator('#approval-search').input_value()=='' and page.locator('#approval-kind').input_value()=='all'
 check('Successful actual empty restart clears filters only after its accepted state')
 page.locator('#job-email').fill(inputs[1]);action('#analyze');action('#draft');search('beta');page.locator('#approval-kind').select_option('send_invoice')
 action('#reset-sandbox');assert state()['pending']==[] and state()['ledger']==[]
 assert page.locator('#approval-search').input_value()=='' and page.locator('#approval-kind').input_value()=='all'
 check('Successful actual Reset clears filters and current queue')
 receipt.update(page.evaluate('({calls:__approvalProbe.calls,replies:__approvalProbe.replies,states:__approvalProbe.states})'))
 assert not receipt['pageErrors'] and not receipt['external']
 receipt['success']=True
except Exception as e:
 receipt['success']=False;receipt['error']=repr(e);receipt['traceback']=traceback.format_exc()
 if context and context.pages:
  try:
   receipt.update(context.pages[-1].evaluate('({calls:__approvalProbe.calls,replies:__approvalProbe.replies,states:__approvalProbe.states})'))
   context.pages[-1].screenshot(path=str(out/'failure.png'),full_page=True)
  except Exception:pass
finally:
 if context:context.close()
 if pw:pw.stop()
 server.shutdown();server.server_close()
 receipt['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 receipt['source']={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ['web-demo/src/approval-filter.ts','web-demo/src/main.ts','web-demo/src/approval-preview.ts','web-demo/python/bridge.py','ledgerly/agent.py']}
 print(json.dumps({'exit':0 if receipt.get('success') else 1,'checks':len(receipt['checks']),'error':receipt.get('error'),'pageErrors':receipt['pageErrors'],'external':receipt['external']}),flush=True)
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
raise SystemExit(0 if receipt['success'] else 1)
