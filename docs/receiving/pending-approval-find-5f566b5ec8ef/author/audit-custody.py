from pathlib import Path
import hashlib,json,subprocess
r=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');s=r/'source';e=r/'evidence'
p=e/'product.diff';p.rename(e/'product-tracked-first.diff')
p.write_bytes(subprocess.run(['git','diff','c498f55883c755553b59921199d54689d99c9730','HEAD','--'],cwd=s,capture_output=True,check=True).stdout)
paths=sorted((s/'.github/workflows').glob('*'))
receipt={'currentMain':'c498f55883c755553b59921199d54689d99c9730','completeWorkflowFiles':[{'path':str(p.relative_to(s)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':p.read_text()} for p in paths],'events':'All four workflows push main, pull_request (some path filters); Pages additionally workflow_dispatch. No issue event. Non-main source push eligibility must be rechecked by final receiver at publication. No write authorized by this receipt.','policy':'No new Actions including implicit triggers; current hamon comment6067592767 unchanged.'}
(e/'workflow-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'productDiff':hashlib.sha256(p.read_bytes()).hexdigest(),'workflowFiles':len(paths),'currentMainUnchanged':True}))
