# Summary

This repo has the final original task, validation notes, trial results, trajectory review, and failure analysis.
I followed the TB3/Harbor contribution and review docs closely and documented the relevant checks and evaluation runs in the repository.

Summary of final local evidence:
- Oracle validation: passed
- Nop validation: passed
- Docker validation: passed
- Codex standard trials: 3/3 valid failures, reward 0.0, exceptions 0
- Claude Code standard trials: 3/3 valid failures, reward 0.0, exceptions 0
- Codex adversarial trial using the TB3 hack-trial prompt: reward 0.0, exceptions 0
- Claude Code adversarial trial using the TB3 hack-trial prompt: reward 0.0, exceptions 0

Adversarial trials were run locally using Harbor's `--extra-instruction-path` with the upstream TB3 hack-trial prompt,
matching the behavior of the `/cheat` review workflow without requiring a PR.
