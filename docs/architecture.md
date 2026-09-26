# Architecture

Poorvabhas has four logical layers. Every layer runs locally; none depends on an external AI service.

## 1. Data sources

| Source | Entry point |
|---|---|
| Manual report entry | `POST /api/reports` (New report page) |
| CSV upload | `POST /api/imports/validate` → `POST /api/imports/{token}/commit` |
| Synthetic demo dataset | `app/seed/generator.py`, loaded by `app/seed/seed.py` on first start |
| IOGP Life-Saving Rules | `taxonomy_rules` table, seeded from `app/nlp/iogp.py::DEFAULT_RULES`, editable on the Taxonomy page |

## 2. Ingestion + NLP (`backend/app/nlp`)

| Module | Responsibility |
|---|---|
| `vocabulary.py` | Structured vocabularies: energy sources (with "high energy" flag), low-energy hazards, barriers (direct vs administrative), barrier-state cues, event and injury cues, activities, behaviours, context, equipment, abbreviations |
| `normalize.py` | Unicode clean-up (offset-preserving), abbreviation expansion, spaCy sentencizer (regex fallback), clause segmentation |
| `extraction.py` | Engine 1: evidence-preserving entities for 13 types, barrier polarity (present / failed / absent / conflict), derived hazards, "Not stated" |
| `scl.py` | Engine 2: four gates, the SCL tree (`resolve`), counterfactual gate flip |
| `iogp.py` | Engine 3: keyword + phrase + structural-signal scoring, primary / secondary rules, confidence, ambiguity |
| `classifier.py` | `SafetyClassifier` interface, TF-IDF + LogReg, optional transformer, LSA embedder |
| `scoring.py` | Explainable confidence, 100-point priority, review routing |
| `pipeline.py` | Orchestrates the nine stages and records a timed trace |

The pipeline is **pure**: it takes a report dict and returns an `AnalysisOutput`. Database context (recurrence, pattern matches) is injected through a callback, so the same code runs in tests, in the API and in the seeder.

## 3. Intelligence (`backend/app/analytics`, `backend/app/services`)

| Module | Responsibility |
|---|---|
| `services/analysis_service.py` | Runs the pipeline for a stored report and persists analysis, entities, evidence spans, SCL gates, rule mappings, review items, embeddings and audit events |
| `services/review_service.py` | Reviewer decisions, feedback examples, manual review requests |
| `services/model_service.py` | Controlled training, held-out evaluation, engine evaluation, human-review evaluation |
| `services/import_service.py` | CSV parsing and row validation |
| `analytics/patterns.py` | Engine 4: HDBSCAN / frequency pattern mining |
| `analytics/trend.py` | EWMA + CUSUM trend tests |
| `analytics/ranking.py` | Engine 5: empirical-Bayes ranking |
| `analytics/dashboard.py` | Command-centre aggregates (all SQL `GROUP BY` at request time) |

## 4. Presentation (`frontend/`)

Next.js App Router. The browser only talks to same-origin `/api/*`; `next.config.ts` proxies those calls to FastAPI in standalone local development, while Vercel Services routes them directly to the FastAPI service. The httpOnly session cookie stays first-party. TanStack Query caches server state; every write invalidates the affected queries (`lib/hooks.ts::useInvalidateAll`), so the dashboard updates after a new report, an import or a review decision.

```
app/login                 sign-in + product story
app/(app)/                authenticated shell (sidebar, status bar, synthetic-data banner)
  page.tsx                Command center
  reports/                registry, [id] investigation, new
  patterns/               explorer, [id] detail
  review/                 reviewer workspace
  import/ taxonomy/ model/ settings/ audit/
components/report/        EvidenceText, ExtractionTable, SclGates, Breakdowns, DecisionForm
components/charts/        ReportsOverTime, HBarList, SparkBars, TrendChart, RankingTable
```

## Security

- Passwords: bcrypt. Sessions: JWT (HS256, 12 h) in an `httpOnly`, `SameSite=Lax` cookie; `Authorization: Bearer` is also accepted for API clients and tests.
- Role-based permissions (`HSE_OFFICER`, `HSE_ADMIN`) are enforced server-side on every endpoint (`security.py::require_permission`); the UI hides what a role cannot use.
- Input validation via Pydantic; CSV size and row limits; all SQL through SQLAlchemy parameters.
- Security headers (`X-Frame-Options`, `nosniff`, `Referrer-Policy`) on the frontend.

## Deployment

`docker-compose.yml` → `postgres` (pgvector/pg16), `backend` (FastAPI, seeds on first start), `frontend` (Next.js standalone). For production: set a strong `SECRET_KEY`, `COOKIE_SECURE=true` behind HTTPS, `DEMO_MODE=false`, disable `AUTO_SEED`, and remove the demo accounts.
