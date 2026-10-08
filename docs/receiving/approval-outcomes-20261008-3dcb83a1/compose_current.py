"""Qualify only the concrete intervening PR13/approval composition."""
import ast,hashlib,json,os,pathlib,shutil,subprocess
from datetime import datetime,timezone
root=pathlib.Path(__file__).resolve().parent
input=json.loads((root/'current-input.json').read_text())
assert shutil.disk_usage(root).free>=512*1024*1024
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def sha(b):return hashlib.sha256(b).hexdigest()
def approve(s):
    start=s.index('    def approve(')
    return s[start:s.index('    def reject(',start)]
for row in input['source']:
    assert blob(row['content'].encode())==row['sha'],row['path']
before=(root/'baseline/ledgerly/agent.py').read_text()
frozen=(root/'source/ledgerly/agent.py').read_text()
current=next(row['content'] for row in input['source'] if row['path']=='ledgerly/agent.py')
assert approve(current)==approve(before)
composed=current.replace(approve(before),approve(frozen),1)
assert composed.replace(approve(frozen),approve(before),1)==current
dest=root/'current-composed'
shutil.copytree(root/'source',dest)
(dest/'ledgerly/agent.py').write_text(composed)
for row in input['source']:
    if row['path']!='ledgerly/agent.py':
        p=dest/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(row['content'])
cmd=['/usr/bin/python3','-B','-m','pytest','-q','-p','no:cacheprovider','tests/test_approval_outcomes.py','tests/test_due_date_receiving.py']
result=subprocess.run(cmd,cwd=dest,env={**os.environ,'LEDGERLY_ALLOW_NETWORK':'0','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=45)
receipt={'at':datetime.now(timezone.utc).isoformat(),'reason':'Main integrated PR13 after frozen original-base receiving; check its actual date rules compose with ordinary approval failure handling.',
 'current_commit':input['current_commit'],'current_tree':input['current_tree'],
 'original_approval_method_equals_current':True,'composition':'Replace only Agent.approve in current main with independently received frozen candidate method.',
 'all_other_current_agent_bytes_preserved':True,'current_inputs':[{'path':r['path'],'git_blob':r['sha'],'sha256':sha(r['content'].encode())} for r in input['source']],
 'frozen_agent_sha256':sha(frozen.encode()),'composed_agent_git_blob':blob(composed.encode()),'composed_agent_sha256':sha(composed.encode()),
 'command':cmd,'cwd':str(dest),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
 'script_sha256':sha(pathlib.Path(__file__).read_bytes()),
 'scope':'Only current due-date and approval controls; original full-suite and independent bridge receipts stay pinned to1871942.',
 'free_bytes_after':shutil.disk_usage(root).free}
(root/'current-composition.json').write_text(json.dumps(receipt,indent=2)+'\n')
assert result.returncode==0,receipt
assert (root/'source/ledgerly/agent.py').read_text()==frozen
assert (root/'baseline/ledgerly/agent.py').read_text()==before
print(json.dumps(receipt))
