# Engineering Notes

These notes summarize the approved thermal qualification model used for the
calibration data. They are intentionally engineering notes, not a full solver
derivation.

## Units

- Lengths are meters.
- Temperatures are degrees Celsius. Temperature differences are interpreted in
  kelvin-equivalent units.
- Layer conductivity is `W/(m*K)`.
- Volumetric heat generation is `W/m^3`.
- Contact resistance is `m^2*K/W`.
- Boundary and interface heat fluxes are `W/m^2`.

## Model Intent

The tool represents a one-dimensional steady stack. The left side is attached
to a fixed-temperature reference plate. The right side rejects heat to an
ambient fluid through a convective film. Internal layer boundaries may include
thermal contact resistance.

The approved model is built from cell-centered finite volumes. Layer material
properties are assigned from the material containing the cell center, not from
the downstream face. Internal material changes occur at cell faces.

## Contacts And Interfaces

Thermal contact resistance does not create or remove heat. It creates an
additional temperature drop at an interface while preserving the same heat flux
through the left material side, the contact, and the right material side.

For zero-contact interfaces, the left-side and right-side reported interface
temperatures should agree within numerical tolerance. For nonzero contacts,
`contact_delta_t_c` should have the same sign as the reported interface heat
flux and should grow when contact resistance grows.

High-conductivity contrast interfaces are sensitive to how the two adjacent
half-cells are combined. Arithmetic averaging is not the approved behavior for
qualification reports.

## Sources And Energy Balance

Layer source terms are volumetric. Their contribution scales with cell
thickness when converted to heat per unit area. Positive source terms add heat
to the stack.

The reported boundary fluxes use the positive `+x` convention. A physically
consistent report keeps the temperature field, left flux, right flux, source
total, interface heat fluxes, and energy residual mutually consistent.

## Boundary Behavior

The left boundary is a fixed-temperature plate connected to the first cell
through the near-boundary half cell.

The right boundary is a convection boundary to `t_inf_c`. It is not a fixed
temperature cell. Stronger `h_w_m2_k` pulls the right-side temperature closer to
the ambient; weaker `h_w_m2_k` increases the thermal resistance to ambient.

## Calibration Guidance

Use `/app/data/calibration_cases.json` and `/app/data/approved_outputs.json` to
calibrate the implementation. The cases exercise single-layer conduction,
volumetric heating, material contrast, contact temperature drops, and convection
sensitivity. A repair that only matches those case IDs without implementing the
general model will fail hidden qualification cases.
