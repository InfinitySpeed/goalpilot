"""Execute only remaining preregistered cells under the prospective bound supplement."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from efficiency_campaign import hashes,write


def run(output):
    m=json.loads((output/'protocol.json').read_text());assert m==json.loads((output/'preregistered-protocol.json').read_text())
    supplement=json.loads((output/'supplementary-bounds-preregistered.json').read_text())
    assert (output/'stopped.json').exists()
    path=output/'supplement-execution.json'
    if not path.exists():write(path,{'started_at':time.time(),'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'primary_study_remains_stopped':True,'remaining_order':[i for i in m['order']if not(output/'trials'/i['id']/'record.json').exists()]})
    assert json.loads(path.read_text())['controller_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for item in m['order']:
        records=[json.loads(p.read_text())for p in (output/'trials').glob('*/record.json')]
        if any(r['fatal']for r in records)or any(r['mode']=='candidate'and not r['usage']['usage_complete']for r in records)or sum(r['usage']['total_tokens']for r in records)>=m['observed_campaign_token_cap']:return
        for case in m['cases']:
            pair={r['mode']:r for r in records if r['case']==case}
            if len(pair)==2 and (pair['baseline']['success']and not pair['candidate']['success']or pair['baseline']['artifact_success']and not pair['candidate']['artifact_success']):return
        if any(r['id']==item['id']for r in records):continue
        trial=output/'trials'/item['id'];assert not trial.exists(),'Uncommitted partial trial must never be blindly rerun'
        assert supplement['registered_at']<time.time()
        source=output/'source_snapshot'/item['mode'];assert hashes(source)==m['source_fingerprints'][item['mode']]
        subprocess.run([sys.executable,str(source/'worker.py'),'worker',str(output),item['id'],str(source)],check=True,cwd=source)


if __name__=='__main__':run(Path(sys.argv[1]).resolve())
