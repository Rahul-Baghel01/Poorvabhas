# Pattern mining

Code: `backend/app/analytics/patterns.py`, `trend.py`. UI: **Pattern explorer**.

## Which reports are mined

Precursor reports only: current decision **SIF potential** or **SIF event**, or an **undetermined** case where a direct control is known to have failed. Low-severity and controlled (Success / Capacity) reports are excluded so that housekeeping noise does not form "patterns".

## Features

Each report becomes a set of tokens from its current analysis:

- `act:<canonical activity>` (e.g. `act:pump maintenance`)
- `bar:<failed barrier>` for every failed / absent control
- `en:<energy source>` for every present high-energy source
- `lsr:<primary rule>`

Sites and locations are **not** features, so a pattern can span locations. They are reported as distributions instead.

## Clustering

1. Build a binary matrix and a **Jaccard distance** matrix.
2. Run **HDBSCAN** (`sklearn.cluster.HDBSCAN`, `metric="precomputed"`, `min_cluster_size` = setting `pattern_min_cluster_size`, default 5, `min_samples=3`).
3. Describe each cluster by its **signature**: modal activity (≥ 60% of members), barrier (≥ 50%), energy (≥ 50%), rule (≥ 60%). Clusters whose signature has fewer than two elements are dropped. Clusters with identical signatures are merged.
4. **Fallback** — if HDBSCAN is unavailable or finds nothing: deterministic grouping by (activity, first failed barrier, first energy) with ≥ `min_size − 1` members.

Each pattern stores: `pattern_code`, name (e.g. *Pump maintenance + energy isolation failure + residual pressure*), method, signature, occurrences, SIF occurrences, site / location / activity / barrier / energy distributions, associated rules, **cohesion** (mean share of signature elements each member matches), **confidence** (cohesion × mean HDBSCAN membership probability), first/last seen, trend and member reports with membership.

Patterns are re-mined after CSV imports, on **Re-mine patterns**, and on **Re-analyse all**. The pattern-check stage of a new report compares it with the current patterns (≥ 2 matching signature elements).

## Trend detection

Calculated **only** from real report dates:

1. Bucket occurrences per month (per week when ≥ 40 events over ≥ 16 weeks), from the earliest report in the database to today.
2. Require **≥ 6 periods and ≥ 10 occurrences**; otherwise → **INSUFFICIENT_HISTORY** (with the reason).
3. Baseline = all but the last quarter of periods (min 2 recent periods). σ = max(sample SD, √mean, 0.5).
4. **EWMA** (λ = 0.3) with control limits μ ± 2.7σ·√(λ/(2−λ)).
5. **Tabular CUSUM** with k = 0.5σ, h = 4σ.
6. **INCREASING** if the latest EWMA exceeds the upper limit or CUSUM⁺ crosses h within the recent periods; **DECREASING** symmetrically; otherwise **STABLE**.

The pattern page draws the counts, EWMA line, upper control limit and baseline, and prints the statistics behind the verdict. The synthetic dataset contains one deliberately rising scenario (hot work without gas testing at Duliajan); the detector finds it without being told.
