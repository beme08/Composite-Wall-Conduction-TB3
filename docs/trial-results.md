# Trial Results — thermal-stack-calibration

## Current status

- Task implemented under `tasks/thermal-stack-calibration`
- Oracle validation: passes
- Nop validation: passes
- Docker oracle/nop: passes
- Public calibration artifacts fixed for consistency
- One post-fix Codex gatekeeper run: reward **0.0**
- One post-fix Claude run: API rate-limit exception (not counted as a valid model trial)
- Full 3× Codex + 3× Claude standard run matrix and cheat trials: **not run**

## v1.1 (tag `thermal-contact-stack-v1.1-claude-pass`)

### Claude Code — 1/1 pass (but task too easy)

| Run | Reward | Exceptions | CTRF | Notes |
|-----|--------|------------|------|-------|
| 1/1 | 1.0 | 0 | — | 35m12s total. Legitimate model pass. Trace review: no evidence of hidden fixture, solution, reference solver, reward, or test access. Agent wrote independent verifier in `/tmp` from public instruction and repaired app source files. |

**Conclusion:** thermal-contact-stack v1.1 is valid but not compliant with the
strict all-run-fail requirement for a hardened benchmark. Both frontier models
solved it, indicating the task was easier than intended.

### Post-hardening (v2 calibration)

| Run | Reward | Exceptions | CTRF | Notes |
|-----|--------|------------|------|-------|
| Codex gatekeeper | **0.0** | 0 | — | Post-hardening, expected hard mode |
| Claude | — | API rate-limit | — | Not counted as a valid model failure |
