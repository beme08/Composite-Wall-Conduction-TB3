# Thermal Stack Calibration TB3 Task

A **Terminal-Bench 3 (TB3)** compatible task built as a coding assignment that i spent a week doing for a
**YCombinator AI company**. 

The task asks an agent to repair a legacy electronics-cooling thermal-stack
qualification tool. The public instruction no longer gives the complete solver
formulas; the intended model must be recovered from engineering notes, visible
calibration cases, approved calibration outputs, code structure, units, and
physical invariants. The verifier compares the repaired app against an
independent deterministic reference solver on hidden generalization cases.

Task name `thermal-stack-calibration`, expected
package name `beme08/thermal-stack-calibration`.

## Layout

- `tasks/thermal-stack-calibration/instruction.md` - final agent-facing task instruction
- `tasks/thermal-stack-calibration/environment/` - inherited buggy `/app`
- `tasks/thermal-stack-calibration/tests/` - separate verifier and hidden fixtures
- `tasks/thermal-stack-calibration/solution/` - oracle repair script and ordered patches
- `tools/partial_fix_audit.py` - case differentiation and 256-state audit
- `docs/` - build notes, failure analysis, and local validation results

## Relationship to Terminal-Bench 3

This is a **Terminal-Bench 3 (TB3)** compatible task built as a coding
assignment for a **YCombinator AI company**. Delivered as a standalone GitHub
repository (not a TB3 upstream PR).

## Current status

- Oracle validation: ✅
- Nop validation: ✅
- Docker oracle/nop: ✅
- Codex standard 3/3 valid failures ✅
- Claude standard 3/3 valid failures ✅
- Codex local cheat reproduction: reward 0.0 ✅
- Claude local cheat reproduction: reward 0.0 ✅
- **Models:** OpenAI GPT-5.5 (extra-high reasoning) via Codex, Anthropic Claude Opus 4.8 (high effort) via Claude Code

See `docs/trial-results.md` for the full trial history,
[`docs/codex-trajectory-review.md`](docs/codex-trajectory-review.md) for Codex trajectory analysis,
[`docs/claude-trajectory-review.md`](docs/claude-trajectory-review.md) for Claude trajectory analysis, and
[`docs/failure-analysis.md`](docs/failure-analysis.md) for failure mode analysis.

## Review Steps

From the repo root:

```bash
git diff --check
bash -n tasks/thermal-stack-calibration/tests/test.sh
bash -n tasks/thermal-stack-calibration/solution/solve.sh
python3 tools/partial_fix_audit.py --check-report
```

Visible calibration smoke uses:

```bash
python3 tasks/thermal-stack-calibration/environment/app/scripts/run_solver.py \
  --cases tasks/thermal-stack-calibration/environment/app/data/calibration_cases.json \
  --output /tmp/thermal-stack-calibration-visible.json
```

For local verifier rewards, copy
`tasks/thermal-stack-calibration/environment/app` to a temp `/app`-like
directory, run `tests/test.sh` for nop, then apply `solution/solve.sh` and
rerun `tests/test.sh` for oracle. Expected rewards: nop `0.0`, oracle `1.0`.

For Docker validation, build the two local images and run the separate verifier
against an extracted `/app`. Expected rewards: Docker nop `0.0`, Docker oracle
`1.0`.

## References

See [`docs/references.md`](docs/references.md) for the papers, benchmark docs,
and articles that informed the task design and failure analysis.
