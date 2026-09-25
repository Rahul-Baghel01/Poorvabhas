# Ranking

Code: `backend/app/analytics/ranking.py`. Endpoint: `GET /api/ranking?dimension=site|activity|location&days=90`.

## Why not raw counts

Raw precursor counts reward busy sites (more work → more reports). Raw rates over-react to tiny samples (1 report, 1 SIF → 100%). Neither is fair. Poorvabhas shows both, and ranks by an **empirical-Bayes (EB) adjusted** score that shrinks small samples toward the dataset average in proportion to how little evidence they have.

## Definitions

- **SIF precursor** — a report whose current decision (AI or reviewer) is SIF-potential (PSIF or Exposure by default).
- **Window** — reports dated in the last *N* days (default 90).

## Columns

| Column | Meaning |
|---|---|
| Reports | total reports in the window |
| SIF potential | SIF precursors in the window (raw precursor count) |
| Raw rate | SIF potential / reports |
| Raw / 100k h | (sites only) SIF precursors per 100,000 exposure hours, with synthetic annual hours scaled to the window |
| Adjusted | EB posterior mean density (sites) or rate (activities, locations) |
| 90% interval | posterior credible interval |

## Method

**Rates — Beta-Binomial.** Prior Beta(α, β) by method of moments across groups: dataset rate *m*, between-group variance τ² = observed weighted variance − expected binomial noise. Prior strength α+β = m(1−m)/τ² − 1, bounded to [2, 2 × mean group size]. Posterior mean = (k + α) / (n + α + β).

**Densities — Gamma-Poisson.** Prior Gamma(α, β) by method of moments on per-exposure rates, with β bounded by 2 × mean exposure. Posterior mean = (k + α) / (E + β), where E is exposure in units of 100k hours.

The upper bound on prior strength matters: with few groups the method of moments tends to underestimate heterogeneity, and without the bound every site collapses to the same score. The cap means the prior never outweighs a typical group's own evidence.

## Language

The top row is annotated **"Highest adjusted SIF-precursor signal in the current dataset."** The UI never calls a site "dangerous" or "most dangerous". A backend test asserts the word does not appear. Groups with fewer than 8 reports are annotated *"Small sample — shrunk strongly toward the dataset mean."*

## Caveats

Exposure hours are synthetic. With real man-hours the site ranking becomes a true exposure-normalised density; until then treat it as illustrative. Activities and locations have no denominator and are ranked by EB-adjusted rate.
