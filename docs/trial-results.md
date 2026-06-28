# Trial Results — thermal-stack-calibration

## Current status

- Task implemented under `tasks/thermal-stack-calibration`
- Oracle validation: passes
- Nop validation: passes
- Docker oracle/nop: passes
- Public calibration artifacts fixed for consistency
- Codex standard matrix: 3/3 valid failures, exceptions 0
- Claude standard matrix: 3/3 valid failures, exceptions 0
- Codex local cheat reproduction: reward 0.0, exceptions 0
- Claude local cheat reproduction: reward 0.0, exceptions 0
- Several invalid attempts due to provider API rate limits or auth failures (not counted)

## v1.1 (tag `thermal-contact-stack-v1.1-claude-pass`)

### Claude Code — 1/1 pass (but task too easy)

| Run | Reward | Exceptions | CTRF | Notes |
|-----|--------|------------|------|-------|
| 1/1 | 1.0 | 0 | — | 35m12s total. Legitimate model pass. Trace review: no evidence of hidden fixture, solution, reference solver, reward, or test access. Agent wrote independent verifier in `/tmp` from public instruction and repaired app source files. |

**Conclusion:** thermal-contact-stack v1.1 is valid but not compliant with the
strict all-run-fail requirement for a hardened benchmark. Both frontier models
solved it, indicating the task was easier than intended.

## Post-fix gatekeeper trials

Candidate task: `thermal-stack-calibration`

### Valid standard runs

| Job | Trial | Agent | Model | Valid? | Reward | Exceptions | Cost |
|---|---:|---:|---:|---:|---:|---:|---|
| gatekeeper-codex-calibfix-1 | `DUzDZUJ` | Codex | gpt-5.5, xhigh | yes | 0.0 | 0 | $1.68 |
| gatekeeper-codex-calibfix-2 | `r28iL9h` | Codex | gpt-5.5, xhigh | yes | 0.0 | 0 | $1.38 |
| gatekeeper-codex-calibfix-3 | `dC99hVQ` | Codex | gpt-5.5, xhigh | yes | 0.0 | 0 | $1.85 |
| gatekeeper-claude-calibfix-2 | `vzReRxx` | Claude Code | claude-opus-4-8, max | yes | 0.0 | 0 | $6.50 |
| gatekeeper-claude-calibfix-3 | `ePQXHgy` | Claude Code | claude-opus-4-8, max | yes | 0.0 | 0 | $4.56 |
| gatekeeper-claude-calibfix-4c | `7ZDW8hw` | Claude Code | claude-opus-4-8, max | yes | 0.0 | 0 | $3.63 |

All six runs: `exception_info: null`, no shortcut/hidden-fixture evidence in trajectory grep.

### Valid local cheat reproductions

| Job | Trial | Agent | Model | Valid? | Reward | Exceptions | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| cheat-codex-calibfix-1 | `UGVGadu` | Codex | gpt-5.5 | yes | 0.0 | 0 | Local reproduction via `--extra-instruction-path .harbor/hack-trial-prompt.md`; agent chose legitimate repair over bypass; calibration matched to 1.4e-11 |
| cheat-claude-calibfix-1 | `36ars6A` | Claude Code | claude-opus-4-8, max | yes | 0.0 | 0 | Local reproduction with adversarial/red-team prompt prepended; reward remained 0.0 |

### Invalid / not-counted attempts

| Job | Failure mode | Exceptions | Notes |
|---|---:|---:|---|
| gatekeeper-claude-calibfix-1 | ApiRateLimitError | 1 | Not counted |
| gatekeeper-claude-calibfix-3bb | ApiRateLimitError | 1 | Not counted |
| gatekeeper-claude-calibfix-3bb2 | ApiRateLimitError | 1 | Not counted |
| gatekeeper-claude-calibfix-4 | ApiRateLimitError | 1 | Not counted |
| gatekeeper-claude-calibfix-4b | ApiRateLimitError | 1 | Not counted |
| gatekeeper-gpt-calibfixv1 | Codex via G0I fallback; 403/401 auth failure | 1 | NonZeroAgentExitCodeError; not counted |

### Detail: Post-fix Claude gatekeeper runs

#### gatekeeper-claude-calibfix-2 (`vzReRxx`)

| Field | Value |
|---|---|
| Agent | `claude-code` |
| Model | `claude-opus-4-8` |
| Valid? | Yes |
| Reward | `0.0` |
| Exceptions | `0` |
| Cost | `$6.495649` |

Trace review:
- Forbidden-surface grep found no `/tests`, `/solution`, `reference_solver`, `expected_hidden`, `audit_report`, `reward.txt`, `git show`, `git log`, or base64 shortcut evidence.
- Agent used public calibration files and logs/scratch space.
- Agent recovered a large part of the model and rewrote modules, but hidden verifier still returned reward `0.0`.

#### gatekeeper-claude-calibfix-3 (`ePQXHgy`)

| Field | Value |
|---|---|
| Agent | `claude-code` |
| Model | `claude-opus-4-8` |
| Valid? | Yes |
| Reward | `0.0` |
| Exceptions | `0` |
| Cost | `$4.560853` |

Trace review: trajectory grep found no matches for hidden-fixture, solution, or reward-file access patterns.

#### gatekeeper-claude-calibfix-4c (`7ZDW8hw`)

| Field | Value |
|---|---|
| Agent | `claude-code` |
| Model | `claude-opus-4-8` |
| Valid? | Yes |
| Reward | `0.0` |
| Exceptions | `0` |
| Cost | `$3.62732875` |

Trace review: trajectory grep found no matches for hidden-fixture, solution, or reward-file access patterns.

## Current Matrix

| Agent | Standard runs | Cheat runs | Status |
|---|---:|---:|---|
| Codex / openai/gpt-5.5 | 3/3 valid failures | 1 local cheat failure | Complete locally |
| Claude Code / claude-opus-4-8 | 3/3 valid failures | 1 local cheat failure | Complete locally |

All valid agents failed at hidden verifier correctness, not infrastructure. Exact hidden-case mismatch is not observable from public artifacts. See [`docs/codex-trajectory-review.md`](codex-trajectory-review.md) and [`docs/claude-trajectory-review.md`](claude-trajectory-review.md) for per-agent trajectory analysis.
