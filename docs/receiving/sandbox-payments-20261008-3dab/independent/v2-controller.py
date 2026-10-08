from pathlib import Path
import json,hashlib,difflib,subprocess,sys,shutil
root=Path('/dev/shm/estate-runtime-ledger-payment-review-3dab')
mf=root/'owner-source-freeze-v2.json';raw=mf.read_bytes()
if hashlib.sha256(raw).hexdigest()!='0c0576bacea4c05d662157d1fd8e3dcf5594a03b56cec792bac2ceefc85ee816':raise RuntimeError('freeze mismatch')
pins=json.loads(raw)
def guard():
 out={}
 for label,s in pins['subjects'].items():
  out[label]={}
  for rel,m in s['files'].items():
   b=(Path(s['path'])/rel).read_bytes()
   sha=hashlib.sha256(b).hexdigest()
   if sha!=m['sha256']:raise RuntimeError('source mismatch '+rel)
   blob=hashlib.sha1(('blob '+str(len(b))+'\0').encode()+b).hexdigest()
   if blob!=m['git_blob']:raise RuntimeError('blob mismatch '+rel)
   out[label][rel]=sha
 return out
before=guard()
a=pins['subjects']['before'];b=pins['subjects']['candidate']
changed=[p for p in a['files'] if p in b['files'] and a['files'][p]['git_blob']!=b['files'][p]['git_blob']]
added=sorted(set(b['files'])-set(a['files']))
removed=sorted(set(a['files'])-set(b['files']))
if set(changed)!={'ledgerly/paypal.py','web-demo/python/bridge.py'} or added!=['tests/test_sandbox_payment_admission.py'] or removed:raise RuntimeError('unexpected source scope')
for rel in changed:
 old=(Path(a['path'])/rel).read_text().splitlines(keepends=True)
 new=(Path(b['path'])/rel).read_text().splitlines(keepends=True)
 print(''.join(difflib.unified_diff(old,new,fromfile='before-v2/'+rel,tofile='candidate-v2/'+rel)))
probe=root/'test_payment_receiving_v1.py'
probe_sha=hashlib.sha256(probe.read_bytes()).hexdigest()
if probe_sha!='606d3ae4818854aac0b7529f291942f684fb3e9d0073f97efeee1ffbd3b638e7':raise RuntimeError('probe changed')
runs=[]
for name,opts in [('normal',[]),('optimized',['-O'])]:
 cmd=['/workspace/scratch/3dab0b9d2ce9/canvaspilot-product/test-env/bin/python','-B',*opts,str(probe),b['path'],str(root/('independent-v2-'+name+'.json'))]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
 (root/('independent-v2-'+name+'.stdout')).write_text(r.stdout)
 (root/('independent-v2-'+name+'.stderr')).write_text(r.stderr)
 runs.append({'mode':name,'command':cmd,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr.encode()).hexdigest()})
 print(json.dumps({'mode':name,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
after=guard()
if before!=after or hashlib.sha256(probe.read_bytes()).hexdigest()!=probe_sha:raise RuntimeError('post-run sources changed')
record={'base':pins['base'],'tree':pins['tree'],'owner_freeze_sha256':hashlib.sha256(raw).hexdigest(),'probe_sha256':probe_sha,'source_before':before,'source_after_equal':True,'preserved_baseline_paths':len(a['files'])-len(changed),'changed':changed,'added':added,'removed':removed,'runs':runs}
data=(json.dumps(record,indent=2)+'\n').encode()
(root/'v2-independent-controller-receipt.json').write_bytes(data)
print(json.dumps({'marker':'PAYMENT_V2_RECEIVING_COMPLETE','receipt_sha256':hashlib.sha256(data).hexdigest(),'source_counts':{k:len(v) for k,v in before.items()},'free':shutil.disk_usage(root).free}))
raise SystemExit(0 if all(r['exit_code']==0 for r in runs) else 1)
