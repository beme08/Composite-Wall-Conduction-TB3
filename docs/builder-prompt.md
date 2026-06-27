You are building a fresh Terminal-Bench 3 task repo at:

~/repos/Composite-Wall-Conduction-TB3

This is a development/build prompt, not the final benchmark instruction.
Do not put implementation hints, bug lists, hidden-case strategy, or solution details into instruction.md.
The final benchmark agent should only see the fair task instruction.

Goal:
Create one original TB3-compatible task named thermal-contact-stack.

Recommended package name:
beme08/thermal-contact-stack

Task path:
tasks/thermal-contact-stack/

High-level task:
Build a pure-Python 1D steady-state finite-volume thermal-stack solver.
The inherited app code in /app should run and produce plausible outputs, but it should contain physics/numerics defects.
The benchmark agent must repair the solver so its outputs match a deterministic reference solution.

This is not a generic textbook composite-wall problem. The central engineering feature is thermal contact resistance at internal stack interfaces:
- heat flux is continuous across interfaces
- temperature may be discontinuous across contact interfaces
- the temperature jump equals q * R_contact

Use:
- cell-centered finite-volume method
- constant thermal conductivity per layer
- optional volumetric heat generation per layer
- fixed-temperature left boundary
- convective right boundary
- internal material/contact interfaces
- direct dense linear solve with numpy
- no nonlinear k(T)
- no FEA/COMSOL/CFD
- no external PDE solver
- no LLM judge
- no internet-dependent data
- deterministic numerical verifier

Before building:
Search local upstream tasks for close overlap. Confirm there is no existing heat-conduction / thermal-contact-stack / composite-wall finite-volume task.

Search locations if present:
- /tmp/terminal-bench-3-upstream
- /tmp/terminal-bench-science
- /tmp/terminal-bench-challenges

Suggested grep:
rg -n -i "heat conduction|thermal contact|contact resistance|finite volume|finite-volume|composite wall|thermal stack|thermal resistance|convection boundary|fourier|heat transfer|thermodynamics|pde|conduction solver" .

Existing upstream examples like protein-autointerp-disulfide, photonic-waveguide-routing, and erp-procurement-planning are not close matches.

Also check task.toml/schema conventions in current TB3 upstream. Do not invent unsupported fields. The number of planted defects is metadata/prose, not a schema field, unless current checks prove otherwise.

Core physics contract for instruction.md:

The wall/stack spans x in [0, L] and is divided into N uniform cell-centered finite-volume control volumes.

dx = L / N
x_i = (i + 0.5) dx, for i = 0, ..., N-1

Each cell receives thermal conductivity k_i and volumetric heat generation q_i from the layer containing its center.

All internal material/contact boundaries must lie exactly on cell faces:
x_boundary = m * dx for an integer m with 1 <= m <= N - 1.

Cases with non-face-aligned internal boundaries are invalid and should be rejected.

Each internal face may have a thermal contact resistance R_contact in m^2*K/W.
For ordinary material continuity, R_contact = 0.
For contact-resistance interfaces, R_contact > 0.

Adjacent-cell face conductance:
For adjacent cells i and i+1:

G_{i+1/2} =
  1 / (dx/(2 k_i) + R_contact_{i+1/2} + dx/(2 k_{i+1}))

Left fixed-temperature boundary:
The left boundary at x = 0 has fixed temperature T_left.

G_left = 2 k_0 / dx

Right convective boundary:
The right boundary at x = L convects to ambient temperature T_inf with coefficient h.

G_right = 1 / (dx/(2 k_{N-1}) + 1/h)

Require:
h > 0
h <= 10000

Cell balance:
For each cell i:

sum_faces G_face * (T_neighbor_or_boundary - T_i) + q_i * dx = 0

For the left boundary, the boundary temperature is T_left.
For the right boundary, the boundary temperature is T_inf.

Volumetric heat generation:
q_i is in W/m^3.
For v1, use q_i >= 0 only.
The finite-volume source contribution per unit area is q_i * dx.

Flux sign convention:
Positive heat flux is in the +x direction.

Boundary fluxes:
left_heat_flux_w_m2 = G_left * (T_left - T_0)

right_heat_flux_w_m2 = G_right * (T_{N-1} - T_inf)

Integrated source:
source_total_w_m2 = sum(q_i * dx over all cells)

Energy residual:
energy_residual_w_m2 =
  right_heat_flux_w_m2 - left_heat_flux_w_m2 - source_total_w_m2

Correct solutions should have energy_residual_w_m2 close to zero.

Internal interface diagnostics:
Report diagnostics only for internal material/contact interfaces.
Do not include x = 0 or x = L.
For single-layer cases with no internal interfaces, interface_diagnostics must be [].

For an internal interface at x_b = m * dx between cells m-1 and m:

T_L = T[m-1]
T_R = T[m]
k_L = k[m-1]
k_R = k[m]
R_contact = contact resistance at that face

G_face = 1 / (dx/(2 k_L) + R_contact + dx/(2 k_R))
q_face = G_face * (T_L - T_R)

Temperature on the left material side of the interface:
T_face_left = T_L - q_face * dx/(2 k_L)

Temperature on the right material side of the interface:
T_face_right = T_R + q_face * dx/(2 k_R)

Contact temperature jump:
contact_delta_t_c = T_face_left - T_face_right

Expected relation:
contact_delta_t_c = q_face * R_contact

If R_contact = 0, T_face_left and T_face_right should be equal within tolerance.
If R_contact > 0, the interface may have a temperature discontinuity.

Output format:
The app should write JSON with this structure:

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

Strict schema:
- No missing keys.
- No extra keys.
- Case IDs must match exactly.
- x_m length must equal N.
- temperature_c length must equal N.
- interface_diagnostics must contain exactly one entry for each internal interface.
- interface_diagnostics must be sorted by x_m ascending.
- Numeric values must be finite.

Input validation:
Reject invalid cases:
- L <= 0
- N < 4
- h <= 0
- h > 10000
- any k <= 0
- any q < 0
- layers do not exactly cover [0, L]
- overlapping layers
- gaps between layers
- internal layer/contact boundaries not aligned to cell faces
- contact resistance < 0
- contact interface not located on a layer boundary or cell face

Inherited app defect classes:
The inherited app should contain exactly 8 scoped physics/numerics defect classes, distributed across multiple files.
Do not expose this list in instruction.md.

Defect classes:
1. CONTACT_RESISTANCE_OMITTED
   Face conductance ignores R_contact.

2. CONTACT_TEMPERATURE_CONTINUITY
   Interface diagnostics incorrectly report one continuous interface temperature instead of separate left/right face temperatures and contact jump.

3. INTERFACE_CONDUCTANCE
   Uses arithmetic/material average instead of resistance-based face conductance.

4. LEFT_BOUNDARY_RESISTANCE
   Uses full-cell distance instead of half-cell resistance for the Dirichlet boundary.

5. RIGHT_CONVECTION_RESISTANCE
   Omits half-cell conduction resistance in series with convection.

6. SOURCE_SCALING_SIGN
   Mishandles q_i * dx contribution or source sign.

7. LAYER_FACE_ASSIGNMENT
   Off-by-one or wrong face/contact mapping near layer interfaces.

8. FLUX_AND_RESIDUAL
   Wrong flux sign/formula or energy residual hides imbalance.

Do not expose the bug list, patch names, hidden-case strategy, audit strategy, or solution hints in instruction.md.

Implementation structure:
Make the inherited app realistic enough that rewriting from scratch is nontrivial but not artificial.

Target about 300-450 LOC across modules.

Suggested app structure:
tasks/thermal-contact-stack/environment/app/
  thermal_stack/
    __init__.py
    models.py
    mesh.py
    materials.py
    assembly.py
    solver.py
    postprocess.py
    io.py
  scripts/
    run_solver.py
  data/
    cases.json

Spread defects across at least:
- mesh.py
- materials.py
- assembly.py
- postprocess.py

Do not put all defects in one file.

Repo structure:
README.md
docs/
  build-notes.md
  failure-analysis.md
  trial-results.md
tools/
  partial_fix_audit.py
tasks/
  thermal-contact-stack/
    instruction.md
    task.toml
    environment/
      Dockerfile
      app/
        thermal_stack/
          __init__.py
          models.py
          mesh.py
          materials.py
          assembly.py
          solver.py
          postprocess.py
          io.py
        scripts/
          run_solver.py
        data/
          cases.json
    solution/
      solve.sh
      patches/
        001-fix-contact-resistance-omitted.patch
        002-fix-contact-temperature-continuity.patch
        003-fix-interface-conductance.patch
        004-fix-left-boundary-resistance.patch
        005-fix-right-convection-resistance.patch
        006-fix-source-scaling-sign.patch
        007-fix-layer-face-assignment.patch
        008-fix-flux-and-residual.patch
    tests/
      Dockerfile
      test.sh
      test_solver.py
      test_anticheat.py
      fixtures/
        hidden_cases.json
        reference_solver.py
        audit_report.json

Visible cases:
Provide 3-5 fair visible sanity cases in /app/data/cases.json.
Visible cases should help the agent understand the input/output format and basic regimes, but should not exhaustively cover all hidden regimes.
Do not describe them as bait or traps.

Suggested visible cases:
- single layer, no source, convection
- two layers, no contact resistance, low k contrast
- two layers, small source, moderate convection
- one contact-resistance example with mild R_contact

Hidden cases:
Use about 12 hidden cases covering:
1. single layer, no source, convection
2. single layer, uniform source
3. two layers, no contact, high k contrast
4. two layers, reversed high k contrast
5. two layers, low contact resistance
6. two layers, high contact resistance
7. three layers with two contact interfaces
8. source only left of contact
9. source only right of contact
10. source on both sides of contact
11. strong convection
12. weak convection / fine mesh mixed stack

All hidden interfaces must align with cell faces.
Use moderate N values, e.g. 8 to 80.
Avoid extreme ill-conditioning.
Use high enough k contrast and R_contact values to expose defects.

Case differentiation audit:
The case differentiation audit is required and blocking.
It must numerically verify that the chosen hidden cases expose the intended defect classes with the actual parameter values used. Do not rely on theoretical coverage. For each defect class, run the reference solution and a corresponding defective variant, compare outputs under the verifier's tolerances, and confirm that at least one hidden case fails by a comfortable margin.
If any hidden case does not create enough numerical separation from the correct solution, redesign that case before proceeding.
A defect is considered detected only if at least one checked quantity differs by >= 10x its verifier tolerance.

For each defect class, audit_report.json must report:
- defect_name
- target_hidden_cases
- detecting_case_ids
- output_fields_responsible
- max_abs_temperature_error
- max_abs_interface_temperature_error
- max_abs_contact_delta_t_error
- max_abs_flux_error
- max_abs_energy_residual_error
- verifier_passes_with_defect
- signal_margin_vs_tolerance

Required defect coverage:
- CONTACT_RESISTANCE_OMITTED must be caught by high-R_contact cases. Expected signal: contact_delta_t and interface diagnostics wrong.
- CONTACT_TEMPERATURE_CONTINUITY must be caught by contact-resistance cases. Expected signal: temperature_left_c / temperature_right_c / contact_delta_t wrong.
- INTERFACE_CONDUCTANCE must be caught by high-k-contrast cases. Expected signal: temperature profile, interface heat flux, and boundary flux wrong.
- LEFT_BOUNDARY_RESISTANCE must be caught by single-layer and source cases. Expected signal: full temperature profile and left flux wrong.
- RIGHT_CONVECTION_RESISTANCE must be caught by strong-convection cases. Expected signal: right boundary temperature/flux wrong.
- SOURCE_SCALING_SIGN must be caught by source cases, especially fine mesh and high source. Expected signal: max temperature, profile, flux difference, residual.
- LAYER_FACE_ASSIGNMENT must be caught by multi-layer and high-contrast cases. Expected signal: interface diagnostics and temperature profile wrong.
- FLUX_AND_RESIDUAL must be caught by any nonzero-flux/source cases. Expected signal: flux signs or energy residual wrong.

Do not continue to oracle/nop until the case differentiation audit passes. If any defect class is not detected with at least 10x tolerance margin by at least one hidden case, redesign the hidden cases and rerun the audit.

Partial-fix audit:
Implement a 256-state audit over the 8 defect classes.
Goal:
- all-buggy state fails
- all-fixed state passes
- every single-fix-alone state fails
- every all-but-one state fails
- ideally only all-fixed passes

Commit only compact audit_report.json.
Do not commit huge per-state dumps.
Optional detailed output may be written to /tmp only.

Verifier:
Compare against an independent reference solver in tests/fixtures/reference_solver.py.
The reference solver should not import app code.
The reference solver should independently implement the finite-volume equations.

Verifier should check:
- exact JSON schema
- exact case IDs
- x_m
- temperature_c
- interface_diagnostics
- left_heat_flux_w_m2
- right_heat_flux_w_m2
- max_temperature_c
- energy_residual_w_m2

Suggested tolerances:
- x positions: 1e-12 m
- temperatures: 5e-4 C
- interface temperatures: 5e-4 C
- contact_delta_t: 5e-4 C
- fluxes: 1e-2 W/m^2
- max temperature: 5e-4 C
- energy residual: 1e-2 W/m^2

Use tolerance comparisons, not bit-identical comparisons.

Environment:
Use python:3.11-slim.
Pin numpy, for example:
numpy==2.0.2
Do not require scipy unless absolutely necessary.
Dense numpy.linalg.solve is fine for N <= 80.

Anti-cheat:
Reuse secure patterns from Hybrid-Retrieval-Fusion-TB3:
- no /tests path passed to /app
- copy hidden inputs to temp verifier workdir before app run
- hash /tests before and after app execution
- hash /app/data before and after app execution
- fail reward if /tests or /app/data are mutated
- strict schema validation
- reward written only by verifier
- no hidden expected outputs in /app
- malicious /tests mutation smoke should reward 0.0
- no jobs committed
- no tokens committed

task.toml:
Use current TB3-compatible schema.
Do not invent unsupported fields.
Use a difficulty explanation emphasizing:
- thermal contact resistance
- finite-volume discretization
- temperature discontinuity at interfaces
- coupled flux/contact-jump/energy diagnostics
- realistic electronics cooling / thermal stack audit workflow

Use a verification explanation emphasizing:
- deterministic reference solver
- strict schema
- numerical comparison
- flux, contact temperature jump, and energy balance checks
- no LLM judge

Expected package/task name:
beme08/thermal-contact-stack

Requirements before review:
- originality grep completed
- task.toml/schema check completed
- git diff --check passes
- bash -n test.sh and solve.sh pass
- Python compiles
- reference sanity checks pass
- case differentiation audit passes with at least 10x tolerance margin
- 256-state partial-fix audit passes
- local oracle reward 1.0
- local nop reward 0.0
- Docker oracle reward 1.0
- Docker nop reward 0.0
- anti-cheat mutation smoke reward 0.0
- do not commit, push, upload, or run official /run trials until reviewed
