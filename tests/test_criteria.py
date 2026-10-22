import unittest

from goalpilot.criteria import assess, validate, validate_requirements
from goalpilot.model import ContractError


GOAL = 'Export the saved report; preserve exact user wording.'
CRITERIA = [{'id':'export','statement':'Export the report',
             'source_quote':'Export the saved report','check_ids':['roundtrip'],'blocker':''},
            {'id':'wording','statement':'Preserve the original wording',
             'source_quote':'preserve exact user wording','check_ids':['original'],'blocker':''}]


class GoalCriteriaTests(unittest.TestCase):
    def test_source_quotes_and_check_links_are_required(self):
        self.assertEqual(validate(CRITERIA, GOAL, ['roundtrip','original']), CRITERIA)
        for quote, checks in [('unsupported inference',['roundtrip']),
                              ('Export the saved report',['unknown']),
                              ('Export the saved report',[])]:
            candidate=[dict(CRITERIA[0],source_quote=quote,check_ids=checks)]
            with self.assertRaises(ContractError):validate(candidate,GOAL,['roundtrip'])
        blocked=[{'id':'external','statement':'Deploy production','source_quote':'Export the saved report',
                  'check_ids':[],'blocker':'Credentials are unavailable'}]
        self.assertEqual(validate(blocked,GOAL,[])[0]['blocker'],'Credentials are unavailable')
        system=[{'id':'suite','statement':'Preserve project tests','source_quote':'preserve exact user wording',
                 'check_ids':['builder-tests']}]
        self.assertEqual(validate(system,GOAL,['original-tests','builder-tests'])[0]['check_ids'],['builder-tests'])
        too_many=[{'id':str(i),'statement':str(i),'source_quote':'Export the saved report',
                    'check_ids':['roundtrip']} for i in range(9)]
        with self.assertRaises(ContractError):validate(too_many,GOAL,['roundtrip'])

    def test_requirement_inventory_must_quote_goal_and_cover_every_criterion(self):
        requirements=[{'id':'export-intent','statement':'Export the saved report',
                       'source_quote':'Export the saved report','criterion_ids':['export']},
                      {'id':'wording-intent','statement':'Preserve the exact wording',
                       'source_quote':'preserve exact user wording','criterion_ids':['wording']}]
        self.assertEqual(validate_requirements(requirements,CRITERIA,GOAL),requirements)
        for candidate in (requirements[:1],
                          [dict(requirements[0],source_quote='unsupported intent'),requirements[1]],
                          [dict(requirements[0],criterion_ids=['unknown']),requirements[1]],
                          [dict(requirements[0],criterion_ids=[]),requirements[1]]):
            with self.assertRaises(ContractError):
                validate_requirements(candidate,CRITERIA,GOAL)

    def test_vague_goal_inventory_preserves_ambiguity_and_blocks_false_completion(self):
        goal="Make onboarding much better, but don't break anything existing."
        criteria=[{'id':'improve-onboarding','statement':'Demonstrate a defined onboarding improvement',
                   'source_quote':'Make onboarding much better','check_ids':[],
                   'blocker':'No target user, failure point, or success measure is defined.'},
                  {'id':'regression','statement':'Keep existing workflows working',
                   'source_quote':"don't break anything existing",'check_ids':['regression']}]
        requirements=[{'id':'better-onboarding','statement':'Improve the onboarding outcome',
                       'source_quote':'Make onboarding much better','criterion_ids':['improve-onboarding']},
                      {'id':'existing-behavior','statement':'Preserve existing workflows',
                       'source_quote':"don't break anything existing",'criterion_ids':['regression']}]
        criteria=validate(criteria,goal,['regression'])
        requirements=validate_requirements(requirements,criteria,goal)
        result=assess(criteria,[{'id':'regression','passed':True}],requirements=requirements)
        self.assertEqual(result['requirements_total'],2)
        self.assertEqual(result['requirements_verified'],1)
        self.assertEqual(result['requirements_coverage_percent'],50)
        self.assertFalse(result['goal_complete'])

        samples=[
            ('Make the report command a lot faster while keeping the results identical.',
             [{'id':'faster','statement':'Median report runtime is below its recorded baseline',
               'source_quote':'Make the report command a lot faster','check_ids':['benchmark']},
              {'id':'same-output','statement':'Report bytes match the baseline fixtures',
               'source_quote':'keeping the results identical','check_ids':['equivalence']}],
             [{'id':'speed','statement':'Speed up report generation',
               'source_quote':'Make the report command a lot faster','criterion_ids':['faster']},
              {'id':'output','statement':'Preserve exact report output',
               'source_quote':'keeping the results identical','criterion_ids':['same-output']}],
             ['benchmark','equivalence']),
            ('Make sync reliable on flaky networks and never show success until the data is saved.',
             [{'id':'retry','statement':'Recover from transient network faults without dropping queued data',
               'source_quote':'Make sync reliable on flaky networks','check_ids':['fault-injection']},
              {'id':'durability','statement':'Report success only after persisted data can be read back',
               'source_quote':'never show success until the data is saved','check_ids':['fault-injection']}],
             [{'id':'network','statement':'Handle flaky networks',
               'source_quote':'Make sync reliable on flaky networks','criterion_ids':['retry']},
              {'id':'saved-before-success','statement':'Wait for durable save before success',
               'source_quote':'never show success until the data is saved','criterion_ids':['durability']}],
             ['fault-injection']),
        ]
        for sample_goal,sample_criteria,sample_requirements,check_ids in samples:
            with self.subTest(goal=sample_goal):
                checked=validate(sample_criteria,sample_goal,check_ids)
                inventory=validate_requirements(sample_requirements,checked,sample_goal)
                evidence=[{'id':ident,'passed':True} for ident in check_ids]
                assessment=assess(checked,evidence,requirements=inventory)
                self.assertEqual(assessment['requirements_total'],len(inventory))
                self.assertEqual(assessment['requirements_coverage_percent'],100)
                self.assertTrue(assessment['goal_complete'])

    def test_each_criterion_reports_verified_missing_blocked_pending_and_stale(self):
        criteria=validate(CRITERIA,GOAL,['roundtrip','original'])
        passing=[{'id':'roundtrip','passed':True},{'id':'original','passed':True}]
        result=assess(criteria,passing)
        self.assertEqual((result['status'],result['coverage_percent'],result['verified']),('verified',100,2))
        self.assertTrue(result['goal_complete'])
        missing=assess(criteria,[{'id':'roundtrip','passed':False},{'id':'original','passed':True}])
        self.assertEqual(missing['criteria'][0]['status'],'missing');self.assertFalse(missing['goal_complete'])
        blocked=assess(criteria,[{'id':'roundtrip','passed':False,'timed_out':True},passing[1]])
        self.assertEqual(blocked['criteria'][0]['status'],'blocked');self.assertEqual(blocked['blocked'],1)
        explicit=assess(validate([{'id':'external','statement':'Deploy production',
             'source_quote':'Export the saved report','check_ids':[],'blocker':'No credentials'}],GOAL,[]),[])
        self.assertEqual(explicit['status'],'blocked');self.assertFalse(explicit['goal_complete'])
        self.assertEqual(assess(criteria,[],stale=True)['criteria'][0]['status'],'stale')


if __name__=='__main__':unittest.main()
