# Poorvabhas

> **Detecting fatal potential before the outcome.**
> *Judge the hazard, not the outcome.*

**SIH 2026 · Problem Statement 26165 · Oil India Limited (OIL)**
AI/NLP engine to detect Serious Injury & Fatality (SIF) precursors in unsafe-act, unsafe-condition and near-miss reports.

> **DEMO ENVIRONMENT — SYNTHETIC SAFETY DATA.** Every report, site profile, exposure denominator and contractor in this repository is synthetic. No OIL production data is included. Poorvabhas is a **decision-support system**: it does not predict fatalities, accidents, injuries or individual outcomes. It helps HSE officers decide where to look first. The final safety decision always belongs to a human HSE reviewer.

---

## Contents

- [Overview](#overview)
- [Problem statement](#problem-statement)
- [Why it matters](#why-it-matters)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [System workflow](#system-workflow)
- [SCL classification](#scl-classification)
- [IOGP mapping](#iogp-mapping)
- [Pattern mining](#pattern-mining)
- [Ranking](#ranking)
- [Human review](#human-review)
- [Technology stack](#technology-stack)
- [Database](#database)
- [API](#api)
- [Installation](#installation)
- [Development](#development)
- [Docker](#docker)
- [Demo credentials](#demo-credentials)
- [Synthetic dataset](#synthetic-dataset)
- [Testing](#testing)
- [Limitations](#limitations)
- [Future pilot](#future-pilot)
- [Research references](#research-references)
- [Important disclaimer](#important-disclaimer)

---

## Overview

Poorvabhas reads free-text safety reports and turns them into an evidence trail an HSE officer can check:

| Step | What happens | Where you see it |
|---|---|---|
| NLP extraction | Activity, energy source, hazard, barrier/control, failure mode, behaviour, context — each with its **source text span** and confidence. Anything not in the text is reported as **Not stated**. | Report detail → *NLP extraction*, highlighted text |
| Hazard reasoning | Four SCL decision gates (high energy? energy event? direct control? serious injury?) answered **YES / NO / INSUFFICIENT**, each with evidence. | Report detail → *SCL decision* |
| SIF potential | SCL class (HSIF, PSIF, Exposure, Capacity, Success, LSIF, Low severity). Prototype SIF-potential = **PSIF + Exposure** (configurable). | Badges everywhere, Command center |
| Rule mapping | IOGP Life-Saving Rule — **proposed crosswalk, requires independent HSE expert validation**. | Report detail → *IOGP mapping* |
| Patterns | Recurring activity + failed barrier + energy combinations mined with HDBSCAN; trends tested with EWMA + CUSUM. | Pattern explorer |
| Ranking | Sites / activities / locations ranked by **empirical-Bayes adjusted** SIF-precursor density, not raw counts. | Command center, Pattern explorer |
| Human review | Uncertain or conflicting cases are routed to a reviewer; every decision is audited and stored as a feedback example. | Review queue, Audit log |

Everything runs locally. **No external LLM or cloud AI API is used or required.**

## Problem statement

OIL collects large volumes of unsafe-act (UA), unsafe-condition (UC) and near-miss reports. Most are low severity; a small fraction describe situations where only luck prevented a fatality. Those precursors are buried in free text and are usually graded by what happened (the outcome) rather than by what could have happened (the hazard). The prototype must:

1. Classify reports as SIF-potential vs non-SIF-potential.
2. Map relevant reports to the IOGP Life-Saving Rules.
3. Surface recurring precursor patterns (activity, location, barrier failure).
4. Rank sites/activities by SIF-precursor density in an interactive dashboard.
5. Let HSE personnel focus interventions where fatal potential is highest.

## Why it matters

Serious injuries and fatalities do not fall in step with minor-injury rates. A near miss where a suspended load swung past a rigger looks "harmless" by outcome but had fatal potential. The Safety Classification and Learning (SCL) approach asks the right questions — *was high energy present, and was a direct control in place?* Poorvabhas answers those questions at scale, shows its evidence, and hands the call to a person.

## How it works

```
REPORTS → FREE TEXT → NLP UNDERSTANDING → ENERGY + CONTROL → SIF POTENTIAL
        → IOGP 9-RULE MAPPING → RECURRING PATTERNS → FAIR RANKING → HUMAN REVIEW → FEEDBACK
```

1. **Level 1 — deterministic NLP.** Structured vocabularies (energy, barriers, activities, behaviours, context), regex/phrase matching, abbreviation and synonym normalisation (`LOTO`, `lock out`, `lockout` → energy isolation; `PTW`, `PPE`, `JSA`, `BOP`, `SIMOPS`…), spaCy sentence segmentation and clause-level barrier-state detection ("isolation **was not verified**", "**without** atmospheric monitoring").
2. **Level 2 — classical ML.** A `SafetyClassifier` abstraction with a TF-IDF + Logistic Regression implementation gives a second opinion P(SIF potential). Disagreement with the rule engine sends the case to review.
3. **Level 3 — transformer-ready.** `TransformerSafetyClassifier` plugs a locally stored HuggingFace model (e.g. DistilBERT) into the same interface when `transformers` + `torch` are installed. Without them the system falls back automatically.

Confidence is **explainable** (extraction, gate, completeness and mapping components). Priority is a **transparent 100-point additive score** with configurable weights. See [docs/scl-engine.md](docs/scl-engine.md).

## Architecture

```
┌────────────── DATA SOURCES ──────────────┐   ┌──────────── INGESTION + NLP ─────────────┐
│ UA / UC / near miss / incident reports    │   │ validation → normalisation → segmentation│
│ manual entry · CSV upload · synthetic set │──▶│ → entity extraction → energy + barriers  │
│ IOGP Life-Saving Rules (taxonomy)         │   │ → SCL gates → SIF → IOGP → pattern check │
└───────────────────────────────────────────┘   │ → priority → review routing              │
                                                 └──────────────────┬───────────────────────┘
┌────────────── PRESENTATION ──────────────┐   ┌──────────── INTELLIGENCE ────────────────┐
│ Next.js command software (dark, dense)    │◀──│ FastAPI · PostgreSQL + pgvector           │
│ command center · registry · investigation │   │ pattern mining (HDBSCAN) · EWMA/CUSUM     │
│ review workspace · patterns · admin       │   │ EB ranking · classifier · audit log       │
└───────────────────────────────────────────┘   └──────────────────────────────────────────┘
```

Details: [docs/architecture.md](docs/architecture.md).

## System workflow

`Create report → Analyze → Extract entities → Determine energy → Determine control → SCL classification → SIF potential → IOGP mapping → Priority → Review queue → Reviewer decision → Audit record → Dashboard update`

This exact flow is exercised by the backend test `test_critical_end_to_end_flow` and by the Playwright test `critical flow`.

## SCL classification

| Gate | Question | Evidence examples |
|---|---|---|
| Q1 | Was high energy present? | "residual pressure", "suspended load", "at 6 m", "415 V MCC panel" |
| Q2 | Did a high-energy incident (release / contact) occur? | "pressure was released", "load dropped", or "task was stopped" (no) |
| Q3 | Was a direct control / barrier in place? | "isolation was not verified" (no), "harness tied off" (yes) |
| Q4 | Was serious injury present? | injury-severity field, "hospitalised with a fracture" |

Seven classes: **HSIF, PSIF, Exposure, Capacity, Success, LSIF, Low severity** (plus *Undetermined* with the remaining candidates when evidence is missing). SIF-potential = **PSIF + Exposure**; HSIF is shown separately as a *SIF event*. Full decision tree: [docs/scl-engine.md](docs/scl-engine.md).

## IOGP mapping

Nine IOGP Life-Saving Rules — Bypassing Safety Controls, Confined Space, Driving, Energy Isolation, Hot Work, Line of Fire, Safe Mechanical Lifting, Work Authorization, Working at Height — plus **Process Safety / No Applicable Rule**. Mapping = admin-editable keywords + phrases × weight + structural signals from extraction (e.g. a failed isolation barrier). Output: primary rule, secondary rules, evidence and confidence.

**This is a proposed crosswalk. It is not an official IOGP mapping and requires independent HSE expert validation.** See [docs/iogp-mapping.md](docs/iogp-mapping.md).

## Pattern mining

Precursor reports are encoded as sets (activity, failed barriers, energy sources, rule) and clustered with **HDBSCAN over Jaccard distance** (scikit-learn), with deterministic frequency grouping as the fallback. Each pattern records occurrences, sites, locations, activities, barriers, energies, associated rules, cohesion and example reports. Trends are tested on real report dates with **EWMA** and **CUSUM**; with too little data the result is *Insufficient history*. See [docs/pattern-mining.md](docs/pattern-mining.md).

## Ranking

For every site / activity / location: total reports, SIF-potential reports, raw rate, raw precursor count, exposure-normalised density (sites: per 100k work-hours — synthetic exposure) and an **empirical-Bayes adjusted score** with a 90% credible interval (Beta-Binomial for rates, Gamma-Poisson for densities). The top row reads *"Highest adjusted SIF-precursor signal in the current dataset"* — never "most dangerous site". See [docs/ranking.md](docs/ranking.md).

## Human review

A case enters the queue when:

| Category | Trigger |
|---|---|
| Insufficient information | A required SCL gate is unsupported by the report |
| Rule conflict | Conflicting control statements, or an ambiguous primary rule |
| Model / rule disagreement | Classifier P(SIF) ≥ 0.70 vs engine "non-SIF" (or ≤ 0.30 vs "SIF") |
| Borderline | A weak gate (< 0.65) whose inversion **would change the SIF outcome** |
| Low confidence | Overall confidence < 0.55 |
| Manual request | An officer sends the report to a reviewer |

Reviewer actions: **Confirm** (engine result is correct), **Correct** (set the SCL class, SIF-potential or LSR, with a reason) and **Refine** (mark insufficient information, or add a note that keeps the review open). A decision that changes the engine's result is shown as **Expert corrected**; otherwise **Expert confirmed**. The API also accepts `REJECT` (flip SIF-potential). Each decision stores the original prediction, the decision, reviewer identity, timestamp, reason and note, writes an audit record, and becomes a **feedback example**. Retraining is an explicit admin action (Model / Analysis → *Retrain classifier*); models are never retrained automatically after each correction.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, Radix primitives (shadcn-style components), Lucide icons, Recharts, TanStack Query, Motion |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2 |
| Database | PostgreSQL 16 + pgvector |
| NLP / ML | spaCy (sentencizer), scikit-learn (TF-IDF, Logistic Regression, TruncatedSVD, HDBSCAN), SciPy, NumPy, pandas; optional HuggingFace Transformers |
| Auth | bcrypt password hashes, JWT (HS256) in an httpOnly SameSite cookie |
| Testing | pytest, Vitest + Testing Library, Playwright |
| Deployment | Vercel (Next.js + FastAPI services) with Neon PostgreSQL + pgvector in production; Docker Compose for local development |

XGBoost was not needed: the classifier's job is a transparent second opinion and TF-IDF + LogReg exposes term weights directly.

## Database

The PostgreSQL schema includes reports, analyses, review decisions, model versions and artifacts, pending CSV imports, embeddings (pgvector `vector(64)` when available), audit logs, and settings. Local startup can initialize the schema; Vercel requires the explicit one-time initializer described in [docs/vercel-deployment.md](docs/vercel-deployment.md). See [docs/data-model.md](docs/data-model.md).

## API

REST under `/api` (OpenAPI UI at `http://localhost:8000/docs`). Main groups: auth, reports, review, dashboard/ranking/patterns, imports, taxonomy, model, settings, audit. See [docs/api.md](docs/api.md).

## Installation

Prerequisites: **Docker Desktop** (simplest) — or Python 3.12+, Node 20+ and PostgreSQL 16 with pgvector for local development.

```bash
git clone <repo> poorvabhas && cd poorvabhas
cp .env.example .env          # set SECRET_KEY
docker compose up --build     # postgres + backend + frontend
```

Open **http://localhost:3000**. On first start the backend creates the schema and seeds the synthetic dataset (~30 s).

## Development

```bash
# 1. database only
docker compose up -d postgres            # exposes localhost:5433

# 2. backend
cd backend
python -m venv .venv
.venv/Scripts/activate                   # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
# reseed a LOCAL database from scratch:  python -m app.seed.seed --reset   (never against production)

# 3. frontend
cd frontend
npm install
npm run dev                              # http://localhost:3000, proxies /api → :8000
```

## Docker

For a single-project Vercel deployment of the existing frontend and FastAPI backend, see [docs/vercel-deployment.md](docs/vercel-deployment.md). The Docker workflow below remains available for local development.

`docker-compose.yml` runs three services:

| Service | Image | Port |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5433 → 5432 |
| `backend` | `./backend` (FastAPI, auto-seeds on first start) | 8000 |
| `frontend` | `./frontend` (Next.js standalone) | 3000 |

Model artefacts live in the `models` volume, database data in `pgdata`. `docker compose down -v` resets everything.

## Demo credentials

| Username | Password | Role | Access |
|---|---|---|---|
| `admin` | `Admin@2026` | HSE Admin | Everything, including taxonomy, model, settings, audit |
| `officer` | `Officer@2026` | HSE Officer | Dashboard, reports, analysis, patterns, review queue, import |
| `reviewer` | `Reviewer@2026` | HSE Officer | Same as officer (second reviewer identity for demos) |

These are demo-only accounts. Change or remove them before any non-demo use.

## Synthetic dataset

`backend/app/seed/generator.py` generates `SEED_REPORTS` random reports plus 5 fixed demo cases `SYN-DEMO-001…005` (285 with the local default of 280; the production demo uses `SEED_REPORTS=275` for **280 reports**) across seven synthetic site profiles named after Assam locations (Digboi, Duliajan, Naharkatiya, Moran, Bokakhat, Hapjan, Tengakhat), 14 activities and four report types, spread over the last 12 months. The mix includes SIF-potential, non-SIF, borderline and deliberately vague reports, plus phrasings outside the engine's vocabulary.

Each scenario carries a **reference label assigned by scenario design**, not by the engine. The labels drive an honest held-out evaluation (25% hash split). A rising hot-work / gas-testing pattern at Duliajan is planted so the trend detector has a real signal to find. All names, contractors ("Contractor-A (synthetic)") and exposure hours are fictional.

## Testing

```bash
cd backend  && pytest                          # 86 tests: extraction, SCL, mapping, scoring, patterns, ranking, API, E2E flow, deployment
cd frontend && npm test                        # Vitest: formatting, evidence highlighting, badges, decision form
cd frontend && npx playwright install chromium && npm run test:e2e   # needs backend + frontend running
```

Playwright covers: the critical create → analyse → review → decision → audit → dashboard flow, every route rendering, search/filters, role restriction, CSV import, and a responsive check that no route scrolls horizontally at 1440 / 1280 / 1024 / 768 / 390 px. E2E runs add a few records; reset with `docker compose down -v && docker compose up` before a live demo.

## Limitations

- **Synthetic evaluation only.** Metrics on the Model page are computed on synthetic data with scenario-designed labels and are optimistic. The deterministic vocabulary was developed alongside those templates, so its agreement is optimistic by construction. Real-world accuracy is unknown until a labelled pilot.
- **English only.** Assamese/Hindi or code-mixed reports are not handled.
- **Vocabulary coverage.** Unusual phrasing ("the casing was still full") can leave a gate unanswered. By design this routes the case to review rather than guessing, but it increases reviewer load.
- **SCL judgement.** Whether a control is "direct" is simplified (e.g. PPE and permits are treated as administrative). Borderline definitions need HSE expert calibration.
- **Crosswalk.** The SCL-to-IOGP mapping is our proposal and has not been validated by IOGP or OIL experts.
- **Exposure denominators** for sites are synthetic; activities and locations are ranked by rate only.
- **CSV import limits.** Validation sessions are stored in PostgreSQL so they survive multiple backend instances. Files are limited to 4 MB to fit Vercel's request limit; large analyses may still need smaller batches or a persistent worker.

## Future pilot

1. Agree a data-sharing and anonymisation protocol with OIL HSE; import 12–24 months of historical UA/UC/near-miss reports.
2. Have two HSE experts independently label a stratified sample of ~1,000 reports (SCL class + rule); measure inter-rater agreement.
3. Calibrate vocabulary, direct-control definitions, thresholds and the IOGP crosswalk with those experts.
4. Fine-tune the transformer classifier on the reviewed labels; evaluate on a held-out, time-split set.
5. Replace synthetic exposure hours with real man-hours per site.
6. Run in shadow mode alongside the existing process for one quarter, then evaluate reviewer workload and missed-signal rate.
7. Add Hindi/Assamese support, SSO (OIL directory) and retention policies.

## Research references

- Edison Electric Institute (EEI). *Safety Classification and Learning (SCL) Model* — the energy-based classification behind the HSIF / PSIF / Exposure / Capacity / Success / LSIF / Low-severity classes.
- Hallowell, M. R. et al. (2021). *The Statistical Invalidity of TRIR as a Measure of Safety Performance.* Professional Safety — why outcome-rate metrics do not track SIF risk.
- International Association of Oil & Gas Producers (IOGP). *Report 459 — IOGP Life-Saving Rules* (2018).
- Campello, R. J. G. B., Moulavi, D., & Sander, J. (2013). *Density-Based Clustering Based on Hierarchical Density Estimates* (HDBSCAN). PAKDD.
- Roberts, S. W. (1959). *Control Chart Tests Based on Geometric Moving Averages* (EWMA). Technometrics.
- Page, E. S. (1954). *Continuous Inspection Schemes* (CUSUM). Biometrika.
- Casella, G. (1985). *An Introduction to Empirical Bayes Data Analysis.* The American Statistician.

The team should confirm edition and page details before citing these in the final submission.

## Important disclaimer

Poorvabhas is a **prototype decision-support tool** built for Smart India Hackathon 2026. It:

- does **not** predict fatalities, accidents, injuries or individual outcomes;
- does **not** replace HSE officers, permit-to-work systems or incident investigation;
- runs on **synthetic demo data** only and contains **no OIL production data**;
- presents a **proposed** SCL-to-IOGP crosswalk that **requires independent HSE expert validation**;
- reports model metrics **only** where computed, with their basis stated.

Every classification is a suggestion with evidence. The HSE reviewer makes the decision.
