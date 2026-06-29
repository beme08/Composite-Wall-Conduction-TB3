# Stage 2: Fixed-point convergence for contact resistance

## Finding
`gatekeeper-codex-tempcontact-2` solves all 15 hidden cases (including h012–h015) at tolerance < 1e-9. The agent correctly implements the two-pass temperature correction. Adding more hidden cases within the current model will not reduce pass-rate.

## Proposal
Replace the exact two-pass temperature correction with **documented fixed-point convergence**:

### Algorithm change
```
1. Age-correct contacts (as before)
2. For up to N iterations (N=10):
   a. Build mesh with current contact resistances
   b. Solve direct linear system
   c. For each temp-dependent contact, compute T_eval from interface diagnostics
   d. Recompute R_eff = R_aged * (1 + coeff * (T_eval - T_ref))
   e. If |R_new - R_old| / R_old < tolerance (1e-6), stop
3. Report final solution
```

### Files to change
- `instruction.md`: Document fixed-point algorithm, max iterations (10), convergence tolerance (1e-6)
- `reference_solver.py`: Implement fixed-point loop instead of two-pass
- `solve.sh` (oracle): Same change
- `approved_outputs.json`: Regenerate
- `calibration_cases.json`: Possibly update if model change affects results

### No changes needed
- `materials_db.csv`
- `hidden_cases.json` (already has 15 cases)
- `engineering_notes.md`
- README/SUMMARY/docs

### Validation gate
1. oracle=1.0 (calibration + hidden)
2. nop=0.0
3. Replay tempcontact-2 artifact
4. If artifact gets 0.0 → run 3 fresh Codex trials
5. If still 1.0 → hardened model is still within agent capability; discuss alternative direction

## Why fixed-point is fairer than two-pass
- Two-pass is arbitrary: why exactly 2 passes and not 3?
- Fixed-point is the natural convergence criterion
- Agents must implement an iterative loop instead of a hardcoded two-step
- Still deterministic (direct solve per iteration, no nonlinear solver)
- Documented upfront in instruction.md — no hidden trap
