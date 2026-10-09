from pathlib import Path
import os,json,subprocess,datetime,hashlib
r=Path('/Users/me/ledgerly-approval-find-20261009-5f566b5ec8ef');s=r/'source';e=r/'evidence'
env=os.environ.copy();env['PATH']='/opt/homebrew/bin:'+env.get('PATH','');env['PYTHON']='/Users/me/.pyenv/versions/3.13.7/bin/python3'
runs=[]
for name,cmd in [('focused',['/opt/homebrew/bin/node','node_modules/vitest/vitest.mjs','run','tests/approval-filter.test.ts','tests/engine-recovery.test.ts','tests/approval-preview.test.ts']),('build',['/opt/homebrew/bin/npm','run','build'])]:
 p=subprocess.run(cmd,cwd=s/'web-demo',env=env,capture_output=True,text=True)
 rec={'name':name,'command':cmd,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 print(json.dumps({'name':name,'exit':p.returncode,'stdoutTail':p.stdout[-3000:],'stderrTail':p.stderr[-1500:]}),flush=True)
 (e/('candidate-'+name+'-first.json')).write_text(json.dumps(rec,indent=2)+'\n');runs.append(rec)
 if p.returncode:break
pins={str(p.relative_to(s)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [s/'web-demo/src/approval-filter.ts',s/'web-demo/src/approval-filter.css',s/'web-demo/src/main.ts',s/'web-demo/index.html',s/'web-demo/tests/approval-filter.test.ts',s/'web-demo/tests/engine-recovery.test.ts']}
(e/'candidate-source-first.json').write_text(json.dumps(pins,indent=2)+'\n');print(json.dumps({'pins':pins}),flush=True)
