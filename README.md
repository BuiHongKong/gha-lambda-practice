# gha-lambda-practice

Public practice repo: **GitHub Actions** + **AWS Lambda** + **allowlisted script execution**.

Personal account bootstrap — no org required.

## What's in here

| Path | Purpose |
|------|---------|
| `lambda/images/` | Lambda that stores an image in S3 and its key in RDS |
| `scripts/` | Allowlisted scripts for Actions |
| `.github/workflows/ci.yml` | Prove changes on push/PR |
| `.github/workflows/run-script.yml` | Manual `workflow_dispatch` script run |
| `.github/workflows/deploy-lambda.yml` | Stub until AWS OIDC is wired |

## Mindset this repo practices

- Git is the allowlist of what may run
- Humans decide **when**; Actions decide **how** (from this repo only)
- CI proves artifacts; deploy is a separate gated step
- No long-lived cloud keys in git — OIDC/IAM roles next

## Quick start (local)

```bash
python scripts/hello.py --name local
python -m py_compile lambda/images/handler.py
```

## Security check

| Item | Status |
|------|--------|
| Where secrets live | GitHub Environment / OIDC role (not yet wired) |
| Who can access | Repo collaborators + Actions permissions |
| Rotation / revoke | Remove GitHub env secrets / IAM role trust |
| Committed to git | **No** real secrets — placeholders only |

## Next (later)

1. AWS IAM OIDC provider trusted to this repo
2. Package + deploy `lambda/images`
3. Optional EventBridge schedule → Lambda
4. Harden `run-script` with environment approvals
