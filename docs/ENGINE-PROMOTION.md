# Frozen engine 0.16.0 promotion

The helper-assisted standalone profile passed every preregistered promotion gate on the same 20 synthetic service goals. Source and benchmark inputs were frozen before the confirmation. No primary outcome was retried or replaced. The portable Skill remains 1.3.1/engine 0.12.1.

| Configuration | Verified goals | Raw tokens | Uncached input + output | Time including judge |
|---|---:|---:|---:|---:|
| GoalPilot Skill 1.3.1 (frozen) | 20/20 | 2,151,252 | 342,356 | 1,541.62 s |
| Codex native (frozen) | 19/20 | 4,716,581 | 720,421 | 3,919.08 s |
| GoalPilot 0.16.0 helper-assisted profile | 20/20 | 880,023 | 197,655 | 1,419.58 s |

Versus the current Skill control: **59.09% fewer raw tokens**, **42.27% fewer uncached-input-plus-output tokens**, and **7.92% time savings**. Versus native Codex: 81.34%, 72.56% and 63.78% savings respectively. Time includes complete caller execution, verification and independent judging.

The host provisions exact-hash generic storage/transport helpers, provides their API without repeatedly reading their source, and freezes original and delivered unittest suites. One authored business journey can now run directly, through real JSONL and through real HTTP on isolated initial fixtures, including dynamically generated IDs and domain rejections. The host derives its verification commands, so the model produces one compact delivery report.

## Run the measured profile

```sh
python3 tools/run_engine_profile.py --goal-file /path/to/goal.txt --repo /path/to/project --run-dir /path/to/evidence --sandbox danger-full-access
```

This explicit permission setting matches the archived controls and this benchmark. The launcher defaults to workspace-write; that setting and ordinary go workflows do not inherit the performance figures. Model gpt-6.1-sol at low effort, wall 600 s, max 2 calls and soft 700,000 raw tokens match the recorded profile. The measured entrypoint runs directly from a terminal. If another agent launches it, that outer caller's tokens and time add to these figures. Helper provisioning is opt-in, requires bounded original unittest coverage, rejects filename collisions, and does not claim arbitrary-project support. Existing storage formats retain their own full domain validator; replay storage is for new pure apps with unspecified formats.

## Evidence and limits

[Promotion manifest](../PROMOTED_ENGINE.json), [full per-case report](../reports/engine-promotion-2026-10-23.json), [frozen source ZIP](../releases/goalpilot-engine-0.16.0.zip). Source tree SHA256: `50d720706d4f307d52cb08d02ada1d741e7206b9e2c5fc62d771f96e51124028`. ZIP SHA256: `92e217cf2e4d153238947264d47304c12b5152e9381ce345505201798572d0cc`.

Run the portable offline evidence audit with `python3 tools/audit_promoted_release.py` (zero model calls). It reruns the exact registered checker, relocating only the historical controls-file path in a temporary copy, and verifies every original promotion gate. Provider meter notifications, delivered files, judgments and frozen checker are included in the report folder. The original source-path audit is `python3 tools/check_engine_promotion.py /workspace/goalpilot-research/promotion-20261023/rc4-confirmation --require-promotion --artifact releases/goalpilot-engine-0.16.0.zip`. Raw trials, delivered projects, provider meter events, exact graders and all rejected variants remain in `/workspace/goalpilot-research/promotion-20261023`. The report copies the protocol, CI receipt and byte-identical historical controls. 304 local tests passed before this confirmation.

These are familiar public synthetic cases, with historical controls; the one-case current Skill calibration showed timing drift. The comparison is descriptive and is not a guarantee for arbitrary goals or another host. Both the original strict score and the existing reviewed score are retained. The same two previously documented scoring amendments were applied before every new outcome; no scoring rule changed to promote this version. Raw/cached/uncached/output token counters do not establish an exact subscription-quota conversion. Research costs are reported separately; root-conversation usage and the administrative authentication failure are not fully metered.
