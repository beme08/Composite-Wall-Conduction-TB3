# Engineering Notes

The plant is a deterministic, noise-free, single-input single-output LTI system.
The public records are deliberately low-rate records over the oracle probing
horizon. They are useful for conventions and signal scale, but they do not pin
down the full transfer function.

The hidden verification instances include a lightly damped resonant mode. That
mode has little DC contribution, so low-frequency fits can look plausible, but
it dominates later tail responses after faster modes decay. A successful
solution should therefore probe the verifier-time oracle with broadband input,
estimate a sufficient-order stable model, and propagate that model to the
unqueried tail.

The oracle returns only forced responses from zero state for `N * dt <= 2.0`.
The verifier scores forced responses from zero state at later times. This makes
the task realization-invariant: any equivalent state-space realization is valid
if it predicts the transfer-function response.
