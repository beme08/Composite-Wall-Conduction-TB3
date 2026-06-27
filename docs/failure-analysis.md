# Failure Analysis

The inherited solver produces plausible thermal-stack outputs but violates
contact-resistance finite-volume physics in several independent ways.

The hidden cases exercise:

- Single-layer convection, with and without volumetric generation.
- Two-layer no-contact stacks with high and reversed conductivity contrast.
- Low and high internal contact resistance.
- Three-layer stacks with two contact interfaces.
- Source generation only left of contact, only right of contact, and on both sides.
- Strong convection and weak-convection/fine-mesh regimes.

The partial-fix audit confirms that the all-buggy state fails, the all-fixed
state passes, every single-fix-alone state fails, every all-but-one state fails,
and only the full eight-fix state receives reward.
