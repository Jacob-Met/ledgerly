from pathlib import Path
import hashlib,json,subprocess,datetime
r=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');s=r/'source';e=r/'evidence';base='c498f55883c755553b59921199d54689d99c9730'
paths=['web-demo/README.md','web-demo/index.html','web-demo/src/main.ts','web-demo/tests/engine-recovery.test.ts','web-demo/APPROVAL-FINDER.md','web-demo/src/approval-filter.css','web-demo/src/approval-filter.ts','web-demo/tests/approval-filter-browser.py','web-demo/tests/approval-filter.test.ts']
def git(*a):return subprocess.run(['git',*a],cwd=s,capture_output=True,check=True).stdout
original={}
for item in git('ls-tree','-r','-z',base).split(b'\0'):
 if not item:continue
 meta,path=item.split(b'\t');mode,kind,blob=meta.decode().split();original[path.decode()]={'mode':mode,'blob':blob}
for p,v in original.items():
 if p in paths:continue
 assert git('hash-object','--no-filters',p).decode().strip()==v['blob'],p
 mode='120000' if (s/p).is_symlink() else ('100755' if (s/p).stat().st_mode&0o111 else '100644')
 assert mode==v['mode'],p
before=git('show',base+':web-demo/src/main.ts').decode();after=(s/'web-demo/src/main.ts').read_text()
for line in [
"import './approval-filter.css';\n",
"import {createApprovalFilters} from './approval-filter';\n",
"const approvalFilters=createApprovalFilters({list:$<HTMLElement>('#approval-list'),query:$<HTMLInputElement>('#approval-search'),kind:$<HTMLSelectElement>('#approval-kind'),clear:$<HTMLButtonElement>('#approval-filter-clear'),note:$<HTMLElement>('#approval-filter-note'),empty:$<HTMLElement>('#approval-filter-empty')});\n",
" approvalFilters.setAvailability(ready,busy);\n",
" approvalFilters.update(queue);\n",
"  if(restarting&&Array.isArray(reply.state?.pending)&&reply.state.pending.length===0&&Array.isArray(reply.state?.ledger)&&reply.state.ledger.length===0)approvalFilters.clear();\n"]:
 assert after.count(line)==1;after=after.replace(line,'')
assert after.count("if(reply?.ok){approvalFilters.clear();$<HTMLTextAreaElement>('#job-email')")==1
after=after.replace("if(reply?.ok){approvalFilters.clear();$<HTMLTextAreaElement>('#job-email')","if(reply?.ok){$<HTMLTextAreaElement>('#job-email')")
assert after==before
text=(s/'web-demo/index.html').read_text();start=text.index('<section class="approval-filters"');end=text.index('</section>',start)+len('</section>')
assert text[:start]+text[end:]==git('show',base+':web-demo/index.html').decode()
text=(s/'web-demo/tests/engine-recovery.test.ts').read_text().replace("import {createApprovalFilters} from '../src/approval-filter';\n",'').replace("createRejectionReasons, createApprovalFilters,","createRejectionReasons,")
assert text==git('show',base+':web-demo/tests/engine-recovery.test.ts').decode()
assert (s/'web-demo/README.md').read_bytes().startswith(git('show',base+':web-demo/README.md'))
freeze={'base':base,'ownedPaths':{p:{'sha256':hashlib.sha256((s/p).read_bytes()).hexdigest(),'bytes':(s/p).stat().st_size,'blob':git('hash-object','--no-filters',p).decode().strip()} for p in paths},'preservation':{'unchangedOriginalLeaves':len(original)-4,'originalLeaves':len(original),'mainInverseExact':True,'indexInverseExact':True,'recoveryTestInverseExact':True,'READMEOriginalPrefixExact':True},'qualification':{'focused':'candidate-focused-first.json','focusedPassed':24,'newCases':12,'build':'candidate-build-first.json','buildExit':0,'browser':'browser-candidate-first/receipt.json','actualBrowserPassed':13,'pageErrors':0,'offOriginRequests':0,'baseline':'browser-baseline/receipt.json'},'visual':{'personallyViewed':['browser-candidate-first/desktop-reminder.png','browser-candidate-first/phone-reminder.png'],'assessment':'Search/type/clear and count fit desktop and390px; retained reminder text and original action buttons remain legible. No layout repair.'},'actions':'No source publication, Actions run or native DB append','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(e/'source-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
(e/'product.diff').write_bytes(git('diff','--',*paths))
git('add','--',*paths)
p=subprocess.run(['git','commit','-m','Add literal pending approval search and action filters'],cwd=s,capture_output=True,text=True)
print(json.dumps({'commitExit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}),flush=True)
assert p.returncode==0
freeze['head']=git('rev-parse','HEAD').decode().strip();freeze['tree']=git('rev-parse','HEAD^{tree}').decode().strip()
assert not git('status','--porcelain')
(e/'source-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
print(json.dumps(freeze),flush=True)
