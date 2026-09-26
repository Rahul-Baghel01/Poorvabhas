# Vercel deployment

Poorvabhas uses one Vercel project with two [Services](https://vercel.com/docs/services). The project root is the repository root. `frontend/` builds as Next.js, and `backend/` builds with Vercel's native FastAPI/Python runtime using `app.main:app`. Root `vercel.json` sends `/api/*` to FastAPI and all other requests to Next.js. The backend receives the original `/api/...` path. The browser always requests same-origin `/api/...`; no Render URL or public API base variable is built into the UI. Do not set a Vercel project Root Directory of `frontend` or `backend`.

## Before linking the project

Use the existing persistent PostgreSQL database only if its **external** connection URL is reachable from Vercel. A Render private/internal hostname will not work. Keep the database running; this migration does not delete or reset it. `postgres://` and `postgresql://` are normalized to the installed psycopg 3 driver. pgvector remains enabled when the database supports the extension; the existing JSON vector fallback remains available.

Back up the database, then perform the one-time additive initialization from a trusted local machine that can reach it. This creates any missing tables, including `model_artifacts` and `pending_imports`. If reports already exist and their old model paths are unavailable, the explicit initializer retrains the classifier and embedder once and stores them in PostgreSQL. It does not reseed an existing report set. On an empty database, it creates the existing synthetic demo set, models, and patterns once. It does not drop tables unless `--reset` is passed, which must **never** be used against the existing Render database.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = '<external PostgreSQL URL>'
$env:SECRET_KEY = '<same production secret configured in Vercel>'
$env:ENVIRONMENT = 'production'
$env:AUTO_SEED = 'false'
.\.venv\Scripts\python.exe -m app.seed.seed
```

The initializer can take longer than a normal HTTP request. Run it in this local CLI, not in a Vercel Function. Do not use the development demo credentials for real safety data. If the database is empty and `DEMO_MODE=true`, the initializer creates the existing demo users and synthetic reports. On an existing Render database, keep its user accounts and current data.

## Vercel project settings

Connect `Rahul-Baghel01/Poorvabhas`, production branch `main`, with project root `./` (repository root). Do not override the build command or the two service roots in `vercel.json`. Set these environment variables in Vercel's dashboard for Production and any Preview deployment that should access a database:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Externally reachable PostgreSQL URL, with TLS as required by the provider. Keep it secret. |
| `SECRET_KEY` | A long random value; use the same value during initialization and across deployments so sessions remain valid. Keep it secret. |
| `ENVIRONMENT` | `production` |
| `COOKIE_SECURE` | `true` |
| `AUTO_SEED` | `false` (the Vercel runtime skips startup seeding regardless) |
| `DEMO_MODE` | `true` for the synthetic demo database; `false` only when configured for non-demo use |
| `SEED_REPORTS` | `280` if initializing an empty synthetic demo database; unused on normal requests |
| `VECTOR_BACKEND` | `auto` (or `json` if the existing database lacks pgvector support) |
| `USE_TRANSFORMER` | `false` unless the optional transformer dependencies and local model are deployed separately |
| `MODEL_PATH` | `/tmp/poorvabhas-models` (optional; this is the Vercel default) |

`CORS_ORIGINS` and `API_URL` are for standalone local development and should not be set in Vercel. `NEXT_PUBLIC_API_URL` is no longer used. `ACCESS_TOKEN_MINUTES` and `SEED_RANDOM_STATE` have safe code defaults; set them only if you intentionally need different behavior. `POSTGRES_*` variables belong to Docker Compose, not the Vercel project.

The FastAPI service performs no database initialization, synthetic seeding, model training, pattern mining, or spaCy warm-up on Vercel startup. `/api/health` only runs a `SELECT 1` database check. The classifier and embedder are trained by explicit initialization or the existing authorized model action, and their joblib artifacts are stored in PostgreSQL. A function may use `/tmp` as a cache, but PostgreSQL is the durable copy. The model format is trusted application data; do not load artifacts from untrusted sources. CSV validation tokens and their rows are also stored in PostgreSQL, tied to the validating user, and expire after 30 minutes.

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

After committing the changes and linking the Git repository in Vercel, a push to `main` triggers production deployment. Alternatively, from the repository root use `vercel link` followed by `vercel deploy --prod` when authorized. Confirm `/api/health` returns HTTP 200 and `database: up`, then load `/login` and sign in with an existing account. Verify the dashboard and the API workflows above against the live deployment. A successful local build alone does **not** verify Vercel routing, bundle size, database reachability, or production cookies.

## Runtime limits

- Vercel's Python runtime and Services are currently beta. The FastAPI service is a Vercel Function with ephemeral local storage. It cannot host PostgreSQL itself. [Services](https://vercel.com/docs/services) and the [Python runtime](https://vercel.com/docs/functions/runtimes/python) document this architecture.
- The installed Windows Python environment is about 523 MB; a Linux deployment bundle can differ. The standard Python bundle limit is 500 MB uncompressed, while [Large Functions](https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size) can reach 5 GB on Fluid Compute. New projects are automatically enrolled; if an older project exceeds its limit, set `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` in Vercel and redeploy. Check actual build output before enabling it.
- Vercel Functions have a [4.5 MB request/response payload limit](https://vercel.com/docs/functions/limitations). CSV validation is capped at 4 MB to leave multipart overhead. Very large imports need a separate upload/worker design. A 5,000-row CSV may still exceed the request duration while being analyzed and mined; split it into smaller files. `POST /api/model/reanalyze-all`, classifier retraining, pattern mining, and initial seeding can also be slow. The existing admin actions remain explicit, but Vercel may terminate them at the plan's duration limit. For larger real datasets, run controlled jobs from a persistent worker rather than relying on a Function request.
- Same-origin routing keeps the existing httpOnly, SameSite=Lax JWT cookie first-party. `COOKIE_SECURE=true` requires HTTPS. The HSE permissions and audit flow are unchanged. No wildcard CORS is enabled in Vercel.

**DEMO ENVIRONMENT — SYNTHETIC SAFETY DATA.** Poorvabhas provides SIF-precursor detection and decision-support. It does not predict fatalities. The proposed IOGP crosswalk requires independent HSE expert validation; the human HSE reviewer makes the final decision.
