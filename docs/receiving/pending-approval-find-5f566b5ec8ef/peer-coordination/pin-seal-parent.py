from pathlib import Path
import json,datetime
r=Path('/Users/me/ledgerly-approval-find-peer-20261009-5f566b5ec8ef')
original=(r/'seal-review.py').read_text()
new=original.replace("snapshot.mkdir()","snapshot.mkdir(exist_ok=True)").replace("'HEAD:web-demo/","'c498f55883c755553b59921199d54689d99c9730:web-demo/")
new=new.replace("'diff','--unified=12','--'","'diff','c498f55883c755553b59921199d54689d99c9730','--unified=12','--'")
new=new.replace("'ownerTestSourcesRead':False","'custodyPhase': 'Original seal stopped at inverse comparison because owner committed unchanged source82e89 while HEAD was used; no behavior rerun. Corrected seal pins canonical c498 explicitly.',\n 'ownerTestSourcesRead':False")
assert new!=original
(r/'seal-review-pinned.py').write_text(new)
(r/'seal-first-custody-diagnostic.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original':'seal-review.py','observed':'AssertionError at inverse.encode()==original','cause':'Owner committed82e89 while seal used moving HEAD; exact runtime pins unchanged.','correction':'Pin all inverse comparisons and diff to c498 canonical input.','behaviorRepeated':False},indent=2)+'\n')
