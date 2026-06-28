# Thermal Stack Calibration TB3 Task

A **Terminal-Bench 3 (TB3)** compatible task built as a coding assignment for a
**Y Combinator AI company**. Task name `thermal-stack-calibration`, expected
package name `beme08/thermal-stack-calibration`.

The task asks an agent to repair a legacy electronics-cooling thermal-stack
qualification tool. The public instruction no longer gives the complete solver
formulas; the intended model must be recovered from engineering notes, visible
calibration cases, approved calibration outputs, code structure, units, and
physical invariants. The verifier compares the repaired app against an
independent deterministic reference solver on hidden generalization cases.

## Layout

- `tasks/thermal-stack-calibration/instruction.md` - final agent-facing task instruction
- `tasks/thermal-stack-calibration/environment/` - inherited buggy `/app`
- `tasks/thermal-stack-calibration/tests/` - separate verifier and hidden fixtures
- `tasks/thermal-stack-calibration/solution/` - oracle repair script and ordered patches
- `tools/partial_fix_audit.py` - case differentiation and 256-state audit
- `docs/` - build notes, failure analysis, and local validation results

## Relationship to Terminal-Bench 3

This is a **Terminal-Bench 3 (TB3)** compatible task built as a coding
assignment for a **Y Combinator AI company**. Delivered as a standalone GitHub
repository (not a TB3 upstream PR).

## Current status

- Oracle validation: ✅
- Nop validation: ✅
- Docker oracle/nop: ✅
- Post-hardening Codex gatekeeper run: reward **0.0** ✅
- Post-hardening Claude run: API rate-limit exception (not counted as a valid trial)
- Full 3× Codex + 3× Claude + cheat trials: ⬜ **not run**

See `docs/trial-results.md` for the full trial history.

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
