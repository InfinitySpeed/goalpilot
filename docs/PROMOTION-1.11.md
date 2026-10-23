# GoalPilot Skill 1.11.0: contract-first test guidance

GoalPilot **1.11.0** updates the native workflow guidance; the native adapter remains 0.3.0 and the frozen service engine remains 0.16.0. The added instructions make agents derive test expectations from the written contract, account for intermediate state in sequential operations, isolate rejection tests, and use the existing pre-green test-revision path directly.

## Primary comparison: the same tasks on Codex native

We compared GoalPilot 1.11 with direct Codex on the exact same original goal and repository for each task. Both arms ran twice per task in fresh app-server sessions, with the same model (`gpt-6.1-sol`) and low reasoning effort. The task set is a vague Java range-utility repair, a vague TypeScript transactional-store repair, and the ambitious Flowdesk multi-team support-platform goal. Each Flowdesk result was independently judged against 26 behavior groups (13 groups across two fixed seeds).

| Equal-weight mean across the 3 task families (6 runs per arm) | Codex native | GoalPilot 1.11 | Change with GoalPilot |
| :--- | ---: | ---: | ---: |
| Independent task checks passed | 6/6 | **6/6** | equal |
| Flowdesk behavior groups passed | 52/52 | **52/52** | equal |
| Uncached input + output tokens per caller | 13,027 | **10,875** | **−16.5%** |
| Elapsed seconds per caller | 99.25 | **64.07** | **−35.4%** |

| Same task | Codex native uncached / seconds | GoalPilot 1.11 uncached / seconds |
| :--- | ---: | ---: |
| Java range utility | 9,425 / 83.90 | **6,494 / 48.72** |
| TypeScript transactional store | 8,216 / 65.65 | **7,264 / 46.28** |
| Flowdesk ambitious workflow | 21,441 / 148.19 | **18,868 / 97.21** |

All six GoalPilot runs also produced a valid GoalPilot completion certificate and preserved the original goal. Native Codex has no GoalPilot certificate; its six runs passed the same independent task judges. The newly run native Flowdesk trials each passed all 26 behavior groups.

## Cache and method limits

Each live run used a new ephemeral Codex app-server thread, but the provider's prefix cache could not be disabled. Native Codex ran without the GoalPilot skill injected; the environment's local post-tool monitoring hook remained enabled for both arms and does not ask the model to do extra work. Every trial records raw tokens, input tokens, cached input, output tokens, uncached input-plus-output, elapsed time, independent-judge status, GoalPilot closure, and exact-goal preservation. Cache hit rates varied between runs. These small synthetic task families are not a population sample or a precise conversion to subscription quota.

An earlier wording candidate was rejected: its two TypeScript runs averaged 9,633 uncached tokens and 55.48 seconds, worse than the 1.9 references. Its results and setup failure are retained in the evidence archive rather than omitted.

The experiment source, protocols, individual outcomes, caller meters, test logs, installed skill hashes, and rejected candidate trials are in [the evidence archive](../reports/skill-111-evidence.zip). Machine-readable metrics and source identities are in [skill-111-2026-10-23.json](../reports/skill-111-2026-10-23.json).
