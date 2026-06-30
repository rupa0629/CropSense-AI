# Vercel + Railway deployment

The React/Vite frontend runs on Vercel. FastAPI, TensorFlow, SQLite, and Redis
run on Railway. The browser calls Railway directly so image uploads do not pass
through Vercel's function request-size limit.

## 1. Railway backend

1. Create a Railway project from the GitHub repository.
2. Create a service from the repository. Railway detects the root `Dockerfile`
   and `railway.json`.
3. Add a Railway Redis database named `Redis`.
4. Add a volume to the backend service mounted at `/app/data`. Keep one backend
   replica because SQLite is a single-node database.
5. In the backend Variables tab, copy the keys from `.env.railway.example`.
   Generate secret values rather than copying the blank placeholders.
6. For Redis variables, use Railway reference values:
   `${{Redis.REDISHOST}}`, `${{Redis.REDISPORT}}`, and
   `${{Redis.REDISPASSWORD}}`.
7. Generate a public Railway domain. Put its hostname in `ALLOWED_HOSTS`,
   alongside `healthcheck.railway.app`, `127.0.0.1`, and `localhost`.
8. Initially set `FRONTEND_ORIGINS` and `FRONTEND_URL` to the expected Vercel
   project URL. Update them after Vercel creates the final URL.
9. Deploy and verify `https://YOUR-API/health/ready`.

The attached volume causes a short deployment interruption by design; Railway
does not overlap volume-mounted deployments.

## 2. Vercel frontend

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Vercel detects Vite; `frontend/vercel.json` also pins the build and SPA
   routing configuration.
4. Add `VITE_API_BASE=https://YOUR-API.up.railway.app` to both Production and
   Preview environment variables.
5. Deploy.
6. Copy the final Vercel URL back into Railway's `FRONTEND_ORIGINS` and
   `FRONTEND_URL`, then redeploy the backend.

## 3. Final checks

- Register and log in from the Vercel URL.
- Upload a valid leaf image and confirm prediction succeeds.
- Confirm invalid uploads are rejected.
- Test weather, chatbot, logout, refresh, and password reset.
- Confirm `https://YOUR-API/metrics/` returns 401 without `X-Metrics-Token`.
- Configure Railway volume backups and an external uptime monitor.
