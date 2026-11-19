# Scripts

Only scripts in this folder (and workflows that call them) are part of the practice allowlist.

## Rules

- Human or `workflow_dispatch` decides **when** to run.
- GitHub Actions runner executes **what** is in this repo.
- No long-lived AWS keys in the repo. Prefer OIDC later.
