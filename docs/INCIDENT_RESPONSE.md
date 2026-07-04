# Incident response and disaster recovery

## Severity

- **SEV-1:** data breach, unsafe widespread advice, unavailable production, or
  corrupted primary database.
- **SEV-2:** elevated errors, broken core feature, model drift alert, or failed
  backups.
- **SEV-3:** limited UI defect or non-critical integration failure.

## Immediate actions

1. Assign an incident commander and open a timestamped incident record.
2. Protect users: disable the affected feature or roll back; do not guess.
3. Preserve privacy-safe logs, deployment IDs, model checksum and metrics.
4. For advice/model incidents, display a service notice and route uncertain
   cases to human review.
5. For credential exposure, rotate secrets, revoke sessions and audit access.
6. Communicate status without publishing personal data or exploitable details.

## Recovery

- Roll back Vercel to the last verified production deployment.
- Roll back Railway to the last verified image and model checksum.
- Restore PostgreSQL only into a disposable environment first.
- Compare row counts, constraints and core workflows before production cutover.
- Verify Redis, SMTP, weather, OpenAI, uploads and metrics after recovery.

## Completion

Document cause, user impact, detection gap, timeline, corrective actions,
owners and deadlines. Run a blameless review within five working days and add a
regression test or alert for the failure mode.
