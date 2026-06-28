# Thermal Stack Calibration

You inherit a pure-Python thermal-stack qualification tool in `/app`. It is used
for electronics cooling audits of layered packages with internal thermal contact
interfaces. The tool still runs and emits plausible JSON, but it has drifted
from the approved qualification model.

Repair the tool so `/app/scripts/run_solver.py` matches the approved model for
the public calibration data and generalizes to hidden qualification cases.

Do not replace the task with FEA, CFD, COMSOL, an external PDE solver, internet
data, or nonlinear material modeling. Keep the existing compact Python
implementation style and use a direct dense linear solve.

## CLI

Keep this interface:

```bash
python3 /app/scripts/run_solver.py --cases /path/to/cases.json --output /path/to/results.json
```

The input file is JSON with a top-level `cases` array. Public calibration cases
are available at:

```text
/app/data/calibration_cases.json
```

Approved outputs for those calibration cases are available at:

```text
/app/data/approved_outputs.json
```

Use those files with the engineering notes in `/app/docs/engineering_notes.md`
to recover the intended model. The hidden verifier checks unseen qualification
cases, so do not hard-code the calibration outputs.

## Case Schema

Each case has:

- `case_id`
- `length_m`
- `num_cells`
- `t_left_c`
- `t_inf_c`
- `h_w_m2_k`
- `layers`
- optional `contacts`

Each layer has:

- `name`
- `x_start_m`
- `x_end_m`
- `k_w_m_k`
- optional `q_w_m3`, defaulting to `0.0`

Each contact has:

- `x_m`
- `r_contact_m2_k_w`

A missing contact at an internal layer boundary means ordinary material
continuity with zero added contact resistance.

## Geometry And Validation

The stack spans `x` in `[0, L]` and is represented by `N` uniform
cell-centered control volumes. Report one `x_m` coordinate per cell center,
from the first half-cell location through the last half-cell location.

Each cell receives its material properties from the layer containing the cell
center. Internal layer and contact boundaries must lie exactly on cell faces.

Reject invalid cases:

- `length_m <= 0`
- `num_cells < 4`
- `h_w_m2_k <= 0`
- `h_w_m2_k > 10000`
- any `k_w_m_k <= 0`
- any `q_w_m3 < 0`
- layers do not exactly cover `[0, L]`
- layers overlap
- gaps exist between layers
- internal layer/contact boundaries are not aligned to cell faces
- contact resistance is negative
- contact interface is not located on an internal layer boundary and cell face

## Qualification Behavior

The approved model is a steady one-dimensional conduction model for a layered
stack with optional volumetric heat generation and a convective ambient on the
right side. Positive heat flux is in the `+x` direction.

Use the public calibration outputs and engineering notes to repair these
behaviors:

- material assignment by cell center
- source terms with correct units and sign
- contact resistance effects at internal interfaces
- high-contrast material interface behavior
- fixed-temperature behavior at the left boundary
- convective, not fixed-temperature, behavior at the right boundary
- consistent boundary fluxes, interface diagnostics, and energy balance

Physical invariants that should hold for valid outputs:

- single-layer cases have no internal interface diagnostics
- zero-contact material interfaces have continuous interface-side temperature
  within numerical tolerance
- nonzero contact resistance may create a temperature drop at the interface
- heat flux through an internal interface is single-valued
- right boundary behavior changes with `h_w_m2_k`
- volumetric generation changes both the temperature field and the global
  energy balance
- the reported energy residual should be close to zero for the approved model

## Output Schema

Write JSON with exactly this structure:

```json
{
  "results": [
    {
      "case_id": "case-001",
      "x_m": [0.0025, 0.0075],
      "temperature_c": [100.0, 98.1],
      "interface_diagnostics": [
        {
          "x_m": 0.04,
          "heat_flux_w_m2": 1234.5,
          "temperature_left_c": 82.1,
          "temperature_right_c": 76.4,
          "contact_delta_t_c": 5.7
        }
      ],
      "left_heat_flux_w_m2": 1200.0,
      "right_heat_flux_w_m2": 1800.0,
      "max_temperature_c": 103.2,
      "energy_residual_w_m2": 0.0
    }
  ]
}
```

Strict requirements:

- No missing keys.
- No extra keys.
- Case IDs must match exactly and remain in input order.
- `x_m` length must equal `num_cells`.
- `temperature_c` length must equal `num_cells`.
- `interface_diagnostics` must contain exactly one entry for each internal
  layer interface.
- `interface_diagnostics` must be sorted by `x_m` ascending.
- Numeric values must be finite.

## Calibration Objective

First make the tool reproduce `/app/data/approved_outputs.json` for
`/app/data/calibration_cases.json`. Then generalize the repair to arbitrary
valid qualification cases with the same schema and physical conventions.

The verifier will compare your output on hidden cases against an independent
approved reference implementation. It checks the exact JSON schema, cell
coordinates, temperatures, interface diagnostics, boundary fluxes, maximum
temperature, and energy residual with numerical tolerances.
