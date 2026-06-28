# Builder Prompt - v2 Calibration Task

Build v2 of the existing thermal-stack benchmark as a calibration-driven
electronics-cooling qualification repair task.

Task name:

```text
thermal-stack-calibration
```

Expected package name:

```text
beme08/thermal-stack-calibration
```

Task path:

```text
tasks/thermal-stack-calibration/
```

Do not start a new repo. Do not change the domain. Do not build a
thermoelectric, nonlinear, CFD, FEA, COMSOL, or internet-dependent task.

## Core Change

The public task must not provide the full final solver formulas. In particular,
`instruction.md` must not include:

- an explicit internal face conductance formula
- an explicit left boundary conductance formula
- an explicit right boundary conductance formula
- exact interface-side temperature formulas
- an exact energy residual formula as a direct implementation recipe

Instead, frame the benchmark as a realistic legacy engineering repair task:

- the agent inherits a thermal-stack qualification tool used for electronics
  cooling audits
- the tool has drifted from the approved model
- the agent repairs it using engineering notes, visible calibration cases,
  approved calibration outputs, unit and field conventions, code structure, and
  physical invariants
- the hidden verifier checks generalization to unseen qualification cases

The task must remain fair. The approved model must be recoverable from public
materials, but not handed over line by line.

## Keep From v1.1

Keep the current infrastructure:

- separate verifier
- deterministic independent reference solver
- strict JSON schema checks
- hidden expected outputs absent from `/app`
- `/tests` and `/app/data` mutation guards
- oracle/nop support
- Docker oracle/nop support
- 256-state partial-fix audit
- blocking case differentiation audit

Do not change the app architecture, merge modules, or change the eight defect
classes or patch semantics.

## Public Artifacts

`instruction.md` should include:

- CLI
- input/output schema
- validation rules
- high-level physical invariants
- engineering-note summaries
- calibration objective
- visible calibration artifacts

`/app/data/calibration_cases.json` should contain public visible calibration
cases.

`/app/data/approved_outputs.json` should contain approved outputs for those
public cases only.

`/app/docs/engineering_notes.md` should include realistic but partial notes:

- contact resistance creates interface temperature drop
- material properties are assigned by cell-center layer membership
- source terms are volumetric and affect energy balance
- the right boundary is convective, not fixed temperature
- boundary and interface diagnostics must be physically consistent

Avoid exact solver formulas in public materials.

## Hidden Cases

Hidden generalization cases should cover:

- high contact resistance
- zero contact
- high conductivity contrast
- reversed conductivity contrast
- source left/right of contact
- source on both sides of contact
- strong and weak convection
- multi-layer stacks

## Audit Requirements

The audit must prove:

- nop reward is `0.0`
- oracle reward is `1.0`
- only all-fixed passes if feasible
- hidden cases detect all eight defect classes with numerical margin
- case differentiation reports detecting case IDs, responsible output fields,
  and signal margin versus verifier tolerance

## Validation Required Before Review

- `git diff --check`
- `bash -n test.sh` and `bash -n solve.sh`
- Python compile
- visible calibration smoke
- patch smoke
- case differentiation audit
- 256-state audit, only `0xff` passes
- local nop reward `0.0`
- local oracle reward `1.0`
- anti-cheat `/tests` mutation smoke reward `0.0`
- Docker nop reward `0.0`
- Docker oracle reward `1.0`

Stop after validation. Do not commit, push, upload, or run official `/run`
trials.
