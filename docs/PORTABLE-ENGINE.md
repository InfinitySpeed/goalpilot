The default is now [generalized Skill 1.9](PROMOTION-1.9.md), composed from the frozen service bundle below and a native adapter. Its metrics are separate. Use --profile candidate for the exact r2 service control.

# Portable skill with engine 0.16.0

Skill 1.7.0-r2 (base API/package 1.7.0) embeds the exact frozen engine 0.16.0. It reuses that engine inside the calling coding-agent session; it does not launch the standalone Codex controller or a second coding model. The original Skill 1.3.1 / engine 0.12.1 remains available as an immutable comparison and fallback.

## Install the default skill

```bash
python3 install.py --host codex
python3 install.py --host claude-code
python3 install.py --host antigravity
python3 install.py --host hermes
```

Choose the host you actually use. T3 Code selects its underlying provider with `--host t3-code --provider codex` (or another supported provider). For other agents, use `--host generic --target <documented-native-skill-directory>/goalpilot`. The bootstrap accepts the same shell flags. Doctor checks do not launch a coding model.

The promoted default is recorded in `PORTABLE_SKILL.json`. `--profile legacy` selects the immutable previous baseline. `--profile candidate` is an explicit alias for the versioned new bundle; it retains the exact r2 service control.

After installation, use `$goalpilot YOUR GOAL` in Codex, `/goalpilot YOUR GOAL` in Claude Code, or ask the current agent to load GoalPilot and achieve the goal. The installed runtime records its interpreter and entry point.

## What changes

- `session begin` preserves the original goal and starts verification in one command. It handles an empty pre-created container, protects nonempty evidence and never resets an existing mission.
- `session deliver` accepts compact, explicitly authored goal criteria. It derives their requirement links and performs the same engine validation; invented source quotes are rejected before acceptance is frozen.
- One authored `assertJourney` callback exercises business assertions directly, over real JSONL and over real HTTP using independent fixtures. Explicit corruption and concurrency checks remain the agent's responsibility.
- Original and delivered suites are frozen independently. Weakening delivered tests after submission invalidates the session. Unsupported checks and blockers remain open.

## Completion modes

On Codex POSIX, the adapter can reuse already configured Stop hooks for this exact engine. In that mode, deliver freezes the submitted acceptance and the Stop hook verifies it after the agent ends; it does not run a duplicate final suite. The hook uses the same calling session for any repair. For a new terminal session, the bundled launcher prepares one reviewed GoalPilot hook set and disables only exact verified duplicates for that process:

```bash
python3 /path/to/installed/goalpilot/scripts/codex_launch.py --audit-only
python3 /path/to/installed/goalpilot/scripts/codex_launch.py -- --cd /path/to/project
```

The audit makes zero model calls and verifies the effective configuration before reporting readiness. The launch command starts Codex normally; it belongs outside an already running coding-agent session. It does not rewrite global settings or disable unrelated or managed policies. Existing correctly configured GoalPilot hooks can also own verification directly. The local verifier never launches this command on the agent's behalf.

A fresh exact-engine hook beacon must match the current thread and project before ownership transfers. Otherwise, delivery verifies immediately. Non-Codex hosts always use explicit local verification and need no Codex executable or login. Never claim the hook benchmark applies to the explicit fallback or another model host.

## Tests and measurement boundaries

Local tests exercise all five installation profiles, exact frozen-engine identity, Unicode goals/paths, three real transports, rejection of invented criteria, preservation of existing evidence, frozen-test tampering, controller-command refusal and one-time Codex Stop verification. Linux execution of those adapters is not a real Claude/Antigravity/Hermes model benchmark or a Windows runtime benchmark.

The standalone controller's published 20-goal figures exclude any outer agent that invokes it. They do not establish the full skill's savings. Whole-skill comparisons must meter the actual calling thread, including instruction reads, context, coding, repairs and verification, with independent behavioral judging. Raw tokens include cached input; uncached input plus output is reported separately. Neither is an exact subscription-quota conversion.

Known synthetic service goals used during development are not evidence for arbitrary repositories, languages, long production goals or other model providers. Exact quotes and requirement links establish traceability; they cannot prove an agent inventoried every implicit intent.

## Measured results

The current instruction revision is **Skill 1.7.0-r2**, with the unchanged engine 0.16.0. It changes only SKILL.md among49 behavior files and completes 20/20 certified goals. Fresh-r1 savings: 46.69% raw, 21.91% uncached+output and 33.24% time. See the [current full comparison and reproducible audit](SKILL-EFFICIENCY.md). The original r1 figures below remain historical evidence.

## Previous revision: Skill 1.7.0-r1

The primary comparison has **20 goals × two arms = 40 recorded caller invocations**, alternating old/new order per case. Every planned outcome is included once; none was retried or replaced. Both arms use the same model, low effort, execution permissions, budget and exact-owned duplicate-hook isolation. No nested engine model is launched. Time includes the calling thread and independent judging, excluding fixture setup, archive copying and the research meta-conversation.

| Profile | Verified goals | Raw tokens | Uncached input | Output | Uncached + output | Seconds |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous Skill 1.3.1, fresh interleaved control | 20/20 | 2,639,864 | 335,304 | 93,872 | 429,176 | 2,457.293 |
| **Skill 1.7.0 / engine 0.16.0, complete invocation** | **20/20** | **1,417,187** | **238,340** | **86,751** | **325,091** | **2,195.825** |
| Native Codex, frozen historical control | 19/20 | 4,716,581 | 499,412 | 221,009 | 720,421 | 3,919.077 |
| Previous Skill 1.3.1, historical archive | 20/20 | 2,151,252 | 256,343 | 86,013 | 342,356 | 1,541.619 |
| Standalone engine 0.16.0, historical narrower profile | 20/20 | 880,023 | 146,247 | 51,408 | 197,655 | 1,419.580 |

Against the fresh old control, savings are **46.3159% raw, 24.2523% uncached + output and 10.6405% elapsed time**. Against historical native Codex, they are **69.9531%, 54.8749% and 43.9709%**. These are totals, not per-goal guarantees or statistical confidence estimates. Historical and fresh old runs differ substantially, illustrating the limits of cross-run time/cache comparisons: the new run is **42.44% slower** than the historical old skill, despite using **34.12% fewer raw** and **5.04% fewer uncached + output tokens**. It is **54.68% slower** and uses **61.04% more raw / 64.47% more uncached + output tokens** than the narrower historical standalone controller. Both remain visible; no controller figure is transferred to the full skill.

### Completion and acceptance

A verified goal means normal session closure plus all independent reviewed behavioral checks. Both contemporary arms achieve **20/20**, not 15/20 versus 20/20. Five old receipts added a trailing newline to the saved request; the new skill preserves all 20 original requests byte-for-byte. That stricter receipt count is reported separately and does not turn a correct old business outcome into a failure.

The historical annotations/subscriptions grading interpretations are retained unchanged for every arm, with original strict scores available: **18/20** pass the original strict business grader in each contemporary arm; **20/20** pass the documented reviewed grader. No grader was changed for this candidate.

All original promotion gates passed: 20/20 new outcomes with exact goals, complete provider meters and installed-source identity; at least 10% time and 15% raw and uncached-plus-output gains against contemporary old; at least 25% time and 45% on each token metric against historical native. The user waived a significant speed gain after 19 pairs, but the original10% target ultimately passed; that waiver was not needed or applied to the audit.

### Reproduce without spending model quota

```bash
python3 tools/audit_portable_invocation.py reports/portable-skill-170-2026-10-23.zip --require-promotion
python3 tools/check_benchmark.py
python3 tools/audit_promoted_release.py
python3 validate.py
python3 tools/build_skill.py
```

The [derived report](../reports/portable-skill-170-2026-10-23.json), [frozen evidence archive](../reports/portable-skill-170-2026-10-23.zip) and [promoted source identity](../PORTABLE_SKILL.json) contain the source, protocol, all 40 outcomes, provider token notifications, installation hashes, sealed verification receipts and independent judges. The audit recomputes counters and results, checks hashes and source parity, and refuses altered or incomplete evidence. Packaging refuses changed promoted bundle files. The original legacy bundle remains untouched in `skills/goalpilot`; default installation selects `skills/goalpilot-016`. Original instructions, wrappers and all engine files are identical to the measured bundle; release labels, default selection and generic meter-scope metadata were updated after measurement. Historical bundled references remain historical; this document and the new report describe1.7.0.

### Research cost and limitations

The entire adaptation campaign includes **51 metered caller invocations**, including failed/slower prototypes and the discarded duplicate-hook-contaminated cohort: **5,481,429 known raw tokens** and **998,741 known uncached-plus-output tokens**. No provider meter is missing for those calls. This includes the 40 primary calls and 11 earlier development/control calls. Reused historical controls were not rerun in those costs. The research meta-conversation has no complete meter, so entire R&D usage and exact subscription quota remain **UNKNOWN**. The internal resource estimate was amended from 5M/800k to 6M/1.2M raw/uncached-plus-output tokens; only resource caps changed, with both protocol hashes retained. Efficacy gates, sources, graders, order and outcomes were unchanged.

Known synthetic Python service tasks were used during development, not a blind holdout. Each case/arm was observed once. The result does not establish broad production performance, true rates on arbitrary goals, other providers, other host integrations or a subscription-quota percentage. Criteria links improve traceability but do not prove that every implicit user intent was captured.
