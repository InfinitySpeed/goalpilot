# GoalPilot Skill 1.11.0: contract-first test guidance

GoalPilot **1.11.0** updates the native workflow guidance; the native adapter remains 0.3.0 and the frozen service engine remains 0.16.0. The added instructions make agents derive test expectations from the written contract, account for intermediate state in sequential operations, isolate rejection tests, and use the existing pre-green test-revision path directly.

## Repeated comparison

The primary comparison uses three synthetic task families: a vague Java range-utility repair, a vague TypeScript transactional-store repair, and a vague goal to complete the Flowdesk multi-team support platform. Each GoalPilot arm ran each task twice in fresh Codex sessions. Flowdesk was judged on 26 independent behavior checks (13 groups across two fixed seeds).

| Mean per caller (6 runs each; equal case weights) | GoalPilot 1.9 | GoalPilot 1.10 | GoalPilot 1.11 |
| :--- | ---: | ---: | ---: |
| Correct independent results | 6/6 | 6/6 | 6/6 |
| Certified GoalPilot closures | 6/6 | 6/6 | 6/6 |
| Original goals preserved | 6/6 | 6/6 | 6/6 |
| Raw tokens, cached input included | 70,792 | 72,939 | **63,974** |
| Uncached input + output tokens | 14,024 | 13,505 | **10,875** |
| Elapsed seconds | 63.12 | 74.55 | **64.07** |

GoalPilot 1.11 used **22.5% fewer uncached input-plus-output tokens than 1.9** and **19.5% fewer than 1.10**. Its aggregate elapsed time was **1.5% higher than 1.9**, within the 3% limit, and **14.1% lower than 1.10**. Raw-token totals are shown for reproducibility; they do not establish subscription-quota savings.

| Case | 1.9 uncached / seconds | 1.10 uncached / seconds | 1.11 uncached / seconds |
| :--- | ---: | ---: | ---: |
| Java range utility | 8,991 / 64.86 | 9,455 / 51.00 | **6,494 / 48.72** |
| TypeScript transactional store | 8,961 / 45.99 | 10,762 / 52.87 | **7,264 / 46.28** |
| Flowdesk ambitious workflow | 24,120 / 78.51 | 20,297 / 119.78 | **18,868 / 97.21** |

The Flowdesk case is a visible tradeoff: 1.11 was **23.8% slower than 1.9 on that case alone**, while Java and TypeScript were faster. Equal-weighting the three task families gives the aggregate 1.5% increase above. The candidate and controls all passed both Flowdesk repetitions; each candidate run passed all 26 independent checks and preserved the original goal.

## Codex native comparison

On the repeated Java and TypeScript tasks, native Codex passed **4/4** independent checks. Per caller, GoalPilot 1.11 averaged **6,879 uncached input-plus-output tokens** versus **8,820** for native Codex (22.0% lower), and **47.50 seconds** versus **74.78 seconds** (36.5% faster). GoalPilot closure certificates do not apply to native Codex.

A prior-day native Flowdesk run on the same model and task passed all 26 artifact checks, but exited in a blocked state instead of completing the goal handoff. It used 57,249 uncached input-plus-output tokens and 314.58 seconds. This is contextual evidence from an earlier protocol, not part of the matched aggregate; its raw 673,953-token count is not a quota comparison.

## Cache and method limits

Each live run used a new ephemeral Codex app-server thread, but the provider's prefix cache could not be disabled. Every trial records raw tokens, input tokens, cached input, output tokens, uncached input-plus-output, elapsed time, independent-judge status, GoalPilot closure, and exact-goal preservation. Cache hit rates varied between runs. The reported uncached-token reduction repeated across Java, TypeScript, and Flowdesk, but these small synthetic task families are not a population sample or a precise conversion to subscription quota.

An earlier wording candidate was rejected: its two TypeScript runs averaged 9,633 uncached tokens and 55.48 seconds, worse than the 1.9 references. Its results and setup failure are retained in the evidence archive rather than omitted.

The experiment source, protocols, individual outcomes, caller meters, test logs, installed skill hashes, and rejected candidate trials are in [the evidence archive](../reports/skill-111-evidence.zip). Machine-readable metrics and source identities are in [skill-111-2026-10-23.json](../reports/skill-111-2026-10-23.json).
