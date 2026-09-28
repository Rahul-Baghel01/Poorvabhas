"""Command-centre aggregates. Every number is computed from the database at request time."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.ranking import rank
from app.models import Pattern, Report, ReviewItem, Site
from app.nlp.iogp import DEFAULT_RULES, FALLBACK_CODE

LSR_NAMES = {r["code"]: r["name"] for r in DEFAULT_RULES}
SIF_SIGNALS = ("SIF_POTENTIAL", "SIF_EVENT")


def _window(q, start: date, end: date):
    return q.where(Report.date > start, Report.date <= end)


def _pct_change(cur: int, prev: int) -> float | None:
    if prev == 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def summary(db: Session, days: int = 90, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    start = today - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    def counts(s: date, e: date) -> dict[str, int]:
        row = db.execute(_window(select(
            func.count(Report.id),
            func.sum(case((Report.sif_potential.is_(True), 1), else_=0)),
            func.sum(case((Report.sif_signal == "SIF_EVENT", 1), else_=0)),
            func.sum(case((Report.sif_signal.in_(SIF_SIGNALS) & Report.priority_level.in_(["CRITICAL", "HIGH"]), 1), else_=0)),
            func.sum(case((Report.sif_signal.in_(SIF_SIGNALS), 1), else_=0)),
            func.sum(case((Report.sif_signal.in_(SIF_SIGNALS) & (Report.primary_lsr != FALLBACK_CODE), 1), else_=0)),
            func.sum(case((Report.sif_signal == "UNDETERMINED", 1), else_=0)),
            func.sum(case((Report.status == "HUMAN_CONFIRMED", 1), else_=0)),
            func.sum(case((Report.status == "HUMAN_REJECTED", 1), else_=0)),
        ), s, e)).one()
        return {"total": int(row[0] or 0), "sif_potential": int(row[1] or 0), "sif_events": int(row[2] or 0), "high_priority": int(row[3] or 0), "sif_signals": int(row[4] or 0), "sif_mapped": int(row[5] or 0), "undetermined": int(row[6] or 0),
                "expert_confirmed": int(row[7] or 0), "expert_corrected": int(row[8] or 0)}

    cur = counts(start, today)
    prev = counts(prev_start, start)

    open_reviews = db.scalar(select(func.count(ReviewItem.id)).where(ReviewItem.status == "OPEN")) or 0
    patterns = db.scalars(select(Pattern).where(Pattern.is_current.is_(True)).order_by(Pattern.occurrences.desc())).all()
    awaiting = db.scalar(_window(select(func.count(Report.id)).where(
        Report.sif_signal.in_(SIF_SIGNALS), Report.priority_level.in_(["CRITICAL", "HIGH"]), Report.decision_source != "HUMAN"), start, today)) or 0
    rules_seen = db.scalars(_window(select(Report.primary_lsr).where(Report.sif_signal.in_(SIF_SIGNALS), Report.primary_lsr != FALLBACK_CODE).distinct(), start, today)).all()

    # distribution
    dist_rows = db.execute(_window(select(Report.sif_signal, func.count(Report.id)).group_by(Report.sif_signal), start, today)).all()
    scl_rows = db.execute(_window(select(Report.scl_class, func.count(Report.id)).group_by(Report.scl_class), start, today)).all()

    # time series (weekly buckets ending today)
    n_weeks = max(1, (days + 6) // 7)
    first = today - timedelta(days=n_weeks * 7 - 1)
    ts_rows = db.execute(select(Report.date, Report.sif_signal).where(Report.date >= first, Report.date <= today)).all()
    series = [{"week_start": (first + timedelta(days=7 * i)).isoformat(), "total": 0, "sif": 0} for i in range(n_weeks)]
    for d, sig in ts_rows:
        i = (d - first).days // 7
        if 0 <= i < n_weeks:
            series[i]["total"] += 1
            series[i]["sif"] += sig in SIF_SIGNALS

    lsr_rows = db.execute(_window(select(Report.primary_lsr, func.count(Report.id)).where(Report.sif_signal.in_(SIF_SIGNALS)).group_by(Report.primary_lsr), start, today)).all()
    act_rows = db.execute(_window(select(func.lower(Report.activity), func.count(Report.id), func.sum(case((Report.sif_signal.in_(SIF_SIGNALS), 1), else_=0))).group_by(func.lower(Report.activity)), start, today)).all()
    site_rows = db.execute(_window(select(Site.name, func.count(Report.id), func.sum(case((Report.sif_signal.in_(SIF_SIGNALS), 1), else_=0))).join(Site, Site.id == Report.site_id).group_by(Site.name), start, today)).all()

    queue = db.execute(select(ReviewItem, Report).join(Report, Report.id == ReviewItem.report_id).where(ReviewItem.status == "OPEN").order_by(ReviewItem.priority_score.desc()).limit(6)).all()

    return {
        "window": {"days": days, "start": start.isoformat(), "end": today.isoformat()},
        "kpis": {
            "total_reports": {"value": cur["total"], "previous": prev["total"], "change_pct": _pct_change(cur["total"], prev["total"])},
            "sif_potential_reports": {"value": cur["sif_potential"], "previous": prev["sif_potential"], "change_pct": _pct_change(cur["sif_potential"], prev["sif_potential"]), "sif_events": cur["sif_events"], "share": round(cur["sif_potential"] / cur["total"], 4) if cur["total"] else None},
            "recurring_patterns": {"value": len(patterns), "increasing": sum(1 for p in patterns if p.trend == "INCREASING")},
            "review_queue": {"value": int(open_reviews)},
            "high_priority_signals": {"value": cur["high_priority"], "previous": prev["high_priority"], "change_pct": _pct_change(cur["high_priority"], prev["high_priority"])},
            "expert_reviewed": {"value": cur["expert_confirmed"] + cur["expert_corrected"], "confirmed": cur["expert_confirmed"], "corrected": cur["expert_corrected"]},
            "lsr_coverage": {"value": round(cur["sif_mapped"] / cur["sif_signals"], 4) if cur["sif_signals"] else None, "mapped": cur["sif_mapped"], "sif_signals": cur["sif_signals"], "rules_observed": len(rules_seen), "rules_total": 9},
        },
        "priority_banner": {"awaiting_human_validation": int(awaiting), "text": f"{awaiting} high-priority SIF-potential or SIF Event report{'s' if awaiting != 1 else ''} in the last {days} days {'have' if awaiting != 1 else 'has'} not yet been validated by an HSE reviewer" if awaiting else None},
        "sif_distribution": [{"signal": s or "PENDING", "count": c} for s, c in dist_rows],
        "scl_distribution": [{"scl_class": s or "PENDING", "count": c} for s, c in scl_rows],
        "reports_over_time": series,
        "top_lsr": sorted([{"code": c, "name": LSR_NAMES.get(c, c), "count": n} for c, n in lsr_rows if c], key=lambda x: -x["count"]),
        "top_activities": sorted([{"activity": a.capitalize(), "total": t, "sif": int(s or 0)} for a, t, s in act_rows], key=lambda x: (-x["sif"], -x["total"]))[:8],
        "top_sites": sorted([{"site": a, "total": t, "sif": int(s or 0)} for a, t, s in site_rows], key=lambda x: (-x["sif"], -x["total"])),
        "patterns": [{"id": p.id, "code": p.pattern_code, "name": p.name, "occurrences": p.occurrences, "trend": p.trend, "primary_lsr": p.primary_lsr, "lsr_name": LSR_NAMES.get(p.primary_lsr or "", p.primary_lsr), "sites": [s["name"] for s in p.sites[:3]], "activities": [a["name"] for a in (p.activities or [])[:2]], "counts": (p.trend_detail or {}).get("counts", [])} for p in patterns[:6]],
        "review_queue": [{"review_id": it.id, "report_id": r.report_id, "category": it.category, "priority_score": it.priority_score, "activity": r.activity, "site": r.site.name, "scl_class": r.scl_class, "sif_signal": r.sif_signal} for it, r in queue],
        "site_ranking": rank(db, "site", days, today, limit=8),
    }
