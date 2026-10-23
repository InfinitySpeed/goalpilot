import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Pipeline(JourneyMixin, unittest.TestCase):
    def setUp(self): self.open_service(Service)

    def test_journey(self):
        def flow(c):
            columns = [{'name': 'id', 'type': 'text', 'required': True}, {'name': 'n', 'type': 'integer', 'required': False}, {'name': 'price', 'type': 'money', 'required': True}]
            self.assertEqual(c('schema.put', id='s', columns=columns, key='id'), dict(id='s', revision=1, columns=columns, key='id'))
            raw = 'id,n,price\n a ,bad,1\na,+02,1.09\na,3,2\n"café\nx",,0.01\nz,4,1.001\n'
            self.assertEqual(c('job.create', id='j', schema='s', csv=raw)['status'], 'draft')
            result = c('job.run', id='j', key='k')
            rows = [{'id': 'a', 'n': 2, 'price': 109}, {'id': 'café\nx', 'n': None, 'price': 1}]
            self.assertEqual(result['rows'], rows)
            self.assertEqual((result['accepted'], result['rejected']), (2, 3))
            self.assertEqual([r['row'] for r in result['rejects']], [2, 4, 7])
            self.assertEqual(c('job.run', id='j', key='k'), result)
            rejects(lambda: c('job.run', id='j', key='other'))
            self.assertEqual(c('job.export', id='j'), 'id,n,price\r\na,2,109\r\n"café\nx",,1\r\n')
            old = c('backup')
            c('schema.put', id='s', columns=columns, key='id')
            rejects(lambda: c('job.publish', id='j', expected_revision=True))
            self.assertEqual(c('job.publish', id='j', expected_revision=1)['revision'], 2)
            self.assertEqual(c('dataset.get', schema='s'), {'job': 'j', 'rows': rows, 'schema_revision': 1})
            rejects(lambda: c('job.retry', id='j', csv=raw))
            c('restore', state=old)
            self.assertEqual(c('job.retry', id='j', csv='id,n,price\nb,-3,2.3\n')['status'], 'draft')
            self.assertEqual(c('job.run', id='j', key='k'), result)
            self.assertEqual(c('job.run', id='j', key='next')['rows'], [{'id': 'b', 'n': -3, 'price': 230}])
            rejects(lambda: c('job.import', jobs=[{'id': 'x', 'schema': 's', 'csv': 'id,n,price\n'}, {'id': 'y', 'schema': 's', 'csv': 'bad\n'}]))
            rejects(lambda: c('job.get', id='x'))
            self.assertEqual(c('job.import', jobs=[{'id': 'x', 'schema': 's', 'csv': 'id,n,price\n'}]), {'imported': 1})
        self.assertJourney(flow)

    def test_restore_and_race(self):
        self.c('schema.put', id='s', columns=[{'name': 'id', 'type': 'text', 'required': True}], key='id')
        self.c('job.create', id='j', schema='s', csv='id\na\n')
        results = self.race(*[('job.run', {'id': 'j', 'key': 'k'})] * 2)
        self.assertTrue(all(ok for ok, _ in results))
        self.assertEqual(results[0][1], results[1][1])
        self.assertCorruptions(lambda b: b['state']['jobs']['j'].update(accepted=99), lambda b: b['state']['schemas']['s'].update(revision=0))
