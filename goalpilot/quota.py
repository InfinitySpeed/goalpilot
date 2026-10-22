"""Read reported account windows without model inference or exposing identity fields."""
import tempfile
import time
from pathlib import Path
from .rpc import AppServerAdapter,ProtocolError


def snapshot(timeout=8):
    observed={'observed_at':time.time(),'model_calls':0,'available':False,'buckets':{}}
    try:
        with tempfile.TemporaryDirectory(prefix='goalpilot-quota-')as temp:
            root=Path(temp)
            with AppServerAdapter()as client:
                deadline=time.monotonic()+timeout
                client._start(root,True,root,deadline)
                reply=client._request('account/rateLimits/read',{'excludeResetCreditDetails':True},deadline)
                buckets=reply.get('rateLimitsByLimitId')or{'codex':reply.get('rateLimits',{})}
                for key,value in buckets.items():
                    selected={}
                    for name in ('primary','secondary'):
                        window=value.get(name)
                        if isinstance(window,dict)and type(window.get('usedPercent'))is int:
                            selected[name]={k:window.get(k)for k in ('usedPercent','resetsAt','windowDurationMins')}
                    if selected:observed['buckets'][key]=selected
                observed['available']=bool(observed['buckets'])
    except (OSError,ValueError,TimeoutError,ProtocolError)as exc:
        observed['error']=type(exc).__name__
    return observed


def compare(before,after):
    windows=[]
    for bucket,values in before.get('buckets',{}).items():
        for name,old in values.items():
            new=after.get('buckets',{}).get(bucket,{}).get(name)
            if not new:continue
            same=old.get('resetsAt')==new.get('resetsAt')and old.get('windowDurationMins')==new.get('windowDurationMins')
            delta=new['usedPercent']-old['usedPercent']if same else None
            windows.append({'bucket':bucket,'window':name,'before':old,'after':new,
                            'same_window':same,'reported_percentage_point_delta':delta,
                            'usable_monotonic_observation':same and delta is not None and delta>=0})
    return {'windows':windows,'exact_attributable_quota_known':False,
            'limitations':'Integer account-wide percentages; unknown rounding and reporting delay, possible concurrent activity. A zero displayed change does not mean zero quota consumed. Window resets cannot be compared. No exact token-to-quota conversion.'}
