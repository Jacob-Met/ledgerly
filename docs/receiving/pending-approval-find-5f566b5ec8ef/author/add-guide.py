from pathlib import Path
import json,hashlib,subprocess
r=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');s=r/'source'
p=s/'web-demo/README.md';before=p.read_bytes()
assert b'APPROVAL-FINDER.md' not in before
(r/'evidence/implementation-first/README.md.before').write_bytes(before)
p.write_bytes(before+b'\n\n## Find pending approvals\n\nUse the human gate\'s literal search and action-type filter to locate an original pending invoice or reminder without changing the queue. [Usage and qualification](APPROVAL-FINDER.md).\n')
print(json.dumps({'mainImportConsumers':[str(p.relative_to(s)) for p in (s/'web-demo/tests').glob('*') if p.is_file() and ('main.ts' in p.read_text(errors='replace'))]},indent=2))
print(subprocess.run(['git','status','--short'],cwd=s,capture_output=True,text=True).stdout)
