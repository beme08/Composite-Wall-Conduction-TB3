# Thermal Contact Stack

You inherit a pure-Python one-dimensional steady-state finite-volume thermal
stack solver in `/app`. It runs and emits plausible JSON, but its physics and
numerical diagnostics are wrong. Repair the solver so `scripts/run_solver.py`
matches the contract below for valid cases.

Do not replace the task with FEA, CFD, COMSOL, an external PDE solver, internet
data, or nonlinear material modeling. Use a direct dense linear solve.

## CLI

Keep this interface:

```bash
python3 /app/scripts/run_solver.py --cases /path/to/cases.json --output /path/to/results.json
```

The input file is JSON with a top-level `cases` array. Each case has:

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

A missing contact at an internal layer boundary means zero contact resistance.

## Geometry And Validation

The stack spans `x` in `[0, L]` and is divided into `N` uniform cell-centered
finite-volume control volumes:

```text
dx = L / N
x_i = (i + 0.5) dx, for i = 0, ..., N - 1
```

Each cell receives thermal conductivity `k_i` and volumetric heat generation
`q_i` from the layer containing its center.

All internal layer/contact boundaries must lie exactly on cell faces:

```text
x_boundary = m dx, for integer m with 1 <= m <= N - 1
```

Reject invalid cases:

- `L <= 0`
- `N < 4`
- `h <= 0`
- `h > 10000`
- any `k <= 0`
- any `q < 0`
- layers do not exactly cover `[0, L]`
- overlapping layers
- gaps between layers
- internal layer/contact boundaries not aligned to cell faces
- contact resistance `< 0`
- contact interface not located on a layer boundary or cell face

## Finite-Volume Contract

Each internal face may have a thermal contact resistance `R_contact` in
`m^2*K/W`. For ordinary material continuity, `R_contact = 0`. For a contact
interface, `R_contact > 0`.

For adjacent cells `i` and `i+1`:

```text
G_{i+1/2} = 1 / (dx/(2 k_i) + R_contact_{i+1/2} + dx/(2 k_{i+1}))
```

The left boundary at `x = 0` has fixed temperature `T_left`:

```text
G_left = 2 k_0 / dx
```

The right boundary at `x = L` convects to ambient temperature `T_inf` with
coefficient `h`:

```text
G_right = 1 / (dx/(2 k_{N-1}) + 1/h)
```

For each cell `i`:

```text
sum_faces G_face * (T_neighbor_or_boundary - T_i) + q_i * dx = 0
```

For the left boundary, the boundary temperature is `T_left`. For the right
boundary, the boundary temperature is `T_inf`. Positive heat flux is in the
`+x` direction.

## Interface Diagnostics

Report diagnostics only for internal material/contact interfaces. Do not include
`x = 0` or `x = L`. Single-layer cases must report an empty
`interface_diagnostics` array.

For an internal interface at `x_b = m dx` between cells `m-1` and `m`:

```text
T_L = T[m-1]
T_R = T[m]
k_L = k[m-1]
k_R = k[m]
R_contact = contact resistance at that face

G_face = 1 / (dx/(2 k_L) + R_contact + dx/(2 k_R))
q_face = G_face * (T_L - T_R)

T_face_left = T_L - q_face * dx/(2 k_L)
T_face_right = T_R + q_face * dx/(2 k_R)
contact_delta_t_c = T_face_left - T_face_right
```

The expected contact relation is:

```text
contact_delta_t_c = q_face * R_contact
```

If `R_contact = 0`, the left and right interface-side temperatures should be
equal within tolerance. If `R_contact > 0`, the interface may have a temperature
discontinuity.

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
- Case IDs must match exactly.
- `x_m` length must equal `N`.
- `temperature_c` length must equal `N`.
- `interface_diagnostics` must contain exactly one entry for each internal interface.
- `interface_diagnostics` must be sorted by `x_m` ascending.
- Numeric values must be finite.

Boundary fluxes and residual:

```text
left_heat_flux_w_m2 = G_left * (T_left - T_0)
right_heat_flux_w_m2 = G_right * (T_{N-1} - T_inf)
source_total_w_m2 = sum(q_i * dx over all cells)
energy_residual_w_m2 = right_heat_flux_w_m2 - left_heat_flux_w_m2 - source_total_w_m2
```

Correct solutions should have `energy_residual_w_m2` close to zero.
