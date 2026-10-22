from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from goalpilot.adapters import AgentResult, CodexAdapter, parse_events
from goalpilot.benchmark import benchmark, fixtures
from goalpilot.cli import initialize, main
from goalpilot.engine import atomic_json, lock, run_mission, token_totals
from goalpilot.metrics import aggregate, html_report, summarize, wilson
from goalpilot.lab import run_lab
from goalpilot.activity import changes, snapshot
from goalpilot.model import ContractError, digest, validate
from goalpilot.process import run_process


class ScriptedAgent:
    simulated = True

    def __init__(self, actions=(), *, usage=True, fatal=False):
        self.actions = list(actions)
        self.prompts = []
        self.usage = usage
        self.fatal = fatal

    def execute(self, prompt, repo, timeout, log_dir):
        self.prompts.append(prompt)
        if self.actions:
            self.actions.pop(0)(repo)
        return AgentResult(1 if self.fatal else 0, "Everything is finished!", 0.001,
                           {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 50} if self.usage else None,
                           fatal=self.fatal, simulated=True)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run = self.root / "run"

    def contract(self, checks=None, **budget):
        checks = checks or [{"id": "result", "description": "User-visible result is exactly correct", "command": [sys.executable, "-c", "from pathlib import Path; assert Path('answer').read_text() == '42'"], "timeout_seconds": 1}]
        return {"goal": "Create the working answer", "repo": str(self.repo), "scope": "user_defined", "checks": checks,
                "budget": {"max_calls": 4, "wall_seconds": 10, "attempt_seconds": 1, "max_tokens": 1000, **budget}}

    def test_agent_claim_is_never_success(self):
        state = run_mission(self.contract(max_calls=1), ScriptedAgent(), self.run)
        self.assertEqual(state["status"], "budget_exhausted")
        self.assertFalse(summarize(state)["verified_success"])

    def test_recovery_changes_strategy_and_finishes(self):
        agent = ScriptedAgent([lambda p: None, lambda p: (p/"answer").write_text("42")])
        state = run_mission(self.contract(), agent, self.run)
        self.assertEqual(state["status"], "completed")
        self.assertEqual([x["strategy"] for x in state["calls"]], ["implement", "diagnose"])
        self.assertIn("Everything is finished!", agent.prompts[1])
        self.assertEqual(summarize(state)["recovery_steps_with_progress"], 1)
        self.assertEqual(state["usage"]["total_tokens"], 240)

    def test_all_strategies_then_stop(self):
        state = run_mission(self.contract(max_calls=9), ScriptedAgent(), self.run)
        self.assertEqual(state["status"], "stalled")
        self.assertEqual([x["strategy"] for x in state["calls"]], ["implement", "diagnose", "alternative", "integrate"])

    def test_multistep_activity_not_prematurely_stopped(self):
        checks=[{"id":"pipeline","description":"Five stages completed","command":[sys.executable,"-c","from pathlib import Path; assert all(Path(f'stage-{i}').exists() for i in range(1,6))"]}]
        actions=[lambda p,n=n: (p/f"stage-{n}").write_text(str(n)) for n in range(1,6)]
        state=run_mission(self.contract(checks,max_calls=8),ScriptedAgent(actions),self.run)
        self.assertEqual(state['status'],'completed')
        self.assertEqual(len(state['calls']),5)
        self.assertEqual(state['calls'][3]['repository_activity']['changed_file_count'],1)

    def test_meaningless_activity_still_bound_by_call_budget(self):
        actions=[lambda p,n=n: (p/f"unrelated-{n}").touch() for n in range(8)]
        state=run_mission(self.contract(max_calls=6),ScriptedAgent(actions),self.run)
        self.assertEqual(state['status'],'budget_exhausted')
        self.assertEqual(len(state['calls']),6)
        self.assertEqual(state['stop_reason'],'max_calls')

    def test_missing_external_verifier_avoids_agent_calls(self):
        checks=[{"id":"checker","description":"External checker","command":[str(self.root/'missing-checker')]}]
        agent=ScriptedAgent()
        state=run_mission(self.contract(checks),agent,self.run)
        self.assertEqual(state['status'],'verification_unavailable')
        self.assertEqual(agent.prompts,[])
        self.assertIsNone(aggregate([state])['groups']['simulated/supervised']['success_rate'])

    def test_missing_project_verifier_can_be_implemented(self):
        verifier=self.repo/'check.py'
        checks=[{"id":"checker","description":"Project command is part of deliverable","command":[str(verifier)]}]
        def implement(p):
            verifier.write_text(f'#!{sys.executable}\nprint("working")\n')
            verifier.chmod(0o755)
        state=run_mission(self.contract(checks),ScriptedAgent([implement]),self.run)
        self.assertEqual(state['status'],'completed')
        self.assertEqual(len(state['calls']),1)

    def test_direct_uses_one_session(self):
        state = run_mission(self.contract(), ScriptedAgent(), self.run, mode="direct")
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(len(state["calls"]), 1)

    def test_resume_cannot_reset_call_budget(self):
        contract = self.contract(max_calls=1)
        run_mission(contract, ScriptedAgent(), self.run)
        agent = ScriptedAgent()
        state = run_mission(contract, agent, self.run, resume=True)
        self.assertEqual(len(state["calls"]), 1)
        self.assertEqual(agent.prompts, [])

    def test_resume_rechecks_previously_completed_repo(self):
        contract = self.contract(max_calls=2)
        (self.repo/"answer").write_text("42")
        state = run_mission(contract, ScriptedAgent(), self.run)
        self.assertEqual(state["status"], "completed")
        (self.repo/"answer").write_text("broken")
        state = run_mission(contract, ScriptedAgent(), self.run, resume=True)
        self.assertNotEqual(state["status"], "completed")

    def test_cannot_resume_changed_contract(self):
        contract = self.contract(max_calls=1)
        run_mission(contract, ScriptedAgent(), self.run)
        contract["budget"]["max_calls"] = 2
        with self.assertRaises(ContractError):
            run_mission(contract, ScriptedAgent(), self.run, resume=True)

    def test_state_contract_tampering_detected(self):
        contract = self.contract(max_calls=1)
        run_mission(contract, ScriptedAgent(), self.run)
        path = self.run/"state.json"
        state = json.loads(path.read_text())
        state["contract"]["goal"] = "Different goal"
        atomic_json(path, state)
        with self.assertRaises(ContractError):
            run_mission(contract, ScriptedAgent(), self.run, resume=True)

    def test_inferred_scope_is_not_verified_goal(self):
        (self.repo/"answer").write_text("42")
        contract = self.contract()
        contract["scope"] = "inferred"
        state = run_mission(contract, ScriptedAgent(), self.run)
        self.assertEqual(state["status"], "scope_passed")
        self.assertFalse(summarize(state)["verified_success"])
        self.assertEqual(len(state["calls"]), 0)

    def test_evidence_outside_repo(self):
        with self.assertRaises(ContractError):
            run_mission(self.contract(), ScriptedAgent(), self.repo/"evidence")

    def test_soft_token_budget_stops_next_call(self):
        state = run_mission(self.contract(max_tokens=110), ScriptedAgent(), self.run)
        self.assertEqual(len(state["calls"]), 1)
        self.assertEqual(state["usage"]["total_tokens"], 120)
        self.assertIn("soft", state["stop_reason"])

    def test_unknown_usage_is_not_zero_usage(self):
        state = run_mission(self.contract(max_calls=1), ScriptedAgent(usage=False), self.run)
        metrics = summarize(state)
        self.assertEqual(metrics["usage"]["calls_without_usage"], 1)
        self.assertFalse(metrics["usage"]["usage_complete"])
        self.assertIsNone(metrics["new_checks_per_1000_tokens"])

    def test_token_difference_unavailable_when_one_condition_has_unknown_usage(self):
        state=run_mission(self.contract(max_calls=1),ScriptedAgent(usage=False),self.run)
        state['simulated']=False
        direct=json.loads(json.dumps(state))
        direct['mode']='direct'
        direct['calls'][0]['result']['usage']={'input_tokens':100,'output_tokens':20,'cached_input_tokens':50}
        comparison=aggregate([state,direct])['comparison']
        self.assertFalse(comparison['token_comparison_available'])
        self.assertIsNone(comparison['reported_token_difference'])
        self.assertIsNone(comparison['reported_token_change_percent'])

    def test_auth_failure_stops_blind_retries(self):
        state = run_mission(self.contract(), ScriptedAgent(fatal=True), self.run)
        self.assertEqual(state["status"], "agent_unavailable")
        self.assertEqual(len(state["calls"]), 1)
        group = aggregate([state])["groups"]["simulated/supervised"]
        self.assertEqual(group["user_defined_runs"], 0)
        self.assertIsNone(group["success_rate"])
        self.assertEqual(group["infrastructure_or_interruption_exclusions"], 1)

    def test_adapter_error_is_checkpointed(self):
        class Broken(ScriptedAgent):
            def execute(self, *a, **kw):
                raise RuntimeError("broken adapter")
        state = run_mission(self.contract(), Broken(), self.run)
        self.assertEqual(state["status"], "adapter_error")
        self.assertEqual(len(state["calls"]), 1)
        self.assertTrue((self.run/"state.json").is_file())

    def test_verification_timeout_cannot_succeed(self):
        checks = [{"id": "slow", "description": "Never finishes", "command": [sys.executable, "-c", "import time; time.sleep(10)"], "timeout_seconds": .05}]
        state = run_mission(self.contract(checks, max_calls=1), ScriptedAgent(), self.run)
        self.assertTrue(state["verifications"][0]["checks"][0]["timed_out"])
        self.assertNotEqual(state["status"], "completed")

    def test_wall_budget_includes_verifications(self):
        checks = [{"id": "slow", "description": "Bounded by wall budget", "command": [sys.executable, "-c", "import time; time.sleep(10)"], "timeout_seconds": 30}]
        state = run_mission(self.contract(checks, wall_seconds=.08), ScriptedAgent(), self.run)
        self.assertEqual(len(state["calls"]), 0)
        self.assertEqual(state["stop_reason"], "wall_seconds")
        self.assertLess(state["active_seconds"], 1)

    def test_concurrent_run_lock(self):
        with lock(self.run/"run.lock"):
            with self.assertRaises(ContractError):
                run_mission(self.contract(), ScriptedAgent(), self.run)

    def test_planning_counted_in_budget_and_usage(self):
        contract = self.contract(max_calls=1)
        contract["planning"] = asdict(AgentResult(0, "{}", .02, {"input_tokens": 10, "output_tokens": 3, "cached_input_tokens": 0}))
        agent = ScriptedAgent()
        state = run_mission(contract, agent, self.run)
        self.assertEqual(agent.prompts, [])
        self.assertEqual(state["usage"]["total_tokens"], 13)
        self.assertEqual(summarize(state)["planning_calls"], 1)

    def test_interrupted_reservation_consumes_budget(self):
        contract = self.contract(max_calls=1)
        state = run_mission(contract, ScriptedAgent(), self.run)
        state["calls"] = [{"strategy": "implement"}]
        state["pending"] = {"call_index": 0, "reserved_seconds": .1, "started_at": time.time()-.1}
        atomic_json(self.run/"state.json", state)
        agent = ScriptedAgent()
        state = run_mission(contract, agent, self.run, resume=True)
        self.assertTrue(state["calls"][0]["interrupted"])
        self.assertEqual(agent.prompts, [])

    def test_regression_uses_restore_strategy(self):
        checks = [{"id": x, "description": x, "command": [sys.executable, "-c", f"from pathlib import Path; assert Path('{x}').exists()"], "timeout_seconds": 1} for x in ["a", "b"]]
        (self.repo/"a").touch()
        agent = ScriptedAgent([lambda p: (p/"a").unlink(), lambda p: [(p/x).touch() for x in ["a", "b"]]])
        state = run_mission(self.contract(checks), agent, self.run)
        self.assertEqual(state["calls"][1]["strategy"], "restore")
        self.assertEqual(state["status"], "completed")

    def test_new_run_does_not_overwrite_existing(self):
        contract = self.contract(max_calls=1)
        run_mission(contract, ScriptedAgent(), self.run)
        with self.assertRaises(ContractError):
            run_mission(contract, ScriptedAgent(), self.run)

    def test_simulated_and_real_results_separated(self):
        (self.repo/"answer").write_text("42")
        state = run_mission(self.contract(), ScriptedAgent(), self.run)
        real = json.loads(json.dumps(state))
        real["simulated"] = False
        result = aggregate([state, real])
        self.assertEqual(set(result["groups"]), {"simulated/supervised", "real/supervised"})
        self.assertEqual(result["groups"]["real/supervised"]["runs"], 1)
        self.assertIsNone(result["groups"]["simulated/supervised"]["success_rate_wilson_95"])

    def test_html_escapes_untrusted_goal(self):
        contract = self.contract(max_calls=1)
        contract["goal"] = "<script>alert(1)</script>"
        state = run_mission(contract, ScriptedAgent(), self.run)
        rendered = html_report(aggregate([state]))
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class ValidationTests(unittest.TestCase):
    def test_invalid_budgets_and_commands(self):
        with tempfile.TemporaryDirectory() as d:
            base = {"goal": "goal", "repo": d, "checks": [{"id": "x", "description": "x", "command": ["true"]}]}
            for value in [-1, 0, float("nan"), float("inf"), True, "4"]:
                contract = json.loads(json.dumps(base))
                contract["budget"] = {"max_calls": value}
                with self.subTest(value=value), self.assertRaises(ContractError):
                    validate(contract)
            for command in ["echo yes", [], [1], [""], ["x\0y"]]:
                contract = json.loads(json.dumps(base))
                contract["checks"][0]["command"] = command
                with self.subTest(command=command), self.assertRaises(ContractError):
                    validate(contract)

    def test_no_empty_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ContractError):
                validate({"goal": "vague", "repo": d, "checks": []})

    def test_init_with_user_checks_is_offline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checks = root/"checks.json"
            checks.write_text(json.dumps([{"id":"x","description":"x","command":["true"]}]))
            args = argparse.Namespace(repo=root, output=root/"mission.json", goal="goal", model=None, max_calls=2, wall_seconds=30, attempt_seconds=10, max_tokens=1000, checks=checks)
            contract = initialize(args)
            self.assertEqual(contract["scope"], "user_defined")
            self.assertNotIn("planning", contract)

    def test_benchmark_requires_live_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["benchmark", "--output", d]), 1)


class UsageTests(unittest.TestCase):
    def test_jsonl_usage_cached_tokens_not_double_counted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"events.jsonl"
            events = ["startup warning", json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"done"}}), json.dumps({"type":"turn.completed","usage":{"input_tokens":1000,"cached_input_tokens":800,"output_tokens":25}})]
            p.write_text("\n".join(events))
            message, usage, fatal = parse_events(p)
            self.assertEqual(message,"done")
            self.assertFalse(fatal)
            self.assertEqual(token_totals([{"result":{"usage":usage}}])["total_tokens"],1025)

    def test_multiple_turns_accumulate(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"events.jsonl"
            event={"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":5}}
            p.write_text(json.dumps(event)+"\n"+json.dumps(event))
            _, usage, _ = parse_events(p)
            self.assertEqual(usage["input_tokens"],200)

    def test_missing_usage_and_auth_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"events.jsonl"
            p.write_text(json.dumps({"type":"turn.failed","error":{"message":"429 quota exceeded"}}))
            _, usage, fatal = parse_events(p)
            self.assertIsNone(usage)
            self.assertTrue(fatal)

    def test_real_observed_refresh_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"events.jsonl"
            p.write_text(json.dumps({"type":"turn.failed","error":{"message":"Your access token could not be refreshed because you have since logged out or signed in to another account. Please sign in again."}}))
            _, usage, fatal = parse_events(p)
            self.assertTrue(fatal)
            self.assertIsNone(usage)

    def test_wilson_interval_small_sample_not_certainty(self):
        lo, hi = wilson(2,2)
        self.assertAlmostEqual(lo, .342380227506653, places=10)
        self.assertAlmostEqual(hi,1)
        self.assertIsNone(wilson(0,0))


class ProcessTests(unittest.TestCase):
    def test_codex_adapter_full_subprocess_roundtrip_with_explicit_test_double(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            repo=root/'repo'
            repo.mkdir()
            shim=root/'fixture-codex'
            shim.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
args=sys.argv
assert args[args.index('--sandbox')+1]=='workspace-write'
assert args[args.index('-a')+1]=='never'
assert 'ORIGINAL GOAL' in sys.stdin.read()
Path('answer').write_text('42')
Path(args[args.index('-o')+1]).write_text('Fixture agent completed work')
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":125,"output_tokens":25,"cached_input_tokens":100}}}}))
''')
            shim.chmod(0o755)
            adapter=CodexAdapter(executable=str(shim))
            adapter.simulated=True
            contract={"goal":"Create answer", "repo":str(repo), "scope":"user_defined", "checks":[{"id":"x","description":"Answer is correct","command":[sys.executable,"-c","from pathlib import Path; assert Path('answer').read_text()=='42'"]}]}
            state=run_mission(contract,adapter,root/'run')
            self.assertEqual(state['status'],'completed')
            self.assertTrue(state['simulated'])
            self.assertEqual(state['usage']['total_tokens'],150)
            self.assertEqual(state['usage']['cached_input_tokens'],100)
            self.assertTrue((root/'run/calls/1/events.jsonl').is_file())

    def test_timeout_kills_descendant_before_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            child="import time; from pathlib import Path; time.sleep(.3); Path('escaped').touch()"
            parent=f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
            result=run_process([sys.executable,"-c",parent], root, .08)
            self.assertTrue(result.timed_out)
            time.sleep(.35)
            self.assertFalse((root/"escaped").exists())

    def test_parent_exit_also_cleans_descendants(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            child="import time; from pathlib import Path; time.sleep(.3); Path('escaped').touch()"
            parent=f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
            result=run_process([sys.executable,"-c",parent],root,1)
            self.assertEqual(result.returncode,0)
            time.sleep(.35)
            self.assertFalse((root/"escaped").exists())

    def test_large_output_is_bounded_but_raw_log_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            result=run_process([sys.executable,"-c","print('a'*10000)"],root,1,log_path=root/"raw.log",max_bytes=100)
            self.assertEqual(len(result.output),100)
            self.assertTrue(result.output_truncated)
            self.assertGreater((root/"raw.log").stat().st_size,10000)

    def test_missing_executable_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_process(["/nonexistent/goalpilot-executable"],Path(d),1)
            self.assertEqual(result.returncode,127)
            self.assertTrue(result.launch_error)

    def test_activity_snapshot_bounded_and_ignores_cache_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)
            (repo/'a').touch()
            before=snapshot(repo)
            (repo/'__pycache__').mkdir()
            (repo/'__pycache__/noise').touch()
            (repo/'link').symlink_to(repo/'a')
            self.assertEqual(changes(before,snapshot(repo))['changed_file_count'],0)
            (repo/'b').touch()
            self.assertEqual(changes(before,snapshot(repo))['changed_files'],['b'])
            _,complete=snapshot(repo,limit=1)
            self.assertFalse(complete)


class FixtureTests(unittest.TestCase):
    def test_live_benchmark_stops_at_first_provider_failure(self):
        with tempfile.TemporaryDirectory() as d:
            args=argparse.Namespace(output=Path(d)/'live',model=None,max_calls=3,wall_seconds=10,attempt_seconds=1,max_tokens=1000)
            agent=ScriptedAgent(fatal=True,usage=False)
            agent.simulated=False
            with patch('goalpilot.benchmark.CodexAdapter',return_value=agent):
                report=benchmark(args)
            self.assertEqual(len(agent.prompts),1)
            self.assertEqual(report['benchmark_status'],'agent_unavailable')
            self.assertEqual(len(report['runs']),1)
            group=report['groups']['real/direct']
            self.assertIsNone(group['success_rate'])
            self.assertEqual(group['user_defined_runs'],0)

    def test_controlled_lab_is_explicit_and_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            report=run_lab(Path(d)/"lab")
            self.assertTrue(report["controlled_result"]["simulated"])
            self.assertEqual(report["controlled_result"]["direct_successes"],1)
            self.assertEqual(report["controlled_result"]["supervised_successes"],3)
            self.assertEqual(report["controlled_result"]["direct_calls"],4)
            self.assertEqual(report["controlled_result"]["supervised_calls"],10)
            self.assertNotIn("real/supervised", report["groups"])

    def test_seed_projects_fail_substantive_acceptance(self):
        for fixture in fixtures():
            with self.subTest(task=fixture["name"]), tempfile.TemporaryDirectory() as d:
                root=Path(d)
                for name, content in fixture["files"].items():
                    (root/name).write_text(content)
                for check in fixture["checks"]:
                    result=run_process(check["command"],root,5)
                    self.assertNotEqual(result.returncode,0,check["id"])


if __name__ == "__main__":
    unittest.main()
