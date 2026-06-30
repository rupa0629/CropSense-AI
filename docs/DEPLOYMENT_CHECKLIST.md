# Production deployment checklist

## Required inputs

- [ ] Public `DOMAIN` resolves to the server
- [ ] Ports 80 and 443 are open
- [ ] `.env` created from `.env.production.example`
- [ ] 64+ character `JWT_SECRET`
- [ ] Unique Redis password and metrics token
- [ ] OpenAI and OpenWeather keys
- [ ] Working SMTP credentials and verified sender
- [ ] `.env` excluded from source control and readable only by the operator

## Automated gates

- [ ] `python scripts/production_preflight.py`
- [ ] `python -m pytest -q`
- [ ] `npm run test -- --run`
- [ ] `npm run build`
- [ ] `docker compose --env-file .env -f docker-compose.prod.yml config --quiet`
- [ ] Production images build successfully
- [ ] Images pass the chosen vulnerability scanner

## Runtime verification

- [ ] HTTPS certificate is valid and HTTP redirects to HTTPS
- [ ] `/api/health` and `/api/health/ready` return 200
- [ ] Register, login, refresh, logout, and password reset work
- [ ] Valid leaf upload predicts; invalid and oversized uploads are rejected
- [ ] Weather and chatbot integrations work
- [ ] Rate limiting returns 429 at the configured threshold
- [ ] `/api/metrics/` rejects missing/incorrect metrics tokens
- [ ] Backend and Redis are not reachable from public host ports

## Operations

- [ ] Daily database backups copied off-host
- [ ] Restore drill completed
- [ ] Uptime, error-rate, latency, disk, and backup-age alerts configured
- [ ] Log retention and aggregation configured
- [ ] Named release tag deployed
- [ ] Rollback command and responsible operator documented
- [ ] Load test completed against staging
