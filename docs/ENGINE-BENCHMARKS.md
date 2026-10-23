# Standalone direct-first diagnostic

Historical standalone development evidence. The default skill is now [Skill 1.7.0 / engine 0.16.0](PORTABLE-ENGINE.md), measured separately on all 20 goals. The [standalone helper-assisted profile](ENGINE-PROMOTION.md) remains a distinct historical treatment.

On October 22, 2026, a short instruction was added to standalone engine 0.15.0's
direct-first prompt: inspect only instructions, contracts and source/tests relevant
to the requested goal, avoiding broad repository sweeps and generated, vendor,
benchmark or unrelated files. The candidate completed two familiar synthetic
service goals in fresh repositories. It made one model call per goal and passed
all 26 independent judge groups per goal.

| Two-goal totals | GoalPilot 0.7.0 | 0.15.0 direct-first candidate | Native Codex |
| :--- | ---: | ---: | ---: |
| Normal closure | 2/2 | 2/2 | 0/2 |
| Correct artifacts | 2/2 | 2/2 | 2/2 |
| Independent judge groups | 52/52 | 52/52 | 52/52 |
| Raw tokens, including cached input | 454,622 | 329,834 (**−27.45%**) | 1,480,502 (**−77.72%**) |
| Uncached input + output tokens | 78,430 | 53,482 (**−31.81%**) | 106,678 (**−49.87%**) |
| Model-session elapsed time | 576.68 s | 363.68 s (**−36.91%**) | 675.08 s (**−46.13%**) |

The same-task per-case results are:

| Case | Arm | Raw tokens | Uncached + output | Time | Closure | Judge groups |
| :--- | :--- | ---: | ---: | ---: | :---: | :---: |
| Flowdesk | Old GoalPilot 0.7.0 | 238,575 | 38,127 | 285.95 s | Yes | 26/26 |
| Flowdesk | Direct-first candidate | 146,107 | 33,979 | 159.67 s | Yes | 26/26 |
| Flowdesk | Native Codex | 673,953 | 57,249 | 314.58 s | No | 26/26 |
| Stockroom | Old GoalPilot 0.7.0 | 216,047 | 40,303 | 290.73 s | Yes | 26/26 |
| Stockroom | Direct-first candidate | 183,727 | 19,503 | 204.01 s | Yes | 26/26 |
| Stockroom | Native Codex | 806,549 | 49,429 | 360.50 s | No | 26/26 |

The earlier unmodified 0.15.0 direct-first Flowdesk diagnostic completed 26/26
groups in 312.17 s with 296,689 raw tokens. The new prompt run on Flowdesk was
48.8% faster and used 50.7% fewer raw tokens in this single-run comparison; its
uncached-input-plus-output count was 41.2% higher. This is a useful signal, not a
repeatable estimate: each variant ran once, and generation variance is not
measured. The full 0.15.0 finish workflow and the portable Skill were not tested
by this treatment.

All trials used `gpt-6.1-sol` at low effort. Historical 0.7.0 and native controls
come from the same Flowdesk and Stockroom task families as the archived
quota/native study. The six per-case records and both candidate protocols are
copied into the report folder for review; see the
[aggregate](../reports/engine-direct-reading-2026-10-22.json) and run
`python3 tools/check_engine_direct_reading.py` to reconcile the figures. No
candidate reruns were performed. A first attempt was killed by a 60-second
test-wrapper timeout before returning usage; its partial usage is unknown and
excluded. These two familiar tasks do not establish general performance or
exact subscription-quota savings.
