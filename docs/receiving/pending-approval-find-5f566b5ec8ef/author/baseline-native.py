from pathlib import Path
import sys,json,hashlib,subprocess,os,datetime,importlib.util
r=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');s=r/'source'
sys.path[:0]=[str(s/'web-demo/python'),str(s)]
from bridge import Demo
d=Demo();d.clock.day=datetime.date(2026,10,9)
inputs=[
"From: Alpha Client <alpha@example.test>\nSubject: Alpha research\n\n2 hours of Alpha research at $40/hr\nNet 7.\n",
"From: Beta Client <beta@example.test>\nSubject: Beta design\n\n3 hours of Beta design at £25/hr\nNet 15.\n",
"From: Gamma Client <gamma@example.test>\nSubject: Gamma copy\n\n4 hours of Gamma writing at $30/hr\nNet 30.\n"]
records=[]
def call(req):
 v=d.dispatch(req);records.append({'request':req,'reply':v});return v
for i,text in enumerate(inputs):
 ex=call({'action':'analyze','text':text})['result']
 assert len(ex['line_items'])==1 and ex['confidence']>=.5,(i,ex)
 assert not any(v['severity']=='error' for v in ex['issues']),(i,ex)
 call({'action':'draft','text':text})
 if i==0:
  a=d.snapshot()['pending'][0];call({'action':'approve','action_id':a['id']})
  call({'action':'advance','day':'2026-10-17'});call({'action':'chase'})
before=d.snapshot();calls=len(d.mock.requests);again=d.snapshot()
assert before==again and len(d.mock.requests)==calls
assert [x['kind'] for x in before['pending']].count('send_invoice')==2
assert [x['kind'] for x in before['pending']].count('send_reminder')==1
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip(),'inputs':inputs,'records':records,'snapshot':before,'mockRequests':d.mock.requests,'snapshotReadUnchanged':True,'browserFinderSourcePresent':False}
p=r/'evidence/baseline-native.json';p.write_text(json.dumps(receipt,indent=2,default=str),encoding='utf-8')
print(json.dumps({'exit':0,'pending':[(x['kind'],x['invoice_id']) for x in before['pending']],'mockRequests':calls,'receiptSHA':hashlib.sha256(p.read_bytes()).hexdigest(),'playwrightAvailable':bool(importlib.util.find_spec('playwright'))}),flush=True)
env=os.environ.copy();env['PATH']='/opt/homebrew/bin:'+env['PATH'];env['PYTHON']='/Users/me/.pyenv/versions/3.13.7/bin/python3'
q=subprocess.run(['/opt/homebrew/bin/npm','run','build'],cwd=s/'web-demo',env=env,capture_output=True,text=True,timeout=120)
print(json.dumps({'buildExit':q.returncode,'stdout':q.stdout[-1800:],'stderr':q.stderr[-1500:]}),flush=True)
(r/'evidence/baseline-build.json').write_text(json.dumps({'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr},indent=2),encoding='utf-8')
assert q.returncode==0
