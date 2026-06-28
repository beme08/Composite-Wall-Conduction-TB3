# Build Notes

## Scope

Built v2 of the thermal-stack task at `tasks/thermal-stack-calibration`.

The v2 task keeps the same domain, app architecture, verifier structure, and
eight scoped defect classes from v1.1, but changes the public task framing. The
agent now inherits a legacy electronics-cooling qualification tool and must
repair it from calibration artifacts rather than copying solver equations from
the instruction.

The inherited app remains intentionally realistic but compact:

- Pure Python with `numpy.linalg.solve` for dense direct solves.
- One CLI: `python3 /app/scripts/run_solver.py --cases INPUT --output OUTPUT`.
- Cell-centered thermal-stack model with internal contact resistance support.
- Public calibration cases live in `/app/data/calibration_cases.json`.
- Approved public calibration outputs live in `/app/data/approved_outputs.json`.
- Engineering notes live in `/app/docs/engineering_notes.md`.

The separate verifier owns the hidden cases and independent reference solver.

## Originality Search

The v1.1 originality search found no close existing thermal-contact stack or
composite-wall finite-volume task in the available upstream task set. v2 keeps
the same domain while changing the public surface to a calibration-driven repair
workflow.

## Schema Check

Current upstream task examples primarily use `schema_version = "1.0"` with
`artifacts`, `[metadata]`, `[verifier]`, `[agent]`, and `[environment]` sections.
This task follows that convention and does not add custom unsupported defect
fields.

## Anti-Cheat Design

The verifier:

- Copies hidden inputs to a private temp directory before running `/app`.
- Does not pass `/tests` paths to the app CLI.
- Hashes `/tests` before app execution, after app execution, and after grading.
- Hashes `/app/data` before and after grading.
- Writes reward only from `tests/test.sh`.
- Scans agent-visible source for narrow, concrete cheat routes.
- Has no hidden expected outputs in `/app`.

The approved outputs in `/app/data/approved_outputs.json` are public
calibration outputs only.

## Audit

`tools/partial_fix_audit.py` evaluates all 256 subsets of the eight scoped
physics/numerics fixes against the hidden reference and writes only a compact
summary report. It also runs a blocking case differentiation audit: for each
defect class, the corresponding defective variant is compared against the
independent reference solution, and at least one hidden case must exceed 10x the
relevant verifier tolerance.

The audit reports detecting case IDs, responsible output fields, field-level
signal margins for all eight defect classes, strongest-output-field failure
signatures, and targeted all-but-one failure signatures.
