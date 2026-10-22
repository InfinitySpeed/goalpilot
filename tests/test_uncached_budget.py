import unittest
from goalpilot.engine import run_mission
from goalpilot.model import validate,ContractError
from tests import test_goalpilot as fixtures


class UncachedBudgetTests(unittest.TestCase):
    setUp=fixtures.EngineTests.setUp
    contract=fixtures.EngineTests.contract

    def test_cached_input_is_excluded_and_resume_cannot_refresh_the_budget(self):
        agent=fixtures.ScriptedAgent()
        contract=self.contract(max_uncached_tokens=100)
        state=run_mission(contract,agent,self.run)
        self.assertEqual(state['usage']['total_tokens'],240)
        self.assertEqual(state['usage']['uncached_tokens'],140)
        self.assertEqual(len(agent.prompts),2)
        self.assertIn('observed_uncached_tokens',state['stop_reason'])
        again=run_mission(contract,agent,self.run,resume=True)
        self.assertEqual(len(agent.prompts),2)
        self.assertEqual(again['usage']['uncached_tokens'],140)

    def test_missing_usage_stops_retries_instead_of_treating_it_as_free(self):
        agent=fixtures.ScriptedAgent(usage=False)
        state=run_mission(self.contract(max_uncached_tokens=1000),agent,self.run)
        self.assertEqual(len(agent.prompts),1)
        self.assertEqual(state['stop_reason'],'uncached_usage_unknown')
        self.assertFalse(state['usage']['usage_complete'])

    def test_invalid_budget_is_rejected_before_work(self):
        for value in (0,-1,True,2.5):
            with self.subTest(value=value),self.assertRaises(ContractError):
                validate(self.contract(max_uncached_tokens=value))
