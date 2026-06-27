# Thermal Contact Stack TB3 Task

This repository contains a Terminal-Bench 3 compatible task named
`thermal-contact-stack`, expected package name `beme08/thermal-contact-stack`.

The task asks an agent to repair a pure-Python, cell-centered finite-volume
solver for one-dimensional steady-state thermal stacks with internal thermal
contact resistance. The verifier compares the repaired app against an
independent deterministic reference solver on hidden cases.

## Layout

- `tasks/thermal-contact-stack/instruction.md` - final agent-facing task instruction
- `tasks/thermal-contact-stack/environment/` - inherited buggy `/app`
- `tasks/thermal-contact-stack/tests/` - separate verifier and hidden fixtures
- `tasks/thermal-contact-stack/solution/` - oracle repair script and ordered patches
- `tools/partial_fix_audit.py` - case differentiation and 256-state audit
- `docs/` - build notes, failure analysis, and local validation results

No commits, pushes, uploads, or official `/run` trials have been performed.

## Review Steps

From the repo root:

```bash
git diff --check
bash -n tasks/thermal-contact-stack/tests/test.sh
bash -n tasks/thermal-contact-stack/solution/solve.sh
python3 tools/partial_fix_audit.py --check-report
```

For local verifier rewards, copy `tasks/thermal-contact-stack/environment/app`
to a temp `/app`-like directory, run `tests/test.sh` for nop, then apply
`solution/solve.sh` and rerun `tests/test.sh` for oracle. Expected rewards:
nop `0.0`, oracle `1.0`.

For Docker validation, build the two local images and run the separate verifier
against an extracted `/app`. Expected rewards: Docker nop `0.0`, Docker oracle
`1.0`.
