# Production deployment

CropSense deploys as four containers: Caddy (automatic HTTPS), the React
frontend, the FastAPI/TensorFlow backend, and Redis. SQLite is the only
supported application database and is persisted in the `backend-data` volume.
Run one backend replica.

## 1. Prerequisites

- A Linux server with 4 GB RAM, 2 CPU cores, and 20 GB free disk
- Docker Engine with the Compose v2 plugin
- A public DNS `A`/`AAAA` record pointing `DOMAIN` at the server
- Inbound TCP ports 80 and 443
- OpenAI, OpenWeather, and SMTP credentials

On Windows, install Docker Desktop and enable its WSL 2 backend. Production
should run on a Linux host rather than a developer workstation.

## 2. Configure

```bash
cp .env.production.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Fill every blank value in `.env`. Never commit that file. `DOMAIN` must be the
public hostname without `https://`. Caddy obtains and renews its TLS
certificate automatically.

Validate interpolated configuration without printing secrets:

```bash
docker compose --env-file .env -f docker-compose.prod.yml config --quiet
python scripts/production_preflight.py
```

## 3. Test and deploy

```bash
python -m pytest -q
cd frontend && npm ci && npm run test -- --run && npm run build && cd ..
docker compose --env-file .env -f docker-compose.prod.yml build
docker compose --env-file .env -f docker-compose.prod.yml up -d
docker compose --env-file .env -f docker-compose.prod.yml ps
```

Verify:

```bash
curl -fsS "https://${DOMAIN}/api/health"
curl -fsS "https://${DOMAIN}/api/health/ready"
```

The backend and Redis have no host ports. Only Caddy publishes ports 80/443.

## 4. Backups

Create a consistent backup from the backend volume:

```bash
docker compose --env-file .env -f docker-compose.prod.yml exec backend \
  python scripts/backup_database.py --output /app/data/backups --retain 14
```

Copy backups off the server or into object storage. Schedule this command at
least daily and test restoration quarterly.

Restore only while the backend is stopped:

```bash
docker compose --env-file .env -f docker-compose.prod.yml stop backend
docker compose --env-file .env -f docker-compose.prod.yml run --rm backend \
  python scripts/restore_database.py /app/data/backups/BACKUP.db --confirm
docker compose --env-file .env -f docker-compose.prod.yml start backend
```

## 5. Monitoring

- Scrape `/api/metrics/` with the `X-Metrics-Token` header.
- Alert on readiness failures, HTTP 5xx rate, latency, disk space, and backup age.
- Ship Docker JSON logs to the chosen log platform.
- Configure an external HTTPS uptime probe for `/api/health/ready`.

## 6. Upgrade and rollback

Tag every release; do not deploy `latest` permanently.

```bash
IMAGE_TAG=2026.06.30 docker compose --env-file .env -f docker-compose.prod.yml build
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

Before upgrades, take a backup. To roll back, restore the previous `IMAGE_TAG`
and run `up -d`. Restore the database only when the release changed its schema
and the rollback procedure explicitly requires it.
