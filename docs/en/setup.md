# Lab setup

> Language: [Українською](../ua/setup.md) · **English**

## Prerequisites
- `git`, `python3` (for `pre-commit`).
- Optional: `trivy`, `gitleaks` for local scans.

## Steps
1. Clone the repository and `cd` into it.
2. Install checks: `bash scripts/setup.sh` (installs `pre-commit` and git hooks).
3. If needed, copy `.env.example` → `.env` and fill it in **locally** (not committed).
4. Verify before committing: `pre-commit run --all-files`.
5. Local security: `bash scripts/security-check.sh`.

## Next
- Conventions — [`guidelines.md`](guidelines.md).
- Working with AI — [`ai-integration.md`](ai-integration.md).
- Methodology — [`../methodology.md`](../methodology.md); plan — [`../PLAN.md`](../PLAN.md).
