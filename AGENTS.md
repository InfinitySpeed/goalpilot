# Working with this repository

GoalPilot is a skill for coding agents: local verification, focused repairs and less repeated work.

- If the user shared this repository to **install or use GoalPilot**, read [INSTALL.md](INSTALL.md) and complete the installation for the current host, including its local doctor check. The user should not have to manage Git, Python or discovery paths.
- If the request is **development, review or explanation**, work on that request; do not install anything merely because this file exists.
- Choose the current agent explicitly when you know it. T3 Code is a control surface: select its underlying provider. For unknown agents, confirm the native skills location from their documentation or use the generic explicit-load option; do not invent a registration mechanism.
- Preserve original goals, frozen tests, deadlines and failed evidence. Do not launch nested agents/models or live benchmarks unless requested.
- Documentation is in English. Respond to users in their language.
- The main release is the promoted standalone 0.16.0 profile; use `tools/run_engine_profile.py` as its canonical entrypoint and read INSTALL.md’s main-release section for setup. Do not replace it with legacy `goalpilot go` or silently change the portable Skill.
- The portable Skill currently ships the benchmark-matched Codex skill 1.3.1 / engine 0.12.1; standalone source 0.16.0 has a promoted helper-assisted profile documented in docs/ENGINE-PROMOTION.md. Other controller workflows and host adapters remain separate treatments. Keep archived records intact. Compare any changed Skill or engine with both the old GoalPilot and native Codex before claiming performance parity; do not transfer figures across hosts.
