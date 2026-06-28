# Failure Analysis

The inherited solver produces plausible thermal-stack qualification outputs but
violates the approved model in several independent ways.

The hidden cases exercise:

- Single-layer convection, with and without volumetric generation.
- Two-layer no-contact stacks with high and reversed conductivity contrast.
- High internal contact resistance.
- A high-k-contrast contact entanglement case.
- Three-layer stacks with two contact interfaces.
- Source generation only left of contact, only right of contact, and on both
  sides.
- Strong convection and weak-convection/fine-mesh regimes.

The partial-fix audit confirms that the all-buggy state fails, the all-fixed
state passes, every single-fix-alone state fails, every all-but-one state fails,
and only the full eight-fix state receives reward.

The v2 public task removes the direct implementation formulas from
`instruction.md`. The intended model remains recoverable from public calibration
cases, approved outputs, engineering notes, unit conventions, existing code
structure, and physical invariants, while the hidden verifier checks
generalization.
