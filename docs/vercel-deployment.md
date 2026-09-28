# Vercel deployment

Poorvabhas uses one Vercel project with two [Services](https://vercel.com/docs/services). The project root is the repository root. `frontend/` builds as Next.js, and `backend/` builds with Vercel's native FastAPI/Python runtime using `app.main:app`. Root `vercel.json` sends `/api/*` to FastAPI and all other requests to Next.js. The backend receives the original `/api/...` path. The browser requests same-origin `/api/...` when `NEXT_PUBLIC_API_URL=/api`. Do not set a Vercel project Root Directory of `frontend` or `backend`.

Production: **https://poorvabhas.vercel.app** (Next.js and FastAPI on Vercel) with **Neon PostgreSQL** (pgvector enabled). Vercel is the only production deployment. Docker Compose remains for local development only.

```
Browser -> https://poorvabhas.vercel.app -> Next.js (frontend service)
                                  /api/*  -> FastAPI (backend service) -> Neon PostgreSQL (pgvector + model artifacts)
```

## Database (Neon)

The production database is a Neon project (branch `production`, database `neondb`). `postgres://` and `postgresql://` URLs are normalized to the installed psycopg 3 driver. With `VECTOR_BACKEND=auto`, `embeddings.vector` is a pgvector `vector(64)` column. On Vercel, the first request in each function instance binds the ORM column to pgvector (`db.configure_vector_column`, once per process). This step creates no tables and writes no rows.

The production database is already initialized with 3 demo users, 280 synthetic reports with analyses and embeddings, 19 mined patterns, and 2 model artifacts (classifier and embedder) stored in PostgreSQL. Do **not** rerun or reset it. A rerun of the initializer against a database that already has reports skips the dataset seed and only restores missing model artifacts.

To initialize a **new, empty** Neon branch, back it up, then run the initializer once from a trusted machine. It creates missing tables, the demo users and the synthetic dataset, then trains the models, stores them in PostgreSQL and mines patterns in a single transaction. If the transaction fails, nothing is committed and it is safe to rerun. Two lessons from the production run:

- Use Neon's **direct** connection string (connection pooling off) for the initializer. The seed holds one transaction open while it analyzes every report, which is tens of minutes over a long-distance link. A run through the pooled endpoint lost its connection and rolled back.
- The generator always adds 5 fixed demo cases (`SYN-DEMO-001…005`) to `SEED_REPORTS` random reports. `SEED_REPORTS=275` gives the 280 reports used in production.

Never pass `--reset` against production: it drops every table.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Copy Neon's direct (non-pooled) connection string to the clipboard; it is never typed or echoed.
$env:DATABASE_URL = (Get-Clipboard -Raw).Trim(); Set-Clipboard -Value ' '
$env:SECRET_KEY = '<same production secret configured in Vercel>'
$env:ENVIRONMENT = 'production'
$env:AUTO_SEED = 'false'
$env:DEMO_MODE = 'true'
$env:SEED_REPORTS = '275'
$env:VECTOR_BACKEND = 'auto'
try { .\.venv\Scripts\python.exe -u -m app.seed.seed } finally { Remove-Item Env:\DATABASE_URL, Env:\SECRET_KEY }
```

The initializer takes much longer than a normal HTTP request. Run it from this local CLI, never in a Vercel Function. Do not use the development demo credentials for real safety data. If the database is empty and `DEMO_MODE=true`, the initializer creates the demo users and synthetic reports. On a database that already has reports, it keeps the user accounts and current data.

## Vercel project settings

Connect `Rahul-Baghel01/Poorvabhas`, production branch `main`, with Root Directory `./` (repository root) and Framework Preset **Services** under Project Settings > Build and Deployment. Both settings are required for Vercel to read the root `vercel.json` and build its two services. Ensure the deployed Git commit contains that file. Do not override the build command or the two service roots in `vercel.json`. Set these environment variables in Vercel's dashboard for Production and any Preview deployment that should access a database:

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `/api` |
| `API_URL` | `/api` |
| `DATABASE_URL` | Neon PostgreSQL connection string (`sslmode=require`). Keep it secret. |
| `SECRET_KEY` | A long random value; use the same value during initialization and across deployments so sessions remain valid. Keep it secret. |
| `ENVIRONMENT` | `production` |
| `COOKIE_SECURE` | `true` |
| `AUTO_SEED` | `false` (the Vercel runtime skips startup seeding regardless) |
| `DEMO_MODE` | `true` for the synthetic demo database; `false` only when configured for non-demo use |
| `SEED_REPORTS` | `280` if initializing an empty synthetic demo database; unused on normal requests |
| `VECTOR_BACKEND` | `auto` (uses pgvector on Neon; `json` only for a database without pgvector) |
| `CORS_ORIGINS` | `https://poorvabhas.vercel.app` (inert on Vercel: requests are same-origin and CORS middleware is only added outside Vercel) |
| `USE_TRANSFORMER` | `false` unless the optional transformer dependencies and local model are deployed separately |
| `MODEL_PATH` | `/tmp/poorvabhas-models` (optional; this is the Vercel default) |

`NEXT_PUBLIC_API_URL=/api` keeps browser calls on the Vercel domain. `API_URL=/api` matches the Vercel project setting; the Next.js proxy is disabled when `VERCEL` is set, so Vercel Services handles these requests. For standalone local development and Docker, retain the existing `API_URL` backend origin from the local environment or Compose configuration. `CORS_ORIGINS` only takes effect in standalone local development and Docker. `ACCESS_TOKEN_MINUTES` and `SEED_RANDOM_STATE` have safe code defaults; set them only if you intentionally need different behavior. `POSTGRES_*` variables belong to Docker Compose, not the Vercel project. No other hosting platform or database variables are used.

The FastAPI service performs no table creation, synthetic seeding, model training, pattern mining, or spaCy warm-up on Vercel startup or on read requests. The only per-instance setup is the pgvector column binding described above. `/api/health` only runs a `SELECT 1` database check. The classifier and embedder are trained by explicit initialization or the existing authorized model action, and their joblib artifacts are stored in PostgreSQL. A function may use `/tmp` as a cache, but PostgreSQL is the durable copy. The model format is trusted application data; do not load artifacts from untrusted sources. CSV validation tokens and their rows are also stored in PostgreSQL, tied to the validating user, and expire after 30 minutes.

## Local verification

Install the current Vercel CLI (`npm install -g vercel`), then from the repository root run `vercel dev -L`. The `-L` flag runs Services locally without a Vercel account. A reachable PostgreSQL database and initialized tables are still required. Set `DATABASE_URL` and `SECRET_KEY` in your local environment or ignored `.env`; use a separate test database if exercising writes. Set `AUTO_SEED=false` and `VERCEL=1` locally to exercise the serverless startup path without modifying an empty database. Vercel CLI's Services support requires a current CLI release.

```powershell
$env:AUTO_SEED = 'false'
$env:VERCEL = '1'
vercel dev -L
# In another terminal:
curl.exe -i http://localhost:3000/api/health
curl.exe -i http://localhost:3000/login
```

Run the backend tests with `cd backend; .\.venv\Scripts\python.exe -m pytest -q`. Run the frontend checks with `cd frontend; npm ci; npm run lint; npm test; npm run build`. To test authentication and the full workflow through `vercel dev`, sign in at `/login` and exercise dashboard, reports and details, search/filter, patterns, CSV import, review, taxonomy, model, settings, and audit with the initialized database.

## Deploy and verify

After committing the changes and linking the Git repository in Vercel, a push to `main` triggers production deployment. Alternatively, from the repository root use `vercel link` followed by `vercel deploy --prod` when authorized. Confirm `/api/health` returns HTTP 200 and `database: up`, then load `/login` and sign in with an existing account. The health endpoint only checks `SELECT 1`; it does not prove that `users`, `roles`, `audit_logs`, or model artifact tables have been initialized. If login fails with a missing-table error in Vercel function logs, perform the one-time database initialization described above from a trusted machine after authorizing the database changes. Verify the dashboard and the API workflows above against the live deployment. A successful local build alone does **not** verify Vercel routing, bundle size, database reachability, or production cookies.

## Runtime limits

- Vercel's Python runtime and Services are currently beta. The FastAPI service is a Vercel Function with ephemeral local storage. It cannot host PostgreSQL itself. [Services](https://vercel.com/docs/services) and the [Python runtime](https://vercel.com/docs/functions/runtimes/python) document this architecture.
- The installed Windows Python environment is about 523 MB; a Linux deployment bundle can differ. The standard Python bundle limit is 500 MB uncompressed, while [Large Functions](https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size) can reach 5 GB on Fluid Compute. New projects are automatically enrolled; if an older project exceeds its limit, set `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` in Vercel and redeploy. Check actual build output before enabling it.
- Vercel Functions have a [4.5 MB request/response payload limit](https://vercel.com/docs/functions/limitations). CSV validation is capped at 4 MB to leave multipart overhead. Very large imports need a separate upload/worker design. A 5,000-row CSV may still exceed the request duration while being analyzed and mined; split it into smaller files. `POST /api/model/reanalyze-all`, classifier retraining, pattern mining, and initial seeding can also be slow. The existing admin actions remain explicit, but Vercel may terminate them at the plan's duration limit. For larger real datasets, run controlled jobs from a persistent worker rather than relying on a Function request.
- Same-origin routing keeps the existing httpOnly, SameSite=Lax JWT cookie first-party. `COOKIE_SECURE=true` requires HTTPS. The HSE permissions and audit flow are unchanged. No wildcard CORS is enabled in Vercel.

**DEMO ENVIRONMENT — SYNTHETIC SAFETY DATA.** Poorvabhas provides SIF-precursor detection and decision-support. It does not predict fatalities. The proposed IOGP crosswalk requires independent HSE expert validation; the human HSE reviewer makes the final decision.
