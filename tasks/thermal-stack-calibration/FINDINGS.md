# Benchmark Findings — Thermal Stack Calibration

## Status

- Repo: [Composite-Wall-Conduction-TB3](https://github.com/beme08/Composite-Wall-Conduction-TB3) (PUBLIC)
- Branch: `level3-masking` (submitted default branch); findings recorded on `wip/radiation-pass-checkpoint`
- Task: `tasks/thermal-stack-calibration`
- Submission status: Submitted on default branch `level3-masking`. This finding documents the submitted non-radiation `thermal-stack-calibration` candidate. Later radiation/WIP branches are separate and produced legitimate frontier solves.
- Current status: Post-submission finding. BENCHMARK_HYGIENE.md audit: PASS WITH NOTES.

## Public/private split

Full audit in `BENCHMARK_HYGIENE.md`. Summary:

- Public: 11 calibration cases (one per phenomenon — constant k, date ambiguity, contact aging, temp-dependent contacts, same-geometry regimes, discovery cases). Buggy app source, materials DB, engineering notes.
- Private: 15 hidden cases (h001-h015) in `tests/fixtures/hidden_cases.json`. Includes shifted-coefficient variants, decimal comma format, Kelvin+mm units, repeatability clones, multiple temp-dependent contacts, negative temp coefficient, high-k contrast, extreme temperatures. Reference solver in `tests/fixtures/reference_solver.py`.
- Private truth never placed in `/app/data/`.
- Some hidden cases are near-duplicate/repeatability clones of other hidden cases.

## Baseline gates

| gate | status | notes |
|---|---|---|
| reference/oracle | **1.0** | confirmed |
| nop/starter | **0.0** | confirmed |
| partial-fix audit | **255 states; only all-fixed passes** | all 254 partial-fix states fail |
| Codex standard (gpt-5.5 xhigh) | **3/3 failures (reward 0.0, exceptions 0)** | legitimate calibration-driven repair attempts; incomplete coupled model recovery |
| Claude standard (opus-4-8 max) | **3/3 failures (reward 0.0, exceptions 0)** | same failure mode |
| Codex cheat | **1/1 failure (reward 0.0, exceptions 0)** | local adversarial reproduction; agent chose legitimate repair over bypass |
| Claude cheat | **1/1 failure (reward 0.0, exceptions 0)** | local adversarial reproduction; reward remained 0.0 |

Recorded submitted-branch trials indicate the all-fail target was met for the non-radiation thermal-stack-calibration candidate. Later radiation/WIP branches are separate and produced legitimate frontier solves.

## Leakage gates

Full audit in `BENCHMARK_HYGIENE.md`. Verified:

- Hidden cases not in `/app`
- Reference solver not in agent container
- SHA-256 tree digests guard against data mutation
- Anti-cheat scans (`test_anticheat.py`) for forbidden patterns
- `jobs/`, `logs/` in `.gitignore`

No known leakage risks.

## Agent outcome

- **Codex (gpt-5.5 xhigh):** 3/3 clean failures. All attempted legitimate calibration-driven repairs; none recovered the full coupled model. Trajectory review found no shortcut or hidden-fixture access evidence.
- **Claude Code (claude-opus-4-8 max):** 3/3 clean failures. Same failure mode. Trajectory review found no hidden-fixture, solution, or reward-file access.
- **Cheat (both agents):** 2/2 failures. Adversarial prompts did not uncover a bypass; agents fell through to legitimate repair attempts that also failed.
- **Invalid runs:** 6 attempts excluded (API rate limits, auth failures — not counted per TB3 rules).
- **Failure mode:** Incomplete coupled calibration model recovery. Agents did not repair all 8 planted bugs simultaneously.

## Lessons learned

- Public calibration cases were diagnostic per phenomenon; hidden cases were more combinatorial with some repeatability/near-duplicate notes.
- Later radiation/harder branches showed legitimate frontier solves.
- Adding physics, masking, or more phenomena is not automatically measured hardness.
- Future hardening should require explicit baseline gates and replay gates.
- The 8-planted-bug, 255-state partial-fix audit was effective at ensuring only the all-fixed state passes.

## Quality gates

| gate | status |
|---|---|
| A. Static/build gates | task compiles, Docker builds |
| B. Correctness: reference=1.0, nop=0.0 | confirmed |
| C. Shortcut: coarse/explicit/brute fail | applicable to numerical tasks; for bug-fix task: partial-fix audit confirmed (255 states, 254 partial-fix states fail) |
| D. Leakage: public-private isolation | confirmed via BENCHMARK_HYGIENE.md audit |
| E. Agent replay | not applicable (no prior solver artifact to replay) |
