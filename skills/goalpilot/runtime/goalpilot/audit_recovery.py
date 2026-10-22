"""Recover complete JSON values from interrupted audit delivery, never invent tests."""
import json
from pathlib import Path


def streamed_json(log_dir):
    path=Path(log_dir)/'events.jsonl'
    if not path.exists()or path.stat().st_size>32000000:return ''
    fragments={}
    for line in path.read_text().splitlines():
        try:event=json.loads(line)['packet']
        except(ValueError,KeyError,TypeError):continue
        if event.get('method')=='item/agentMessage/delta':
            p=event.get('params',{});fragments.setdefault(p.get('itemId',''),[]).append(p.get('delta',''))
    messages=[''.join(parts).strip()for parts in fragments.values()]
    messages=[s[7:].lstrip()if s.startswith('```json')else s for s in messages]
    return max((s for s in messages if s.startswith('{')),key=len,default='')


def prefix_fields(text):
    """Decode only whole top-level values and whole requirement objects.

    A truncated string/object is never made executable. This output is an
    unfinished checkpoint; a subsequent completed review must confirm coverage.
    """
    text=text.strip();decoder=json.JSONDecoder();values={};pos=0
    def space(i):
        while i<len(text)and text[i].isspace():i+=1
        return i
    if not text.startswith('{'):return values
    pos=1
    try:
        while True:
            pos=space(pos)
            if pos>=len(text)or text[pos]=='}':return values
            key,pos=decoder.raw_decode(text,pos);pos=space(pos)
            if key not in('assumptions','blockers','limitations','requirements')or key in values or pos>=len(text)or text[pos]!=':':return {}
            pos=space(pos+1)
            if key=='requirements':
                if pos>=len(text)or text[pos]!='[':return {}
                pos+=1;items=[];values[key]=items
                while True:
                    pos=space(pos)
                    if pos>=len(text):return values
                    if text[pos]==']':pos+=1;break
                    item,end=decoder.raw_decode(text,pos)
                    if not isinstance(item,dict)or len(items)>=8:return {}
                    items.append(item);pos=space(end)
                    if pos>=len(text):return values
                    if text[pos]==',':pos+=1;continue
                    if text[pos]==']':pos+=1;break
                    return {}
            else:
                value,pos=decoder.raw_decode(text,pos)
                if not isinstance(value,list)or any(not isinstance(v,str)for v in value):return {}
                values[key]=value
            pos=space(pos)
            if pos>=len(text)or text[pos]=='}':return values
            if text[pos]!=',':return {}
            pos+=1
    except(json.JSONDecodeError,TypeError):return values


def combine(prefix,delivery):
    result={k:list(dict.fromkeys(prefix.get(k,[])+delivery.get(k,[])))for k in('assumptions','blockers','limitations')}
    requirements=[];ids=set()
    for item in prefix.get('requirements',[])+delivery.get('requirements',[]):
        if item in requirements:continue
        item=dict(item);name=item.get('id')
        while name in ids:name='recovered-'+name
        item['id']=name;ids.add(name);requirements.append(item)
    result['requirements']=requirements
    result['limitations'].append('Review delivery recovered after an interruption; original completed probes retained. Token accounting may remain partial.')
    return result
