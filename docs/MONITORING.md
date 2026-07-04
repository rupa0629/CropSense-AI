# Monitoring and privacy-safe alerts

Production exposes token-protected Prometheus metrics at `/metrics/` and can
send unhandled exceptions to Sentry when `SENTRY_DSN` is configured.

Sentry is initialized with `send_default_pii=False`. Do not add uploaded image
bytes, chat contents, email addresses, access tokens, reset tokens, exact GPS
coordinates, or request bodies to logs or error tags.

Import `observability/prometheus-alerts.yml` into the chosen Prometheus/Alertmanager
provider. Route critical alerts to at least two maintainers.

Monitor:

- uptime, request count, 5xx rate and p95 latency;
- inference latency, confidence distribution and uncertain-prediction rate;
- predicted class distribution compared with the approved validation baseline;
- PostgreSQL connections, storage, backup age and failed migrations;
- Redis availability and rate-limit failures;
- Vercel Core Web Vitals and frontend JavaScript errors.

Investigate distribution changes before calling them drift: season, geography,
new users and a changed camera population can all shift inputs. Retraining
requires a newly labelled, independently tested and agronomist-approved dataset.
