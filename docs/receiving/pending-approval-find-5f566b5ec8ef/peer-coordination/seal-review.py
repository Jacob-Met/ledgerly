from pathlib import Path
import json,hashlib,subprocess,datetime,re
r=Path('/Users/me/ledgerly-approval-find-peer-20261009-5f566b5ec8ef')
s=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef/source')
sha=lambda b:hashlib.sha256(b).hexdigest()
first=json.loads((r/'controller-first/receipt.json').read_text());fixed=json.loads((r/'controller-literal-fixed/receipt.json').read_text())
assert first['result']['passed']==6 and first['result']['total']==7 and fixed['result']['passed']==fixed['result']['total']==1
assert first['unchanged'] and fixed['unchanged'] and first['contextClosed'] and fixed['contextClosed']
assert json.loads((r/'controller-process.json').read_text())['exit']==1
assert json.loads((r/'controller-literal-fixed-process.json').read_text())['exit']==0
pins=json.loads((s.parent/'evidence/candidate-source-first.json').read_text())
for p,h in pins.items():assert sha((s/p).read_bytes())==h,(p,h)
paths=['web-demo/src/approval-filter.ts','web-demo/src/approval-filter.css','web-demo/src/main.ts','web-demo/index.html','web-demo/src/approval-preview.ts','web-demo/APPROVAL-FINDER.md']
snapshot=r/'reviewed-source';snapshot.mkdir()
for p in paths:
 dst=snapshot/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((s/p).read_bytes())
main=(s/'web-demo/src/main.ts').read_text()
lines=main.splitlines(keepends=True)
removed=[x for x in lines if x.startswith("import './approval-filter.css'") or x.startswith("import {createApprovalFilters}") or x.startswith("const approvalFilters=") or x.strip() in ('approvalFilters.setAvailability(ready,busy);','approvalFilters.update(queue);') or x.strip().startswith('if(restarting&&Array.isArray(reply.state?.pending)')]
assert len(removed)==6
inverse=''.join(x for x in lines if x not in removed)
assert inverse.count('if(reply?.ok){approvalFilters.clear();')==1
inverse=inverse.replace('if(reply?.ok){approvalFilters.clear();','if(reply?.ok){')
original=subprocess.check_output(['/usr/bin/git','-C',str(s),'show','HEAD:web-demo/src/main.ts'])
assert inverse.encode()==original
html=(s/'web-demo/index.html').read_text()
inverseHTML,n=re.subn(r'<section class="approval-filters".*?</section>(?=<div id="approval-list")','',html,count=1)
assert n==1
assert inverseHTML.encode()==subprocess.check_output(['/usr/bin/git','-C',str(s),'show','HEAD:web-demo/index.html'])
assert (s/'web-demo/src/approval-preview.ts').read_bytes()==subprocess.check_output(['/usr/bin/git','-C',str(s),'show','HEAD:web-demo/src/approval-preview.ts'])
diff=subprocess.check_output(['/usr/bin/git','-C',str(s),'diff','--unified=12','--','web-demo/src/main.ts','web-demo/index.html'])
(r/'reviewed-hook-delta.diff').write_bytes(diff)
ps=subprocess.check_output(['ps','-axo','pid=,command='],text=True)
remaining=[x for x in ps.splitlines() if 'Google Chrome' in x and str(r) in x]
assert not remaining
review={
 'schema':'hamon.independent-review.v1','actor':'chatgpt:5f566b5ec8ef:coordination','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'accepted within bounded source and real DOM controller receiving',
 'contractSHA256':'c90c7ab389510a1b1d80425dad766b57a6e77c5c8437473658f39655336084e6',
 'blindFreeze':{'path':'blind-expectations.json','sha256':sha((r/'blind-expectations.json').read_bytes()),'beforeProductAndOwnerTests':True,'cases':12},
 'source':{p:sha((s/p).read_bytes()) for p in paths},
 'sourceFindings':[
  'Exact ordered IDs and both unique action buttons are revalidated on each paint; invalid association reveals current cards and disables filter inputs without discarding view values.',
  'Identity metadata is copied. Filtering reads current original proposal text and changes only hidden attributes; action handlers and renderer remain original.',
  'Persistent controls are outside replacement list. Availability hooks retain values. Reset and restart clear only inside their existing successful reply branches, with restart additionally requiring empty pending and ledger arrays.',
  'Guide explicitly documents trimmed query boundaries, literal lowercased matching, collapsed original text, omitted rejection-note text, and no-match versus empty semantics.',
  'Inverse removes only six added hook/import lines plus reset clear and reproduces entire current canonical main.ts; removing only the isolated HTML section reproduces original index. Complete original renderer remains exact.'
 ],
 'nativePhases':[
  {'receipt':'controller-first/receipt.json','sha256':sha((r/'controller-first/receipt.json').read_bytes()),'processExit':1,'passedGroups':6,'totalGroups':7,'failure':'Receiver-only whole-document script selector counted the two injected module scripts; literal group stopped before its remaining assertions. No product finding.'},
  {'receipt':'controller-literal-fixed/receipt.json','sha256':sha((r/'controller-literal-fixed/receipt.json').read_bytes()),'processExit':0,'passedGroups':1,'totalGroups':1,'change':'Only execute affected literal group and scope markup assertion to rendered list. No product change or six-group replay.'}
 ],
 'nativeOutcome':'Seven distinct groups accepted across retained phases; not a single whole-current 7/7 process.',
 'runtime':{'Chrome':first['browser'],'method':'Existing Python Playwright private headless persistent contexts; TypeScript transpileModule produces exact-source browser modules. Launch uses installed library defaults; no normal-sandbox assertion.','requests':[],'pageErrors':[],'filterEffects':[],'contextsClosed':True,'remainingOwnedChromeProcesses':remaining},
 'limits':['No personal execution of author full app/real Python engine or approve/reject provider workflow. The explicit delegate witness is a local original-ID observer, not an Agent action.','No author suite, SDK, installation, Pages, source publication, CI or hosted gate replay.','Failed reset/restart success ordering is source reviewed here; actual engine fault controls belong to the author receiver.','No root personal review or execution attribution.'],
 'ownerTestSourcesRead':False
}
(r/'independent-review.json').write_text(json.dumps(review,indent=2)+'\n')
selected=[]
for p in sorted(r.rglob('*')):
 if not p.is_file() or any(x=='profile' for x in p.parts) or p.name in ('manifest.json',):continue
 selected.append({'path':str(p.relative_to(r)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
(r/'manifest.json').write_text(json.dumps({'files':selected},indent=2)+'\n')
print(json.dumps({'reviewSHA256':sha((r/'independent-review.json').read_bytes()),'manifestSHA256':sha((r/'manifest.json').read_bytes()),'files':len(selected),'bytes':sum(x['bytes'] for x in selected),'sourcePins':review['source'],'remainingOwnedChrome':remaining}))
