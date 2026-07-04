# Staging, release and rollback

## Environments

- `main` deploys production only after CI, CodeQL and container scanning pass.
- Pull requests create Vercel previews and should use a separate Railway staging
  API, PostgreSQL database, Redis instance, SMTP sandbox and API keys.
- Never point a preview frontend at production.

Protect the GitHub `production` environment with required reviewers. Keep
provider tokens in environment-scoped secrets.

## Release gate

1. Backend unit/integration/security tests pass.
2. Frontend unit, desktop and mobile browser tests pass.
3. Container and dependency scans contain no unaccepted critical/high issue.
4. Alembic migration succeeds on a restored staging backup.
5. Model checksum matches an approved agronomist release record.
6. Staging smoke and load tests pass.
7. Backup age and restore rehearsal are within policy.
8. A named operator and rollback deployment IDs are recorded.

## Rollback

If production health, errors, latency or safety checks fail:

1. Stop promotion and disable the affected feature if necessary.
2. Promote the prior verified Vercel deployment.
3. Redeploy the prior verified Railway image/model checksum.
4. Do not downgrade a database blindly. Use a tested forward fix unless the
   migration has a verified data-preserving downgrade.
5. Verify health, login, upload, prediction, weather, feedback and metrics.
6. Open an incident record and preserve privacy-safe evidence.

Run staging load smoke:

```powershell
python scripts/load_test.py https://STAGING-API/health/ready --requests 500 --concurrency 20
```
