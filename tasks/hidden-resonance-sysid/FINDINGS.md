# Benchmark Findings — Hidden Resonance System Identification

## Status

- Repo: [Composite-Wall-Conduction-TB3](https://github.com/beme08/Composite-Wall-Conduction-TB3) (PUBLIC)
- Branch: `wip/radiation-pass-checkpoint` (NOT the default branch; not merged into `level3-masking`)
- Task: `tasks/hidden-resonance-sysid`
- Submission status: Not submitted. Task exists only on the non-default `wip/radiation-pass-checkpoint` branch.
- Current status: Archived attempt. Boundary-sweep analysis showed the noise-free deterministic LTI setup was fully determining from public calibration data alone. BENCHMARK_HYGIENE.md audit: PASS WITH NOTES.

## Public/private split

Full audit in `BENCHMARK_HYGIENE.md`. Summary:

- Public: low-rate calibration data (`public_calibration.json`, dt=0.05), `simulate.py` stub, engineering notes, starter `fit.py`.
- Private: `tests/private_oracle.c` (C source with hardcoded system matrices), compiled oracle binary (permission 0500). Hidden eval inputs generated at verification time.
- Probe oracle horizon-limited to 2.0s; evaluation window t=2.0s to 6.0s.

## Baseline gates

| gate | status | notes |
|---|---|---|
| reference/oracle (ERA) | **1.0** | confirmed |
| nop/zero-predictor | **0.0** | confirmed |
| naive/fixed-model | **0.0** | confirmed via replay |
| brute/overresolve (timeout) | **0.0** | confirmed |
| Codex standard trials | not run / errors | gatekeeper runs had infrastructure errors (exceptions ≠ 0); no clean failures recorded |
| cheat/adversarial trials | not run | no cheat trials found in repo artifacts |

No complete final all-fail Harbor matrix is recorded for this archived attempt. Baseline gates (oracle, nop, naive, brute, replay) were confirmed via ad-hoc evaluation runs, but no clean frontier-agent trial matrix exists.

**Note on spike runs:** Some ad-hoc spike tests (`spike-hidden-resonance-harbor-*`) show nop receiving reward 1.0 in isolated configurations, indicating task design issues beyond hygiene.

## Leakage gates

Full audit in `BENCHMARK_HYGIENE.md`. Verified:

- Private oracle compiled binary (permission 0500) not in `/app`
- Hidden eval inputs generated at verification time, not stored
- Probe oracle horizon-limited to prevent parameter extraction
- Evaluation window (2.0s–6.0s) separates probe from evaluation
- `jobs/`, `logs/` in `.gitignore`

Public/private split and compiled oracle isolation were clean enough as a benchmark attempt. The core issue is task design, not leakage.

## Agent outcome

- Codex gatekeeper runs produced infrastructure errors, not clean failures.
- No complete agent trial matrix exists for this task.
- Boundary-sweep analysis (see git log `19db8cf Document sysid boundary-sweep findings`) showed the noise-free deterministic LTI system was fully determining: hidden parameters can be identified from public calibration data alone when identification and prediction are computationally cheap.

## Lessons learned

- Public/private split and compiled oracle isolation were clean enough as a benchmark attempt.
- Boundary sweeps showed the core noise-free LTI setup was fully determining — hidden parameters do not matter if identification and prediction are computationally cheap.
- Preserve as evidence of boundary-sweep analysis, not as final strict all-fail candidate.
- A benchmark is not hard because its story sounds hard. It is hard only after cheap solution paths are measured and closed.

## Quality gates

| gate | status |
|---|---|
| A. Static/build gates | task compiles, Docker builds, oracle runs |
| B. Correctness: reference=1.0, nop=0.0 | confirmed |
| C. Shortcut: naive=0.0, brute/timeout=0.0 | confirmed |
| D. Leakage: public-private isolation | confirmed via BENCHMARK_HYGIENE.md audit |
| E. Agent replay | replay baseline confirmed 0.0; but replay is against reference solver, not a prior agent artifact |
