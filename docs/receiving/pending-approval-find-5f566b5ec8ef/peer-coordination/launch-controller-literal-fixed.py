from pathlib import Path
import subprocess,json,hashlib,time,datetime
r=Path("/Users/me/ledgerly-approval-find-peer-20261009-5f566b5ec8ef");out=r/'controller-literal-fixed-process.json';assert not out.exists()
cmd=['/Users/me/.pyenv/versions/3.13.7/bin/python3','-B',str(r/'run-controller-literal-fixed.py')]
start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
(r/'controller-literal-fixed-process.stdout').write_text(p.stdout);(r/'controller-literal-fixed-process.stderr').write_text(p.stderr)
receipt={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'exit':p.returncode,'seconds':time.monotonic()-start,'stdoutSHA256':hashlib.sha256(p.stdout.encode()).hexdigest(),'stderrSHA256':hashlib.sha256(p.stderr.encode()).hexdigest()}
out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
