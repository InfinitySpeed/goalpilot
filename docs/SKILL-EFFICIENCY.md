# Skill 1.7.0-r2: measured instruction efficiency

The default is **Skill 1.7.0-r2 with the unchanged engine 0.16.0**. The API/base package remains 1.7.0; r2 identifies the new instruction revision. The frozen experiment called it candidate 1.8.0. That experimental identifier remains in the original protocol; only the publication label changed.

## What changed

Only `SKILL.md` changes among the 49 measured behavior files. All 48 other files, 32 engine modules, helpers, host adapters and verifier behavior remain identical. The 118 added words direct the agent to implement next from supplied context, combine code/tests/criteria/delivery, avoid unnecessary documentation or narration and generate compact code without sacrificing workflows or checks. A shorter304-word candidate was rejected because its extra reads increased total raw tokens.

## Results

| Profile | Verified goals | Raw tokens | Uncached + output | Minutes |
| :--- | ---: | ---: | ---: | ---: |
| Skill 1.7.0-r2, fresh | 20/20 | 1,225,323 | 306,027 | 27.09 |
| Skill 1.7.0-r1, fresh interleaved | 17/20 | 2,298,301 | 391,869 | 40.57 |
| Skill 1.7.0-r1, historical | 20/20 | 1,417,187 | 325,091 | 36.60 |
| Skill 1.3.1, historical | 20/20 | 2,151,252 | 342,356 | 25.69 |
| Native Codex, historical | 19/20 | 4,716,581 | 720,421 | 65.32 |

Against the fresh previous revision: **46.69% fewer raw tokens, 21.91% fewer uncached-input-plus-output tokens and 33.24% less time**. Against historical native Codex: **74.02%, 57.52% and 58.53%**, respectively.

The fresh r1 control was costlier than its published archive:100 provider meter updates versus70 previously. Extra reads and frozen-test failures contributed; serving/cache conditions also differ. Against the published r1 archive, r2 uses 13.54% fewer raw tokens, 5.86% fewer uncached+output tokens and 25.98% less time. These historical observations remain separate from the interleaved primary comparison. Historical Skill 1.3.1 was 5.43% faster than r2; no speed gain over that archive is claimed.

### Completion definition

The candidate completed **20/20 certified goals** and passed independent business checks on **20/20**. The fresh control completed **17/20 certified goals** and passed business checks on **19/20**. Certification requires normal caller exit, frozen original/delivered checks, `goal_complete:true`, byte-identical original goal and independent review. Business correctness is a separate outcome. Two control artifacts were business-correct but blocked by bugs in their own frozen tests; the tickets control passed its local suite but failed the independent contract. Every cost and failure remains included.

Raw tokens include cached input; uncached+output removes cached input. Neither is an exact subscription-quota conversion. Totals include all 20 attempts per arm, including failures. Costs per certified completion, per-case outcomes and provider counter updates are available in the report.

## Promotion protocol

Twenty familiar synthetic Python service goals, 40 full caller invocations, alternating current/candidate order. Same `gpt-6.1-sol`, low effort, permissions, 600-second session limits and exact-engine native Stop-hook isolation. Engine model calls are zero; calling-agent preparation, implementation, repair and closure are metered. Independent grading is included in elapsed time. Fixtures, export, research meta-conversation and the final offline judge replay are excluded from primary time.

Before inference the candidate, source, graders, order and efficacy gates were frozen. Required: 20/20 candidate success, complete meters, at least 10% raw AND uncached+output savings, no more than 3% time regression and no completion regression. Historical-native floors remain 45% both token savings and 25% time. No case was replaced or retried; reviewed grading amendments are the same pre-existing amendments used for both controls.

The original aggregate research admission budget was 3.2M raw/650k uncached+output; the preserved resource-only amendment permits 4M/800k to finish the same 40 calls after expensive control loops. It changes no efficacy threshold, source, session deadline or outcome. Original limits, graceful resource stop and exact continuation are retained in the archive. This is an admission limit, not a hard cap on an in-flight caller.

These are descriptive outcomes on known development cases, one observation per case/arm. They do not establish a production guarantee, blind holdout result, universal goal completion, exact quota savings or cross-host/model performance. Historical references used different serving/cache conditions; all remain visible above. The narrower standalone engine archive (880,023 raw, 197,655 uncached+output, 23.66 minutes) excludes the outer calling agent and is not a full-skill comparison.

## Reproduce the evidence audit

```bash
python3 tools/audit_skill_efficiency.py reports/portable-skill-170-r2-2026-10-23.zip --require-promotion
python3 validate.py
```

The final 40-artifact independent judge replay also reproduced every original reviewed outcome:20/20 candidate business successes and 19/20 control successes, with zero model calls.

These commands use no coding models. The audit reconciles provider counters, exact installed behavior, source/judge identities, original goal bytes, frozen receipts, interleaved order and promotion gates. Imported archived Python is independently pinned before execution. Tests reject forged counters, unapproved executable source and incomplete promotion evidence. The public archive excludes account data, raw assistant/tool traffic and app-server stderr while retaining all provider counter notifications.

- [Machine-readable results](../reports/portable-skill-170-r2-2026-10-23.json)
- [Source, receipts, provider meters and research ledger](../reports/portable-skill-170-r2-2026-10-23.zip)
- [Previous revision's full comparison](PORTABLE-ENGINE.md#previous-revision-skill-170-r1)
- [Rejected shortened-instruction screen](../reports/skill-yield-screen-2026-10-23.json)

The research ledger includes the rejected screen, pilot and all 40 primary callers. The research meta-conversation is **UNKNOWN** and is not reported as zero. Current hosts beyond Codex POSIX and explicit-verification fallback are locally tested, without a model performance claim.

## Installation and rollback

Normal installation selects r2 through `PORTABLE_SKILL.json`. Reinstall and reload the skill to update an existing copy. The doctor now compares selected behavior files, so an older same-version instruction set cannot appear current merely because its version label matches. The original r1 source and proof remain immutable at tag `skill-v1.7.0-r1`; `--profile legacy` still selects the separate historical 1.3.1 baseline.

## Research cost

The retained 46 full-caller trials used **3,967,160 raw tokens** and **782,264 uncached+output tokens**:4 calls from the rejected prior screen,2pilot calls and 40 primary calls. This is measured research usage, not a claim about total subscription consumption. The current research meta-conversation is unmetered and remains UNKNOWN.
