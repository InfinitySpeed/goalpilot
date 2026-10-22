"""Stop at a whole-trial boundary after an irreversible primary-criterion loss."""
import fcntl,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json

def stop(output,pid):
    output=Path(output).resolve()
    atomic_json(output/'futility-stop-request.json',{'requested_at_epoch':time.time(),'reason':'First complete pair: direct success, GoalPilot artifact correct but mission incomplete after independent review timeout. Primary zero-paired-regressions criterion is now impossible. Stop after the already-active trial; do not waste further Codex quota on a version that cannot meet its registered primary criterion.','protocol_deviation':'This early futility rule was not preregistered. Original protocol, all original trial outcomes and incomplete planned denominator retained. No positive primary claim is allowed. No active model turn is interrupted by this stop.','runner_pid':pid})
    with(output/'campaign.lock').open('a+')as fd:
        fcntl.flock(fd,fcntl.LOCK_EX)
        records=list((output/'trials').glob('*/record.json'))
        atomic_json(output/'futility-stop.json',{'stopped_at_epoch':time.time(),'completed_trials':len(records),'planned_trials':12,'reason':'Registered no-regression condition already violated; stopped at trial boundary to repair generic closure bug. Original campaign remains an incomplete failed study.','registered_product_sources_untouched':True})
        print(json.dumps({'stopped_at_boundary':True,'completed':len(records)}),flush=True)
        # The registered runner uses a nonblocking lock; its next trial cannot start.
        until=time.monotonic()+60
        while time.monotonic()<until:
            try:os.kill(pid,0)
            except ProcessLookupError:return
            time.sleep(.2)

if __name__=='__main__':stop(sys.argv[1],int(sys.argv[2]))
