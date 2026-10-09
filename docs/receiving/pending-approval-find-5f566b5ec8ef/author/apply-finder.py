from pathlib import Path
import hashlib,json,subprocess
root=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef')
src=root/'source'
phase=root/'evidence'/'implementation-first'
phase.mkdir(exist_ok=True)
paths=['web-demo/src/main.ts','web-demo/index.html','web-demo/tests/engine-recovery.test.ts']
for p in paths:
 b=(src/p).read_bytes()
 target=phase/(Path(p).name+'.before')
 assert not target.exists()
 target.write_bytes(b)
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a))
 return s.replace(a,b)
p=src/paths[0];s=p.read_text()
s=replace(s,"import './approval-preview.css';","import './approval-preview.css';\nimport './approval-filter.css';\nimport {createApprovalFilters} from './approval-filter';")
s=replace(s,"const rejectionReasons=createRejectionReasons($<HTMLElement>('#approval-list'));","const rejectionReasons=createRejectionReasons($<HTMLElement>('#approval-list'));\nconst approvalFilters=createApprovalFilters({list:$<HTMLElement>('#approval-list'),query:$<HTMLInputElement>('#approval-search'),kind:$<HTMLSelectElement>('#approval-kind'),clear:$<HTMLButtonElement>('#approval-filter-clear'),note:$<HTMLElement>('#approval-filter-note'),empty:$<HTMLElement>('#approval-filter-empty')});")
s=replace(s," rejectionReasons.setAvailability(ready,busy);"," rejectionReasons.setAvailability(ready,busy);\n approvalFilters.setAvailability(ready,busy);")
s=replace(s," rejectionReasons.afterRender(queue.map((action:any)=>action.id));"," rejectionReasons.afterRender(queue.map((action:any)=>action.id));\n approvalFilters.update(queue);")
s=replace(s,"  needsFreshSandbox=false;setControls(true);b.textContent='Python engine loaded';","  if(restarting&&Array.isArray(reply.state?.pending)&&reply.state.pending.length===0&&Array.isArray(reply.state?.ledger)&&reply.state.ledger.length===0)approvalFilters.clear();\n  needsFreshSandbox=false;setControls(true);b.textContent='Python engine loaded';")
s=replace(s,"if(reply?.ok){$<HTMLTextAreaElement>('#job-email').value='';invalidateAnalysis('Sandbox reset.","if(reply?.ok){approvalFilters.clear();$<HTMLTextAreaElement>('#job-email').value='';invalidateAnalysis('Sandbox reset.")
p.write_text(s)
p=src/paths[1];s=p.read_text()
controls='''<section class="approval-filters" aria-label="Find pending approvals"><label class="approval-filter-query" for="approval-search">FIND IN QUEUED PROPOSALS<input id="approval-search" type="search" placeholder="Recipient, invoice ID, item or message" autocomplete="off" aria-describedby="approval-filter-note" disabled></label><label for="approval-kind">ACTION TYPE<select id="approval-kind" disabled><option value="all">All pending</option><option value="send_invoice">Invoice sends</option><option value="send_reminder">Reminders</option></select></label><button id="approval-filter-clear" type="button" class="button button-secondary" disabled>Clear filters</button><p id="approval-filter-note" role="status" aria-live="polite">Load the local engine to find pending approvals.</p><p id="approval-filter-empty" class="approval-filter-empty" hidden>No pending approvals match these filters. Clear the filters to see the full queue.</p></section>'''
s=replace(s,'<div id="approval-list" class="approval-list">',controls+'<div id="approval-list" class="approval-list">');p.write_text(s)
p=src/paths[2];s=p.read_text()
s=replace(s,"import {createRejectionReasons} from '../src/rejection-reason';","import {createRejectionReasons} from '../src/rejection-reason';\nimport {createApprovalFilters} from '../src/approval-filter';")
s=replace(s,"createReceivablesView, createRejectionReasons,","createReceivablesView, createRejectionReasons, createApprovalFilters,")
p.write_text(s)
out=subprocess.run(['git','diff','--',*paths],cwd=src,capture_output=True,text=True)
(phase/'integration.diff').write_text(out.stdout)
receipt={'paths':{p:{'before':hashlib.sha256((phase/(Path(p).name+'.before')).read_bytes()).hexdigest(),'after':hashlib.sha256((src/p).read_bytes()).hexdigest()} for p in paths},'compatibility':'Recovery VM import/binding only; every original assertion is unchanged.'}
(phase/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
