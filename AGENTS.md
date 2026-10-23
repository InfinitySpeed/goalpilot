# Working with this repository

GoalPilot is a skill for coding agents: local verification, focused repairs and less repeated work.

- If the user shared this repository to **install or use GoalPilot**, read [INSTALL.md](INSTALL.md) and complete the installation for the current host, including its local doctor check. The user should not have to manage Git, Python or discovery paths.
- If the request is **development, review or explanation**, work on that request; do not install anything merely because this file exists.
- Choose the current agent explicitly when you know it. T3 Code is a control surface: select its underlying provider. For unknown agents, confirm the native skills location from their documentation or use the generic explicit-load option; do not invent a registration mechanism.
- Preserve original goals, frozen tests, deadlines and failed evidence. Do not launch nested agents/models or live benchmarks unless requested.
- Documentation is in English. Respond to users in their language.
- The default is promoted Skill 1.7.0-r2 (base API/package 1.7.0) / engine 0.16.0, selected by PORTABLE_SKILL.json. Normal onboarding uses install.py or the bootstrap and works inside the calling session. Read docs/PORTABLE-ENGINE.md for completion modes and whole-caller measurements.
- The standalone 0.16.0 controller remains separate; only prepare tools/run_engine_profile.py when that profile is explicitly requested. Never replace a skill invocation with a nested model controller.
- Keep skills/goalpilot and benchmarks/codex-1.3.1 immutable as historical controls. The default bundle is skills/goalpilot-016. Compare changed skills against both previous GoalPilot and native Codex; never transfer standalone figures or cross-host performance claims.

- Revision r2 changes only the measured SKILL.md guidance. Keep all 48 other behavior files and 32 engine modules exact. Frozen experiment ID 1.8.0 is released as 1.7.0-r2; current proof is docs/SKILL-EFFICIENCY.md. Original r1 remains in its immutable release/evidence archive.
