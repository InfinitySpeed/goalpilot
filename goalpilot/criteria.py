"""Trace user requirements to frozen executable evidence."""
from .model import ContractError


def validate(criteria, goal, check_ids):
    if criteria is None:
        return None
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 8:
        raise ContractError('criteria must contain 1 to 8 goal-derived items')
    available, seen, frozen = set(check_ids), set(), []
    for item in criteria:
        if not isinstance(item, dict):
            raise ContractError('Every criterion must be an object')
        ident, statement = item.get('id'), item.get('statement')
        quote, links = item.get('source_quote'), item.get('check_ids')
        blocker = item.get('blocker', '')
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ContractError('Criterion IDs must be nonempty and unique')
        if not isinstance(statement, str) or not statement.strip():
            raise ContractError('Every criterion needs a concise statement')
        if not isinstance(quote, str) or not quote.strip() or quote not in goal:
            raise ContractError('Each criterion must quote its source from the original goal exactly')
        if (not isinstance(links, list) or any(not isinstance(x, str) for x in links)
                or len(links) != len(set(links)) or any(x not in available for x in links)):
            raise ContractError('Criterion check_ids must reference distinct submitted checks')
        if not isinstance(blocker, str):
            raise ContractError('Criterion blocker must be text')
        if not links and not blocker.strip():
            raise ContractError('Every criterion needs an executable check or an explicit blocker')
        seen.add(ident)
        frozen.append({'id': ident, 'statement': statement.strip(), 'source_quote': quote,
                       'check_ids': list(links), 'blocker': blocker.strip()})
    return frozen


def validate_requirements(requirements, criteria, goal):
    """Freeze an explicit inventory of goal intents and their criterion links."""
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 16:
        raise ContractError('requirements must contain 1 to 16 goal-derived items')
    criteria_by_id = {item['id']: item for item in criteria}
    seen, covered, frozen = set(), set(), []
    for item in requirements:
        if not isinstance(item, dict):
            raise ContractError('Every requirement must be an object')
        ident, statement = item.get('id'), item.get('statement')
        quote, links = item.get('source_quote'), item.get('criterion_ids')
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ContractError('Requirement IDs must be nonempty and unique')
        if not isinstance(statement, str) or not statement.strip():
            raise ContractError('Every requirement needs a concise statement')
        if not isinstance(quote, str) or not quote.strip() or quote not in goal:
            raise ContractError('Each requirement must quote its source from the original goal exactly')
        if (not isinstance(links, list) or not links
                or any(not isinstance(x, str) for x in links)
                or len(links) != len(set(links))
                or any(x not in criteria_by_id for x in links)):
            raise ContractError('Requirement criterion_ids must reference distinct submitted criteria')
        seen.add(ident)
        covered.update(links)
        frozen.append({'id': ident, 'statement': statement.strip(), 'source_quote': quote,
                       'criterion_ids': list(links)})
    if covered != set(criteria_by_id):
        raise ContractError('Every criterion must map to at least one inventoried requirement')
    return frozen


def assess(criteria, results, *, requirements=None, stale=False):
    if not criteria:
        return {'status': 'stale' if stale else 'unassessed', 'goal_complete': False,
                'coverage_percent': 0, 'verified': 0, 'missing': 0, 'blocked': 0,
                'pending': 0, 'criteria': [], 'requirements': []}
    by_id = {item['id']: item for item in results}
    rows = []
    for criterion in criteria:
        evidence = [by_id.get(ident) for ident in criterion['check_ids']]
        if stale:
            status = 'stale'
        elif criterion['blocker'].strip():
            status = 'blocked'
        elif not evidence or any(item is None for item in evidence):
            status = 'pending'
        elif any(item.get('infrastructure_error') or item.get('timed_out') for item in evidence):
            status = 'blocked'
        elif all(item.get('passed') for item in evidence):
            status = 'verified'
        else:
            status = 'missing'
        rows.append({'id': criterion['id'], 'statement': criterion['statement'],
                     'source_quote': criterion['source_quote'], 'status': status,
                     'checks': [{'id': ident, 'status': ('pending' if by_id.get(ident) is None else
                                 'passed' if by_id[ident].get('passed') else
                                 'blocked' if by_id[ident].get('infrastructure_error') or by_id[ident].get('timed_out') else 'failed')}
                                for ident in criterion['check_ids']],
                     'blocker': criterion['blocker'] or None})
    counts = {name: sum(row['status'] == name for row in rows)
              for name in ('verified', 'missing', 'blocked', 'pending')}
    status = ('stale' if stale else 'verified' if counts['verified'] == len(rows) else
              'blocked' if counts['blocked'] else 'incomplete' if counts['missing'] else 'pending')
    requirement_rows = []
    for requirement in requirements or []:
        linked = [row for row in rows if row['id'] in requirement['criterion_ids']]
        if stale:
            requirement_status = 'stale'
        elif linked and all(row['status'] == 'verified' for row in linked):
            requirement_status = 'verified'
        elif any(row['status'] == 'blocked' for row in linked):
            requirement_status = 'blocked'
        elif any(row['status'] == 'missing' for row in linked):
            requirement_status = 'missing'
        else:
            requirement_status = 'pending'
        requirement_rows.append({'id': requirement['id'], 'statement': requirement['statement'],
                                 'source_quote': requirement['source_quote'],
                                 'criterion_ids': requirement['criterion_ids'],
                                 'status': requirement_status})
    requirement_counts = {name: sum(row['status'] == name for row in requirement_rows)
                          for name in ('verified', 'missing', 'blocked', 'pending')}
    requirement_coverage = (round(100 * requirement_counts['verified'] / len(requirement_rows), 1)
                            if requirement_rows else 0)
    complete = status == 'verified' and (not requirements or requirement_coverage == 100)
    return {'status': 'verified' if complete else status if status != 'verified' else 'incomplete',
            'goal_complete': complete,
            'coverage_percent': requirement_coverage if requirements else round(100 * counts['verified'] / len(rows), 1),
            **counts, 'criteria': rows, 'requirements': requirement_rows,
            'requirements_verified': requirement_counts['verified'],
            'requirements_total': len(requirement_rows),
            'requirements_coverage_percent': requirement_coverage}
