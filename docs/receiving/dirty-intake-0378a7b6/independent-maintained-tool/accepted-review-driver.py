import difflib,hashlib,json,pathlib,subprocess,time
root=pathlib.Path(r'C:\Users\minec\hamon-0378a7b6-ledgerly-discovery');out=pathlib.Path(__file__).parent/'maintained-harness-review-v2';out.mkdir(exist_ok=False)
rel='web-demo/tools/check_intake_file_browser.mjs';p=root/rel;raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest();assert pin=='abda8db353383e970a68ca678470a5c9dd850734d8f4282b6580946319cb60b1'
prior=subprocess.check_output(['git','-C',str(root),'show','HEAD:'+rel]).decode().splitlines();now=raw.decode().splitlines()
ops=[(tag,a,b,c,d) for tag,a,b,c,d in difflib.SequenceMatcher(a=prior,b=now,autojunk=False).get_opcodes() if tag!='equal'];assert len(ops)==2,ops
assert ops[0][0]=='insert' and ops[0][2]==ops[0][1] and ops[0][4]-ops[0][3]==11,ops
assert ops[1][0]=='replace' and ops[1][2]-ops[1][1]==1 and ops[1][4]-ops[1][3]==1,ops
assert prior[ops[1][1]].strip()=="const trusted=await evaluate('__intakeProbe.events');"
assert now[ops[1][3]].strip()=="const trusted=[...priorTrusted,...await evaluate('__intakeProbe.events')];"
keyboard=[l for l in prior if 'trusted.some' in l];assert len(keyboard)>=4 and all(l in now for l in keyboard)
assert 'returnByValue:true' in '\n'.join(now) and 'if(e.isTrusted)p.events.push' in '\n'.join(now)
diff='\n'.join(difflib.unified_diff(prior,now,fromfile='current-main-maintained',tofile='candidate-maintained'))+'\n';(out/'reviewed.diff').write_text(diff)
receipt={'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'reviewer':'chatgpt-0378a7b6b7c2/mac_product','source_sha256':pin,'base':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip(),'edit_opcodes':ops,'original_keyboard_predicates_unchanged':keyboard,'only_added_setup_and_trusted_event_snapshot':True,'exact_runtime_receiving_stays_separate':True,'source_unchanged':hashlib.sha256(p.read_bytes()).hexdigest()==pin,'scope':'Narrow source acceptance only; no claim that reviewer ran maintained 408 assertions.'};assert receipt['source_unchanged'];(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))