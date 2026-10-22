import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from evaluation.holdouts import evaluate_benchmark, freeze, holdouts
from evaluation.vague_goal import run
from evaluation.default_smoke import run as run_default_smoke
from goalpilot.adapters import AgentResult
from goalpilot.benchmark import fixtures
from goalpilot.model import ContractError, digest, validate
from goalpilot.cli import initialize
from goalpilot.process import run_process


class EvaluationTests(unittest.TestCase):
    def test_holdouts_compile_and_have_unique_ids(self):
        for task, checks in holdouts().items():
            self.assertEqual(len({x['id'] for x in checks}),len(checks))
            for criterion in checks:
                compile(criterion['command'][2],task,'exec')

    def test_frozen_holdout_cannot_be_silently_changed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            spec=freeze(root/'spec.json')
            self.assertEqual(spec['checks_hash'],digest(spec['checks']))
            spec['checks']['notes'][0]['command']=['true']
            with self.assertRaises(ValueError):
                evaluate_benchmark(root,spec)

    def test_holdouts_reject_unfinished_seed_projects(self):
        by_name={x['name']:x for x in fixtures()}
        for task,checks in holdouts().items():
            with self.subTest(task=task),tempfile.TemporaryDirectory() as d:
                root=Path(d)
                for name,content in by_name[task]['files'].items():
                    (root/name).write_text(content)
                for criterion in checks:
                    result=run_process(criterion['command'],root,5)
                    self.assertNotEqual(result.returncode,0,criterion['id'])

    def test_vague_evaluation_requires_explicit_live_flag(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ContractError):
                run(argparse.Namespace(live=False,output=Path(d)/'not-created'))

    def test_default_smoke_requires_explicit_live_flag(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ContractError):
                run_default_smoke(argparse.Namespace(live=False,output=Path(d)/'not-created'))

    def test_external_judge_separate_and_planning_cost_included(self):
        external={'id':'external','description':'Answer really correct','command':[sys.executable,'-c',"from pathlib import Path; assert Path('answer').read_text()=='42'"]}
        planned={'id':'planned','description':'Answer artifact exists','command':[sys.executable,'-c',"from pathlib import Path; assert Path('answer').exists()"]}
        class Actor:
            simulated=True
            prompts=[]
            def execute(self,prompt,repo,timeout,log_dir):
                self.prompts.append(prompt)
                (repo/'answer').write_text('42')
                return AgentResult(0,'fixture result',.001,{'input_tokens':20,'output_tokens':2,'cached_input_tokens':0},simulated=True)
        actor=Actor()
        def planner(options):
            return validate({'goal':options.goal,'repo':str(options.repo),'scope':'inferred','checks':[planned],
                'budget':{'max_calls':3,'wall_seconds':10,'attempt_seconds':2,'max_tokens':1000},
                'planning':asdict(AgentResult(0,'fixture plan',.001,{'input_tokens':100,'output_tokens':10,'cached_input_tokens':0},simulated=True))})
        with tempfile.TemporaryDirectory() as d:
            args=argparse.Namespace(live=True,output=Path(d)/'experiment',wall_seconds=10,attempt_seconds=2,planning_seconds=2,model=None)
            with patch('evaluation.vague_goal.CodexAdapter',return_value=actor),patch('evaluation.vague_goal.initialize',side_effect=planner),patch('evaluation.vague_goal.fixtures',return_value=[{'checks':[external]}]),patch('evaluation.vague_goal.holdouts',return_value={'notes':[]}):
                report=run(args)
            modes={x['mode']:x for x in report['results']}
            self.assertTrue(all(x['external_goal_success'] for x in modes.values()))
            self.assertTrue(all(x['simulated'] for x in modes.values()))
            self.assertEqual(modes['supervised']['usage']['total_tokens'],132)
            self.assertEqual(modes['direct']['usage']['total_tokens'],22)
            self.assertEqual(modes['supervised']['agent_calls'],2)
            self.assertEqual(report['comparison']['token_change_percent'],500)
            self.assertNotIn(external['command'][2],actor.prompts[0])
            self.assertNotIn(external['command'][2],actor.prompts[1])
            previous_calls=len(actor.prompts)
            args.resume=True
            with patch('evaluation.vague_goal.CodexAdapter',return_value=actor),patch('evaluation.vague_goal.initialize',side_effect=planner),patch('evaluation.vague_goal.fixtures',return_value=[{'checks':[external]}]),patch('evaluation.vague_goal.holdouts',return_value={'notes':[]}):
                resumed=run(args)
            self.assertEqual(len(actor.prompts),previous_calls)
            self.assertEqual(len(resumed['results']),2)

    def test_failed_planning_result_is_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            repo=root/'repo'
            repo.mkdir()
            args=argparse.Namespace(goal='Finish goal',repo=repo,output=root/'mission.json',checks=None,
                model=None,max_calls=3,wall_seconds=10,attempt_seconds=2,max_tokens=1000,planning_seconds=2)
            failed=AgentResult(124,'planning interrupted',2,None,timed_out=True,simulated=True)
            with patch('goalpilot.cli.CodexAdapter') as factory:
                factory.return_value.execute.return_value=failed
                with self.assertRaises(ContractError):
                    initialize(args)
            saved=json.loads((root/'mission-planning/result.json').read_text())
            self.assertTrue(saved['timed_out'])
            self.assertIsNone(saved['usage'])
            self.assertEqual(saved['duration_seconds'],2)

    def test_planning_failure_does_not_skip_baseline(self):
        check={'id':'answer','description':'Actual answer','command':[sys.executable,'-c',"from pathlib import Path; assert Path('answer').read_text()=='42'"]}
        class Actor:
            simulated=True
            def execute(self,prompt,repo,timeout,log_dir):
                (repo/'answer').write_text('42')
                return AgentResult(0,'fixture',.001,{'input_tokens':20,'output_tokens':2,'cached_input_tokens':0},simulated=True)
        def planner(options):
            result=options.output.parent/'supervised-planning/result.json'
            result.parent.mkdir(parents=True)
            result.write_text(json.dumps(asdict(AgentResult(124,'timeout',.01,None,timed_out=True,simulated=True))))
            raise ContractError('planning timed out')
        with tempfile.TemporaryDirectory() as d:
            args=argparse.Namespace(live=True,output=Path(d)/'experiment',wall_seconds=10,attempt_seconds=2,planning_seconds=2,model=None)
            with patch('evaluation.vague_goal.CodexAdapter',return_value=Actor()),patch('evaluation.vague_goal.initialize',side_effect=planner),patch('evaluation.vague_goal.fixtures',return_value=[{'checks':[check]}]),patch('evaluation.vague_goal.holdouts',return_value={'notes':[]}):
                report=run(args)
            records={x['mode']:x for x in report['results']}
            self.assertEqual(records['supervised']['internal_status'],'planning_failed')
            self.assertFalse(records['supervised']['external_goal_success'])
            self.assertTrue(records['direct']['external_goal_success'])
            self.assertIsNone(report['comparison']['token_difference'])


if __name__=='__main__':
    unittest.main()
