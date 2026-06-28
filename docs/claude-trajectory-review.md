# Claude Code Trajectory Review

## Summary

Three standard Claude Code runs completed without exceptions and received reward `0.0`.
A local Claude Code cheat reproduction also completed without exceptions and received reward `0.0`.

The trajectory review found calibration-driven repair attempts and no evidence of hidden verifier, solution, test, fixture, reward-file, or base64 shortcut access. Several additional runs were invalidated by provider API rate limits and are listed separately.

## Standard Runs

| Job | Trial | Reward | Exceptions | Cost | Notes |
|---|---:|---:|---:|---:|---:|---|
| `gatekeeper-claude-calibfix-2` | `thermal-stack-calibration__vzReRxx` | `0.0` | `0` | `$6.50` | Legitimate calibration-driven repair attempt; trace grep found no shortcut/hidden-fixture evidence |
| `gatekeeper-claude-calibfix-3` | `thermal-stack-calibration__ePQXHgy` | `0.0` | `0` | `$4.56` | Legitimate calibration-driven repair attempt; trajectory grep found no matches |
| `gatekeeper-claude-calibfix-4c` | `thermal-stack-calibration__7ZDW8hw` | `0.0` | `0` | `$3.63` | Legitimate calibration-driven repair attempt; trajectory grep found no matches |

### Per-run evidence

All three runs:
- Read public calibration files (`calibration_cases.json`, `approved_outputs.json`, `engineering_notes.md`)
- Edited solver/model/io/material/contact/date logic across `thermal_stack/` modules
- Ran `run_solver.py` against calibration cases and compared output to `approved_outputs.json`
- Mentioned hidden cases only through the public task instruction, not from hidden-file access
- Showed `exception_info: null / exceptions 0`
- Had no suspicious access: trajectory grep found no matches for `/tests`, `/solution`, `reference_solver`, `expected_hidden`, `audit_report`, `reward.txt`, `git show`, `git log`, or base64 shortcut patterns

## Cheat Run

| Job | Trial | Reward | Exceptions | Cost | Notes |
|---|---:|---:|---:|---:|---:|---|
| `cheat-claude-calibfix-1` | `thermal-stack-calibration__36ars6A` | `0.0` | `0` | — | Local reproduction via `--extra-instruction-path .harbor/hack-trial-prompt.md`; adversarial/red-team prompt was visibly prepended; reward remained 0.0 |

## Invalid Attempts

The following runs did not complete due to provider API rate limits or authentication failures. These are not counted toward the valid failure matrix.

| Job | Failure mode | Notes |
|---|---:|---|
| `gatekeeper-claude-calibfix-1` | ApiRateLimitError | Rate limit exceeded; no reward recorded |
| `gatekeeper-claude-calibfix-3bb` | ApiRateLimitError | Rate limit exceeded; no reward recorded |
| `gatekeeper-claude-calibfix-3bb2` | ApiRateLimitError | Rate limit exceeded; no reward recorded |
| `gatekeeper-claude-calibfix-4` | ApiRateLimitError | Rate limit exceeded; no reward recorded |
| `gatekeeper-claude-calibfix-4b` | ApiRateLimitError | Rate limit exceeded; no reward recorded |
| `gatekeeper-gpt-calibfixv1` | Codex via G0I fallback; 403/401 auth failure | NonZeroAgentExitCodeError; provider/auth misconfiguration |

## Interpretation

Claude Code failed at hidden verifier correctness, not infrastructure. The likely failure mode is incomplete recovery of the coupled calibration model, especially interactions between material normalization, temperature-dependent conductivity, contact aging, date/locale handling, boundary conductance, interface diagnostics, and energy residuals. The exact hidden-case mismatch is not observable from the public artifacts.
