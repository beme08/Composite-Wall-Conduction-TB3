# Engineering Notes

These notes summarize the approved thermal qualification model used for the
calibration data. They are intentionally engineering notes, not a full solver
derivation.

## Units

- Lengths are meters by default. Input cases may specify `length_unit` ("m" or
  "mm"); values must be converted to meters before solving.
- Temperatures are degrees Celsius by default. Input cases may specify
  `temperature_unit` ("C" or "K"); values must be converted to Celsius before
  solving. Temperature differences are interpreted in kelvin-equivalent units.
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

Some qualification setups also exchange radiation between the right surface and
nearby surroundings. The radiative film is in parallel with the convective film,
but the surrounding radiation temperature may differ from the ambient fluid
temperature. Use the Stefan-Boltzmann linearization for a surface-temperature
estimate `T_s` and surrounding temperature `T_sur`, both in kelvin:

```text
h_rad = emissivity * view_factor * sigma * (T_s + T_sur) * (T_s^2 + T_sur^2)
```

Then combine the two surface films as:

```text
h_total = h_conv + h_rad
T_reference = (h_conv * T_inf + h_rad * T_sur) / h_total
```

The approved report requires the final right-surface temperature used for
`h_rad` to be consistent with the heat flux produced by the linearized solve.
Zero-emissivity cases reduce to convection only.

## Calibration Guidance

Use `/app/data/calibration_cases.json` and `/app/data/approved_outputs.json` to
calibrate the implementation. The cases exercise single-layer conduction,
volumetric heating, material contrast, contact temperature drops, and convection
sensitivity. Some visible cases only probe the presence of optional schema
fields; a repair that only matches those case IDs without implementing the
general model will fail hidden qualification cases.
