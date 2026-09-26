# API

Base URL: `http://localhost:8000/api` (the frontend calls the same paths via `/api` on port 3000). Interactive docs: `http://localhost:8000/docs`.

**Authentication.** `POST /api/auth/login` sets an httpOnly `pv_session` cookie and also returns a `token`; send `Authorization: Bearer <token>` from scripts. Errors use `{"detail": "..."}`: 401 unauthenticated, 403 wrong role, 404 not found, 409 conflict, 422 validation, 503 database unavailable.

Permissions: **O** = HSE Officer and Admin, **A** = Admin only.

## Auth

| Method | Path | Body / notes |
|---|---|---|
| POST | `/auth/login` | `{"username","password"}` → `{user, token}` |
| POST | `/auth/logout` | clears cookie |
| GET | `/auth/me` | current user, role, permissions |

## Reports (O)

| Method | Path | Notes |
|---|---|---|
| GET | `/reports` | `search`, `report_type`, `site`, `date_from`, `date_to`, `sif_signal`, `priority`, `scl_class`, `lsr`, `status`, `activity`, `location` (comma-separated for multiple), `page`, `page_size` (≤ 100), `sort` (`date_desc`, `date_asc`, `priority_desc`, `confidence_asc`, `report_id`). Server-side pagination. |
| GET | `/reports/facets` | filter options |
| POST | `/reports` | create + analyse; returns `{report_id, trace, detail}` (201) |
| GET | `/reports/{report_id}` | full investigation: report, analysis (entities + evidence, SCL gates, mapping, priority, confidence, trace), open review, decisions, audit, patterns |
| GET | `/reports/{report_id}/similar?k=5` | nearest reports by embedding (pgvector cosine) |
| POST | `/reports/{report_id}/reanalyze` | re-run the engine (human decisions preserved) |
| POST | `/reports/{report_id}/request-review` | `{"reason"}` → manual review item |
| POST | `/reports/{report_id}/decision` | reviewer decision (same body as below) |

Create body:

```json
{
  "report_id": null,
  "report_type": "Near Miss",
  "date": "2026-09-20",
  "site": "Digboi",
  "location": "GGS-2 Digboi",
  "activity": "Pump maintenance",
  "equipment": "Booster pump",
  "description": "During pump maintenance, isolation was not verified ...",
  "worker_role": "Fitter",
  "contractor": null,
  "injury_severity": "None",
  "shift": "Day",
  "weather": "Clear"
}
```

## Review (O)

| Method | Path | Notes |
|---|---|---|
| GET | `/review` | `category`, `status` (`OPEN`/`CLOSED`), `page`, `page_size`, `sort` (`priority`, `newest`, `oldest`); items include gate evidence |
| GET | `/review/stats` | open counts per category |
| POST | `/review/{id}/decision` | see below |

Decision body:

```json
{ "action": "CHANGE", "scl_class": "EXPOSURE", "sif_potential": null, "primary_lsr": null,
  "reason": "No pedestrian segregation", "note": "Traffic management action raised" }
```

`action` ∈ `CONFIRM`, `REJECT`, `CHANGE`, `INSUFFICIENT`, `NOTE`. `REJECT` and `CHANGE` require `reason`; `NOTE` requires `note` and leaves the item open.

## Analytics (O)

| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard?days=90` | KPIs with prior-period deltas, priority banner, distributions, weekly series, top rules / activities / sites, patterns, queue preview, site ranking |
| GET | `/ranking?dimension=site&days=90` | EB ranking (see ranking.md) |
| GET | `/patterns` | current patterns |
| GET | `/patterns/{id}` | pattern + trend statistics + member reports |
| POST | `/patterns/mine` | re-mine now |

## Import (O)

| Method | Path | Notes |
|---|---|---|
| GET | `/imports/template` | CSV template |
| POST | `/imports/validate` | multipart `file` → `{token, rows_detected, valid_rows, invalid_rows, errors[], preview[], new_sites[]}` |
| POST | `/imports/{token}/commit` | store + analyse valid rows, re-mine patterns → `{imported, analyzed, sif_signal, review_required, report_ids}` |

CSV files are limited to 4 MB on Vercel. Validation tokens are stored in PostgreSQL, belong to the validating user, and expire after 30 minutes.

## Administration

| Method | Path | Perm | Notes |
|---|---|---|---|
| GET | `/taxonomy` | A | rules + crosswalk label/disclaimer |
| PUT | `/taxonomy/{code}` | A | `{keywords?, phrases?, weight?, is_active?}` (audited) |
| POST | `/taxonomy/test` | A | `{"text"}` → mapping result |
| GET | `/model/status` | O | engine, components, versions, metrics (only if computed), feedback counts, human-review evaluation |
| POST | `/model/train` | A | retrain classifier on reference labels + feedback |
| POST | `/model/reanalyze-all` | A | re-run all reports with current engine / taxonomy / settings |
| GET | `/settings` | A | engine settings, environment, database, versions, security |
| PUT | `/settings/{key}` | A | `priority_weights` (sum 100), `priority_thresholds`, `review_thresholds`, `sif_potential_classes`, `recurrence_window_days`, `pattern_min_cluster_size`, `use_classifier` |
| GET | `/audit` | A | `event_type`, `search`, `page`, `page_size` |
| GET | `/health` | — | database status |
