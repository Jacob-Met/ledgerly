import pathlib,sys,json,hashlib,os,subprocess
runner=sys.argv[1];previous=sys.argv[2]
base=pathlib.Path('/dev/shm/memory-delivery-ledgerly-3dab');evidence=base/'publication-composition';path=evidence/'run_native_composition.py'
incident=None
if path.exists():
 raw=path.read_bytes()
 if not previous.encode().startswith(raw):raise RuntimeError('Unexpected partial runner contents')
 incident={'operation':'write unexecuted composition controller','error':'ENOSPC','partial_path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'verified_prefix_of_unexecuted_source':True,'action':'removed only this incomplete unexecuted owner file; final exact runner and receipts held in process memory'}
 path.unlink()
bootstrap="import sys; code, filename, source, manifest=sys.argv[1:]; sys.argv=[filename,source,manifest]; exec(compile(code,filename,'exec'), {'__name__':'__main__','__file__':filename,'RUNNER_SOURCE':code})"
py='/workspace/scratch/3dab0b9d2ce9/canvaspilot-product/test-env/bin/python'
runs=[]
for mode in ('normal','optimized'):
 argv=[py,'-B']+(['-O'] if mode=='optimized' else [])+['-c',bootstrap,runner,str(path),str(base/'candidate-pr33'),str(evidence/'source-freeze-pr33.json')]
 result=subprocess.run(argv,capture_output=True,text=True,cwd=base/'candidate-pr33',env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','LEDGERLY_ALLOW_NETWORK':'0'})
 parsed=None
 try:parsed=json.loads(result.stdout)
 except json.JSONDecodeError:pass
 runs.append({'mode':mode,'exit_code':result.returncode,'execution':'exact UTF-8 runner source compiled in memory; bootstrap sets __file__ and RUNNER_SOURCE; no test source changes','executable':py,'flags':['-B']+(['-O'] if mode=='optimized' else []),'source':str(base/'candidate-pr33'),'manifest':str(evidence/'source-freeze-pr33.json'),'runner_sha256':hashlib.sha256(runner.encode()).hexdigest(),'stdout':result.stdout,'stderr':result.stderr,'receipt':parsed})
print(json.dumps({'incident':incident,'runs':runs}))
raise SystemExit(0 if all(x['exit_code']==0 for x in runs) else 1)
