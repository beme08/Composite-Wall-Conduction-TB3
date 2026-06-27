# Build Notes

## Scope

Built a fresh TB3 task at `tasks/thermal-contact-stack` for the
`thermal-contact-stack` benchmark.

The inherited app is intentionally realistic but compact:

- Pure Python with `numpy.linalg.solve` for dense direct solves.
- One CLI: `python3 /app/scripts/run_solver.py --cases INPUT --output OUTPUT`.
- Cell-centered finite-volume discretization over a 1D thermal stack.
- Internal contact resistance support in the input schema and diagnostics.
- Visible cases live in `/app/data/cases.json`.

The separate verifier owns the hidden cases and independent reference solver.

## Originality Search

Searched `/tmp/terminal-bench-3-upstream/tasks` for heat conduction, thermal
contact, contact resistance, finite-volume, composite wall, thermal stack,
thermal resistance, convection boundary, Fourier, heat transfer,
thermodynamics, and conduction solver terms. No close existing thermal-contact
stack or composite-wall finite-volume task was found. The only scientific PDE
hit was `ks-solver-cpp`, which is a nonlinear disk PDE solver and not close.

The optional `/tmp/terminal-bench-science` and `/tmp/terminal-bench-challenges`
paths were absent in this environment.

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

## Audit

`tools/partial_fix_audit.py` evaluates all 256 subsets of the eight scoped
physics/numerics fixes against the hidden reference and writes only a compact
summary report. It also runs a blocking case differentiation audit: for each
defect class, the corresponding defective variant is compared against the
independent reference solution, and at least one hidden case must exceed 10x the
relevant verifier tolerance.

v1.1 tightened the hidden suite and audit reporting without changing the app
architecture or the eight defect classes:

- `h001` was weakened so first-case boundary failures no longer dominate the
  audit signatures.
- `h002` was strengthened as the source/residual case.
- `h005_entangled_high_contrast_contact` replaces the weak contact case with a
  face-aligned high-k-contrast contact case with a meaningful contact
  temperature jump.
- `h011` was sharpened as the strong-convection case.
- Case differentiation now reports detecting case IDs, responsible output
  fields, and field-level signal margins for all eight defect classes.
- The 256-state audit records strongest-output-field failure signatures and
  targeted all-but-one failure signatures to expose false-summit coverage.
