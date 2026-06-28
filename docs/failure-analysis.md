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

The final public task removes the direct implementation formulas from
`instruction.md`. The intended model remains recoverable from public calibration
cases, approved outputs, engineering notes, unit conventions, existing code
structure, and physical invariants, while the hidden verifier checks
generalization.

## Trial outcomes

Standard agent trials are locally complete:

- **Codex (openai/gpt-5.5, extra-high reasoning):** 3/3 valid failures, reward 0.0.
- **Claude Code (anthropic/claude-opus-4-8, max effort):** 3/3 valid failures, reward 0.0.
- **Codex local cheat reproduction:** reward 0.0, no bypass found.
- **Claude Code local cheat reproduction:** reward 0.0, no bypass found.

All valid agents failed at hidden verifier correctness. All six standard runs
exited cleanly (`exception_info: null`), and trajectory grep found no evidence
of hidden-fixture, solution, verifier, reward-file, or base64 shortcut access.

## Likely failure mode

The exact hidden-case mismatch is not observable from public artifacts. The
most plausible explanation is incomplete recovery of the coupled calibration
model. A correct repair must simultaneously satisfy:

- Material normalization (temperature-dependent conductivity, Kelvin reference,
  calibration offsets).
- Contact aging (date parsing, locale-aware format detection, service-age
  calculation).
- Half-cell boundary conductance at the left fixed-temperature face.
- Series internal face resistance with optional contact resistance.
- Right convective boundary with film coefficient.
- Volumetric source scaling and sign convention.
- Interface-side temperature extrapolation and diagnostics.
- Energy residual closure.

The calibration cases exercise these features in isolation and combination,
but a repair that matches calibration may still fail on hidden cases that
stress interactions the agent did not fully correct. The partial-fix audit
confirms that each of the eight planted bugs must be corrected for the
full reward — a single missed bug is sufficient to fail.

## Task-design rationale

The task is designed so that calibration-driven repair is necessary but not
sufficient. Public calibration cases and approved outputs let agents
self-check during development. Hidden generalization cases, schema strictness,
and the eight-bug partial-fix audit ensure that only a complete, principled
repair receives the reward. This design prevents agents from patching
calibration-specific symptoms while leaving the underlying model broken.
