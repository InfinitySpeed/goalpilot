"""Before implementation only: independently review calculated test expectations."""
import ast

SCHEMA={'type':'object','additionalProperties':False,'properties':{
 'patches':{'type':'array','maxItems':8,'items':{'type':'object','additionalProperties':False,
  'properties':{k:{'type':'string'}for k in ('id','old','new','reason','source')},
  'required':['id','old','new','reason','source']}},
 'limitations':{'type':'array','items':{'type':'string'}}},'required':['patches','limitations']}


def _numeric_expectations_only(old,new,allowed=False,inside_assert=False):
    if isinstance(old,ast.Constant)and isinstance(new,ast.Constant)and old.value!=new.value:
        return allowed and type(old.value)is int and type(new.value)is int and old.value>=0 and new.value>=0
    if type(old)is not type(new):return False
    if isinstance(old,ast.AST):
        inside=inside_assert or isinstance(old,ast.Assert)
        return all(_numeric_expectations_only(getattr(old,k),getattr(new,k),
            inside and isinstance(old,ast.Compare)and all(isinstance(op,ast.Eq)for op in old.ops)and k=='comparators',inside)for k in old._fields)
    if isinstance(old,list):
        return len(old)==len(new)and all(_numeric_expectations_only(a,b,allowed,inside_assert)for a,b in zip(old,new))
    return old==new


def apply_validation(audit,review):
    if not isinstance(review,dict)or not isinstance(review.get('patches'),list)or len(review['patches'])>8:
        raise ValueError('Invalid independent arithmetic review')
    limits=review.get('limitations')
    if not isinstance(limits,list)or any(not isinstance(s,str)for s in limits):raise ValueError('Invalid review limits')
    items={r['id']:dict(r)for r in audit['requirements']}
    for patch in review['patches']:
        if not isinstance(patch,dict)or any(not isinstance(patch.get(k),str)or not patch[k].strip()for k in ('id','old','new','reason','source')):
            raise ValueError('Arithmetic correction needs exact text, ID and original-contract justification')
        if patch['id']not in items:raise ValueError('Unknown acceptance ID')
        item=items[patch['id']];old=item['python']
        if patch['old']==patch['new']or old.count(patch['old'])!=1:raise ValueError('Correction must match exactly once')
        new=old.replace(patch['old'],patch['new'])
        if not _numeric_expectations_only(ast.parse(old),ast.parse(new)):
            raise ValueError('Only integer expectations in comparisons may change before freezing')
        item['python']=new
    return {**audit,'requirements':list(items.values()),'limitations':audit['limitations']+limits}


def prompt(goal,original,audit):
    import json
    return f'''Check the arithmetic of these inferred acceptance programs BEFORE any implementation.
Original coding goal: {goal}
Original public contract:
{original}
Programs to be frozen:
{json.dumps(audit['requirements'],ensure_ascii=False)}
You are a FRESH read-only context of the same model. Do NOT inspect or run the application:
it is unfinished, and implementation output is not the oracle. Independently trace the concrete
test inputs using ONLY the original public rules. Recount aggregate events/movements, loop
iterations, workspace isolation, idempotent replays and quantities. Check every nontrivial
hard-coded integer expectation; the generating model often miscounts successful mutations.
For each DEFINITE arithmetic mistake return a minimal exact-text old/new patch with the same
requirement id, source quote and a reason showing the count/derivation. You may change ONLY
integer expectations in comparisons. Never change inputs, operators, branches, assertions,
requested behavior, requirement IDs or provenance. Do not weaken tests to fit unknown code.
Return patches=[] if the expectations are consistent. Other uncertainty belongs in limitations.
Keep output short: patches and their specific calculations, not a rewrite of the programs.
Return only the JSON schema. This review precedes builder access and immutable freezing.
'''
