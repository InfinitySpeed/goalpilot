"""Conservative checks for deterministic generated-harness errors, not app behavior."""
from collections import Counter
import ast


def issues(program):
    tree=ast.parse(program);result=[]
    # import http.client; def http(...): ...; http.client.HTTPConnection(...)
    imports=set();functions=set()
    def module_scope(nodes):
        for node in nodes:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                imports.update(alias.asname or alias.name.split('.')[0]for alias in node.names)
            elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                functions.add(node.name)
            elif isinstance(node,ast.ClassDef):continue
            else:module_scope(ast.iter_child_nodes(node))
    module_scope(tree.body)
    for name in sorted(imports & functions):
        if any(isinstance(node,ast.Attribute)and isinstance(node.value,ast.Name)
               and node.value.id==name for node in ast.walk(tree)):
            result.append(f'Imported name {name!r} is rebound to a function/class but still used as a module/object attribute')
    # dict(token='a', **kw) rejects an override; it does not merge mappings.
    definitions=Counter(n.name for n in ast.walk(tree)if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))
    def own_body(nodes):
        for node in nodes:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):continue
            yield node
            yield from own_body(ast.iter_child_nodes(node))
    functions_by_name={n.name:n for n in ast.walk(tree)
                       if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))and definitions[n.name]==1}
    formals={name:{a.arg for a in (*f.args.posonlyargs,*f.args.args,*f.args.kwonlyargs)}
             for name,f in functions_by_name.items()}
    incoming={name:set()for name in functions_by_name}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id in incoming:
            name=node.func.id
            incoming[name].update({k.arg for k in node.keywords if k.arg is not None}-formals[name])
    # Propagate known overrides through named **kwargs forwarding chains.
    # This catches the indirect wrapper defect from the rejected0.6.3 trial.
    edges=[]
    for name,f in functions_by_name.items():
        if f.args.kwarg:
            for node in own_body(f.body):
                if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id in incoming:
                    if any(k.arg is None and isinstance(k.value,ast.Name)and k.value.id==f.args.kwarg.arg for k in node.keywords):
                        edges.append((name,node.func.id))
    changed=True
    while changed:
        changed=False
        for caller,callee in edges:
            new=incoming[caller]-formals[callee]-incoming[callee]
            if new:incoming[callee].update(new);changed=True
    for function in ast.walk(tree):
        if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef))or not function.args.kwarg:continue
        if definitions[function.name]!=1:continue
        kwarg=function.args.kwarg.arg;reserved=set()
        formal={a.arg for a in (*function.args.posonlyargs,*function.args.args,*function.args.kwonlyargs)}
        for node in own_body(function.body):
            if not(isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='dict'):continue
            if any(k.arg is None and isinstance(k.value,ast.Name)and k.value.id==kwarg for k in node.keywords):
                reserved.update(k.arg for k in node.keywords if k.arg is not None)
        if not reserved:continue
        duplicate=reserved & incoming.get(function.name,set())
        if duplicate:
            result.append(f'{function.name}() receives {sorted(duplicate)!r} already passed explicitly to dict(..., **{kwarg})')
        for node in ast.walk(tree):
            if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id==function.name:
                duplicate=(reserved-formal) & {k.arg for k in node.keywords if k.arg is not None}
                if duplicate:
                    result.append(f'{function.name}() receives {sorted(duplicate)!r} already passed explicitly to dict(..., **{kwarg})')
    return sorted(set(result))


def assertion_signature(program):
    """Necessary guard for plumbing-only repair; not semantic equivalence proof."""
    return Counter(ast.dump(node,include_attributes=False)for node in ast.walk(ast.parse(program))
                   if isinstance(node,ast.Assert)or isinstance(node,ast.Call)and isinstance(node.func,ast.Attribute)
                   and node.func.attr.startswith('assert'))


def merge_repair(original,repaired):
    if not isinstance(repaired,dict)or not isinstance(repaired.get('requirements'),list):
        raise ValueError('Probe repair requires a requirements list')
    broken={r['id']:r for r in original['requirements']if issues(r['python'])}
    incoming=repaired['requirements']
    if len(incoming)!=len(broken)or {r.get('id')for r in incoming}!=set(broken):
        raise ValueError('Repair must retain every defective probe ID, without adding/removing requirements')
    updates={}
    for item in incoming:
        old=broken[item['id']]
        if any(item.get(k)!=old[k]for k in ('id','requirement','source')):
            raise ValueError('Probe repair changed requirement provenance')
        if assertion_signature(item['python'])!=assertion_signature(old['python']):
            raise ValueError('Probe repair changed behavioral assertions')
        if issues(item['python']):raise ValueError('Probe plumbing error remains')
        updates[item['id']]=item
    return {**original,'requirements':[updates.get(r['id'],r)for r in original['requirements']]}
