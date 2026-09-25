# Demo script (≈ 10 minutes)

**Setup:** `docker compose up` (or the dev setup), open http://localhost:3000 in a 1440 px wide window. Have `docs/sample-import.csv` ready. To start from a clean dataset: `docker compose down -v && docker compose up`, or run `python -m app.seed.seed --reset` in the backend.

**One-line pitch:** *Poorvabhas reads OIL's unsafe-act and near-miss reports, judges the hazard rather than the outcome, and shows HSE where fatal potential is concentrated. A human always makes the final call.*

| # | Do | Say |
|---|---|---|
| 1 | **Login** — click `admin / Admin@2026` in the demo credentials box, *Sign in*. | "Two roles: HSE Officer and HSE Admin. Everything you see is synthetic data, labelled on every screen." |
| 2 | **Command center.** Point at the KPIs, the red priority banner, *SIF potential distribution*, *Reports over time*. | "Every number is a live database query. The banner counts high-priority SIF signals no human has validated yet." |
| 3 | Click **SIF-potential reports**, sort *Highest priority*, then open **SYN-DEMO-001** (search for it). | "Let's investigate one report." |
| 4 | **Original report** panel. | "This is exactly what the fitter wrote. Every highlight is evidence the engine used." |
| 5 | **NLP extraction** table — hover a row to highlight its span. | "Activity, energy, barrier, failure mode, each with source text and confidence. Environmental context isn't in the report, so it says *Not stated*. Nothing is invented." |
| 6 | **SCL decision — Gate Q1.** | "High energy: YES — *residual pressure*." |
| 7 | **Gate Q3.** | "Direct control: NO — *isolation was not verified*." |
| 8 | **Decision path → SCL class.** | "Exposure: high energy with no direct control, and nobody was hurt only because it didn't release. That's judging the hazard, not the outcome." |
| 9 | **SIF potential: YES.** | "Prototype definition: PSIF + Exposure, configurable in Settings." |
| 10 | **IOGP mapping.** Point at the amber disclaimer. | "Energy Isolation. This is our proposed crosswalk and needs independent HSE expert validation." |
| 11 | **Priority score** and **Confidence** breakdowns. | "Transparent 100-point model and explainable confidence, with a classifier second opinion." |
| 12 | Go to **Safety Reports → New report**, click the demo case **Vehicle + pedestrian**, click **ANALYZE REPORT**. Watch the live pipeline. | "The report says a pedestrian was nearby, but not whether there was segregation. The engine won't assume, so it routes to a reviewer as *Insufficient information*." |
| 13 | **Open full investigation** → in *Review status* choose **Change**, SCL class **Exposure**, reason "No pedestrian segregation at the gantry", **Record decision**. | "The reviewer decides. Original prediction, decision, identity, time, reason and note are all stored, and the case becomes a feedback example for controlled retraining." |
| 14 | Scroll to **Audit history**. | "REPORT_CREATED → ANALYZED → SIF_CLASSIFIED → RULE_MAPPED → REVIEW_STARTED → REVIEW_COMPLETED." |
| 15 | **Pattern explorer.** | "Patterns are mined from the data with HDBSCAN, not hard-coded." |
| 16 | Open **Hot work + gas testing failure** (marked *Increasing*). | "Trend claimed by CUSUM/EWMA on real dates; small patterns say *Insufficient history*." |
| 17 | Scroll to **SIF precursor density ranking**; switch *site / activity*. | "Empirical-Bayes adjusted, so a site with nine reports doesn't top the list by luck. The wording: *highest adjusted signal in this dataset*, never 'most dangerous site'." |
| 18 | **Import data** → drop `docs/sample-import.csv` → show validation (valid / invalid rows, errors) → **Import & analyse**. | "Bad rows are rejected with reasons; valid rows go through the same engine." |
| 19 | **Command center** — totals, queue and charts now include the import. | "The dashboard updates immediately." |

**Optional:** Review queue (inline decisions by category), Taxonomy (*Test mapping*), Model / Analysis (metrics labelled synthetic, human-review evaluation *pending*), sign in as `officer` to show role restrictions.

**Closing:** "AI finds the signal, NLP extracts the evidence, SCL reasoning evaluates the hazard, IOGP mapping connects it to action, pattern mining finds recurrence, ranking prioritises attention, and the HSE reviewer makes the final decision."

## Likely judge questions

- **Is the accuracy real?** Metrics are computed on a held-out synthetic split and say so. The engine's vocabulary was built alongside the templates, so its figures are optimistic. The Model page shows human-review evaluation as *pending* until 20 reviewed decisions exist. Real accuracy needs a labelled OIL pilot.
- **Why not an LLM?** Auditability, data residency and cost. Every decision is traceable to text spans and rules, and runs on-premise. The `SafetyClassifier` interface accepts a local transformer.
- **What if the report is vague?** The gate returns INSUFFICIENT and the report goes to a reviewer. The engine never guesses.
