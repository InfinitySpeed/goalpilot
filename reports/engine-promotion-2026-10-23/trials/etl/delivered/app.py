import csv
import io
import re
from goalpilot_runtime import ReplayService, require, fields, text, integer, boolean, choice, sequence, idempotent


def banner(): return 'Local Ops — café'


def schema_fields(d):
    fields(d, {'id': text, 'columns': sequence(lambda c: fields(c, {'name': text, 'type': choice('text', 'integer', 'money'), 'required': boolean}), nonempty=True), 'key': text})
    names = [c['name'] for c in d['columns']]
    require(len(set(names)) == len(names), 'Duplicate columns')
    require(any(c['name'] == d['key'] and c['type'] == 'text' and c['required'] for c in d['columns']), 'Invalid primary key')


def reader(raw, schema):
    require(isinstance(raw, str), 'CSV must be text')
    r = csv.reader(io.StringIO(raw, newline=''), strict=True)
    try:
        require(next(r, None) == [c['name'] for c in schema['columns']], 'Invalid CSV header')
    except csv.Error as e:
        raise ValueError(str(e))
    return r


def process(job):
    s = job['snapshot']
    r = reader(job['csv'], s)
    rows, rejects, seen = [], [], set()
    while True:
        try:
            cells = next(r)
        except StopIteration:
            break
        except csv.Error as e:
            rejects.append({'row': r.line_num, 'reason': str(e) or 'Invalid CSV'})
            break
        try:
            require(len(cells) == len(s['columns']), 'Wrong cell count')
            row = {}
            for c, value in zip(s['columns'], cells):
                v = value.strip()
                require(v or not c['required'], 'Required value: ' + c['name'])
                if c['type'] == 'text':
                    row[c['name']] = v
                elif not v:
                    row[c['name']] = None
                elif c['type'] == 'integer':
                    require(re.fullmatch(r'[+-]?[0-9]+', v), 'Invalid integer: ' + c['name'])
                    row[c['name']] = int(v)
                else:
                    require(re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', v), 'Invalid money: ' + c['name'])
                    whole, _, fraction = v.partition('.')
                    row[c['name']] = int(whole) * 100 + int((fraction + '00')[:2])
            key = row[s['key']]
            require(key and key not in seen, 'Empty or duplicate primary key')
            seen.add(key)
            rows.append(row)
        except ValueError as e:
            rejects.append({'row': r.line_num, 'reason': str(e)})
    return {'id': job['id'], 'status': 'processed', 'accepted': len(rows), 'rejected': len(rejects), 'rows': rows, 'rejects': rejects, 'schema_revision': s['revision']}


class Service(ReplayService):
    def initial(self):
        return {'schemas': {}, 'jobs': {}, 'datasets': {}, 'keys': {}}

    def handle(self, state, op, d):
        schemas, jobs = state['schemas'], state['jobs']
        if op == 'schema.put':
            schema_fields(d)
            result = dict(d, revision=schemas.get(d['id'], {}).get('revision', 0) + 1)
            schemas[d['id']] = result
            return result
        if op in ('job.create', 'job.import'):
            entries = [d] if op == 'job.create' else None
            if entries is None:
                fields(d, {'jobs': sequence(lambda x: fields(x, {'id': text, 'schema': text, 'csv': lambda v: require(isinstance(v, str))}))})
                entries = d['jobs']
            pending = {}
            for entry in entries:
                fields(entry, {'id': text, 'schema': text, 'csv': lambda v: require(isinstance(v, str))})
                require(entry['id'] not in jobs and entry['id'] not in pending, 'Job already exists')
                require(entry['schema'] in schemas, 'Unknown schema')
                snapshot = schemas[entry['schema']]
                reader(entry['csv'], snapshot)
                pending[entry['id']] = dict(entry, snapshot=snapshot, revision=1, status='draft')
            jobs.update(pending)
            return pending[d['id']] if op == 'job.create' else {'imported': len(pending)}
        if op == 'dataset.get':
            fields(d, {'schema': text})
            require(d['schema'] in state['datasets'], 'No published dataset')
            return state['datasets'][d['schema']]
        if op == 'job.run':
            fields(d, {'id': text, 'key': text})
            def run():
                require(d['id'] in jobs, 'Unknown job')
                job = jobs[d['id']]
                require(job['status'] == 'draft', 'Job must be draft')
                result = process(job)
                job.update(result)
                return result
            return idempotent(state, d['key'], op, d, run)
        if op in ('job.get', 'job.export', 'job.retry', 'job.publish'):
            spec = {'id': text}
            if op == 'job.retry': spec['csv'] = lambda v: require(isinstance(v, str))
            if op == 'job.publish': spec['expected_revision'] = lambda v: integer(v, minimum=1)
            fields(d, spec)
            require(d['id'] in jobs, 'Unknown job')
            job = jobs[d['id']]
            if op == 'job.get': return job
            if op == 'job.export':
                require(job['status'] in ('processed', 'published'), 'Job is not processed')
                out = io.StringIO(newline='')
                writer = csv.writer(out)
                names = [c['name'] for c in job['snapshot']['columns']]
                writer.writerow(names)
                writer.writerows(['' if row[n] is None else row[n] for n in names] for row in job['rows'])
                return out.getvalue()
            require(job['status'] == 'processed', 'Job must be processed')
            if op == 'job.retry':
                reader(d['csv'], job['snapshot'])
                new = {k: job[k] for k in ('id', 'schema', 'snapshot', 'revision')}
                new.update(csv=d['csv'], status='draft')
                jobs[d['id']] = new
                return new
            require(d['expected_revision'] == job['revision'], 'Revision conflict')
            job.update(status='published', revision=2)
            state['datasets'][job['schema']] = {'job': job['id'], 'rows': job['rows'], 'schema_revision': job['snapshot']['revision']}
            return job
        raise ValueError('Unknown operation')


if __name__ == '__main__': Service.main()
