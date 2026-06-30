# Findings: Hidden-Resonance SysID Boundary Analysis

Date: 2026-06-30

## Context

This repository contains the hidden-resonance system-identification TB3 candidate. The task explored a verifier-owned oracle pattern, private deterministic instances, strict model schema validation, and held-out zero-state evaluation.

## What worked

- The architecture spike validated the verifier-owned oracle pattern.
- Trusted oracle restoration worked.
- Static exfiltration checks passed.
- Nop failed.
- Reference/oracle passed.
- Brute/slow baseline failed by timeout.
- Schema validation rejected malformed, unstable, oversized, and non-finite models.

## Boundary-sweep finding

After the initial validation, stronger non-strawman boundary sweeps showed that the core difficulty separation was weaker than intended.

For a noise-free deterministic LTI system:

1. Public-only fitting can recover the hidden mode if model order is high enough.
2. Short-horizon broadband probing can identify the system and extrapolate the held-out tail.
3. The main difficulty boundary is model order, not true hidden discovery.

The key reason is mathematical: exact noise-free LTI data is fully determining. Once the system is identified, tail prediction is computationally cheap.

## Why this matters

The intended mechanism was:

- public data underdetermines the hidden resonance;
- early oracle access prevents direct tail replay;
- naive replay/extrapolation fails;
- only active discovery under budget succeeds.

The stronger sweeps showed that this mechanism does not hold strongly enough in the noise-free LTI setting. The sysid task is fair and informative, but it is not strong enough for the strict all-fail target.

## Engineering conclusion

The difficulty needs to move to a domain where hard work remains after the hidden parameter is known.

The better next direction is a ks-solver-style transient thermal PDE task:

- manufactured exact PDE truth;
- hidden temporal scale exposed only through oracle behavior;
- stiff or precision-sensitive numerical solve;
- tight tolerance over many hidden points;
- verifier wall-clock budget preventing brute force;
- obvious fixed-dt/coarse solver silently wrong;
- trusted oracle restored at verification time.

## Status

This is a post-analysis documentation note. It preserves the submitted sysid task and records why I pivoted rather than silently rewriting the repository.
