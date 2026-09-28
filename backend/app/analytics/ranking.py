"""Engine 5 - fair ranking of sites / activities / locations by SIF-precursor signal.

Raw counts reward busy sites; raw rates over-react to tiny samples. We therefore report:
  total reports, SIF-potential reports, raw rate, raw precursor count,
  exposure-normalised density (sites: per 100k work-hours, synthetic exposure), and an
  empirical-Bayes adjusted score that shrinks small samples toward the dataset mean.

- Rate (share of reports that are SIF-potential): Beta-Binomial EB, method of moments.
- Density (per exposure): Gamma-Poisson EB, method of moments.
90% credible intervals come from the posterior distributions.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Report, Site

HOURS_UNIT = 100_000
TOP_NOTE = "Highest adjusted SIF-precursor signal in the current dataset"


def _beta_prior(k: list[int], n: list[int]) -> tuple[float, float]:
    N = sum(n)
    m = sum(k) / N if N else 0.0
    m = min(max(m, 1e-3), 1 - 1e-3)
    if len(n) < 2:
        return m * 10, (1 - m) * 10
    s2 = sum(ni * ((ki / ni) - m) ** 2 for ki, ni in zip(k, n)) / N
    noise = m * (1 - m) * sum(1 / ni for ni in n) / len(n)
    tau2 = max(s2 - noise, 1e-5)
    # MoM under-estimates heterogeneity on small samples; cap prior strength at twice the
    # average group size so the prior never outweighs a typical group's own evidence.
    cap = max(2.0, 2.0 * N / len(n))
    strength = min(max(m * (1 - m) / tau2 - 1, 2.0), cap)
    return m * strength, (1 - m) * strength


def _gamma_prior(k: list[int], e: list[float]) -> tuple[float, float]:
    E = sum(e)
    m = max(sum(k) / E if E else 0.0, 1e-3)
    if len(e) < 2:
        return m * 2, 2.0
    s2 = sum(ei * ((ki / ei) - m) ** 2 for ki, ei in zip(k, e)) / E
    noise = m * sum(1 / ei for ei in e) / len(e)
    tau2 = max(s2 - noise, 1e-4)
    beta = min(max(m / tau2, 0.1), 2.0 * E / len(e))
    return m * beta, beta


def rank(db: Session, dimension: str = "site", days: int | None = 90, today: date | None = None, limit: int | None = None) -> dict[str, Any]:
    from scipy import stats  # deferred: importing it adds ~0.7 s to every serverless cold start

    today = today or date.today()
    col = {"site": Site.name, "activity": func.lower(Report.activity), "location": Report.location}[dimension]
    sif = func.sum(case((Report.sif_potential.is_(True), 1), else_=0))
    events = func.sum(case((Report.sif_signal == "SIF_EVENT", 1), else_=0))
    high = func.sum(case((Report.priority_level.in_(["CRITICAL", "HIGH"]), 1), else_=0))
    q = select(col.label("key"), func.count(Report.id), sif, events, high, func.avg(Report.priority_score)).join(Site, Site.id == Report.site_id)
    if dimension == "location":
        q = q.add_columns(func.min(Site.name))
    if days:
        q = q.where(Report.date > today - timedelta(days=days), Report.date <= today)
    q = q.group_by(col)
    rows = db.execute(q).all()
    if not rows:
        return {"dimension": dimension, "days": days, "items": [], "method": {}, "note": "No reports in the selected window"}

    keys = [r[0] for r in rows]
    n = [int(r[1]) for r in rows]
    k = [int(r[2] or 0) for r in rows]
    a, b = _beta_prior(k, n)

    exposure: dict[str, float] = {}
    if dimension == "site":
        scale = (days or 365) / 365
        for s in db.scalars(select(Site)).all():
            if s.exposure_hours:
                exposure[s.name] = s.exposure_hours * scale / HOURS_UNIT
    use_density = dimension == "site" and all(key in exposure for key in keys)
    if use_density:
        e = [exposure[key] for key in keys]
        alpha, beta = _gamma_prior(k, e)

    items = []
    for i, r in enumerate(rows):
        post_a, post_b = k[i] + a, n[i] - k[i] + b
        item: dict[str, Any] = {
            "key": keys[i],
            "label": keys[i].capitalize() if dimension == "activity" else keys[i],
            "total_reports": n[i],
            "sif_potential_reports": k[i],
            "sif_events": int(r[3] or 0),
            "high_priority": int(r[4] or 0),
            "mean_priority": round(float(r[5] or 0), 1),
            "raw_rate": round(k[i] / n[i], 4) if n[i] else None,
            "eb_rate": round(post_a / (post_a + post_b), 4),
            "eb_rate_ci90": [round(float(stats.beta.ppf(0.05, post_a, post_b)), 4), round(float(stats.beta.ppf(0.95, post_a, post_b)), 4)],
            "raw_precursor_count": k[i],
        }
        if dimension == "location":
            item["site"] = r[6]
        if use_density:
            ga, gb = k[i] + alpha, e[i] + beta
            item["exposure_hours"] = round(e[i] * HOURS_UNIT)
            item["raw_density"] = round(k[i] / e[i], 3) if e[i] else None
            item["eb_density"] = round(ga / gb, 3)
            item["eb_density_ci90"] = [round(float(stats.gamma.ppf(0.05, ga, scale=1 / gb)), 3), round(float(stats.gamma.ppf(0.95, ga, scale=1 / gb)), 3)]
            item["adjusted_score"] = item["eb_density"]
        else:
            item["raw_density"] = None
            item["eb_density"] = None
            item["adjusted_score"] = round(item["eb_rate"] * 100, 2)
        notes = []
        if n[i] < 8:
            notes.append("Small sample - shrunk strongly toward the dataset mean")
        item["notes"] = notes
        items.append(item)

    items.sort(key=lambda x: (-x["adjusted_score"], -x["sif_potential_reports"]))
    for i, it in enumerate(items, start=1):
        it["rank"] = i
        it["raw_rank"] = sorted(items, key=lambda x: -x["raw_precursor_count"]).index(it) + 1
    if items and items[0]["sif_potential_reports"] > 0:
        items[0]["notes"].insert(0, TOP_NOTE)
    total_n, total_k = sum(n), sum(k)
    method = {
        "score": "EB-adjusted SIF-precursor density per 100k work-hours" if use_density else "EB-adjusted SIF-potential rate (%)",
        "rate_prior": {"alpha": round(a, 3), "beta": round(b, 3), "dataset_rate": round(total_k / total_n, 4) if total_n else None},
        "exposure_note": "Exposure hours are SYNTHETIC demo denominators, scaled to the selected window." if use_density else "No exposure denominator for this dimension - rate per report is used.",
        "definition": "SIF precursor = report classified PSIF or Exposure (SIF-potential), after any human review.",
    }
    if use_density:
        method["density_prior"] = {"alpha": round(alpha, 3), "beta": round(beta, 3)}
    return {"dimension": dimension, "days": days, "items": items[:limit] if limit else items, "method": method}
