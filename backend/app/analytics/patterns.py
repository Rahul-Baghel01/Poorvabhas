"""Engine 4 - recurring precursor pattern mining.

Precursor reports (SIF signal or a failed control) are encoded as binary feature sets
(activity, failed barrier, energy source, Life-Saving Rule) and clustered with HDBSCAN
over Jaccard distance. Each cluster is described by the features shared by most of its
members. If HDBSCAN is unavailable or finds nothing, deterministic frequency grouping of
(activity, failed barrier, energy) combinations is used instead. Nothing is hardcoded.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.analytics.trend import detect_trend
from app.audit import log_event
from app.models import Pattern, PatternReport, Report, ReportAnalysis, Site, User
from app.nlp.iogp import DEFAULT_RULES
from app.services.settings_service import get_setting

LSR_NAMES = {r["code"]: r["name"] for r in DEFAULT_RULES}


def _precursor_rows(db: Session) -> list[dict[str, Any]]:
    q = select(Report, ReportAnalysis, Site).join(ReportAnalysis, ReportAnalysis.id == Report.current_analysis_id).join(Site, Site.id == Report.site_id)
    rows = []
    for r, a, s in db.execute(q).all():
        f = (a.extraction or {}).get("features") or {}
        failed = f.get("failed_barriers") or []
        # precursor = SIF signal, or an unresolved case where a direct control failed
        is_precursor = r.sif_signal in ("SIF_POTENTIAL", "SIF_EVENT") or (r.sif_signal == "UNDETERMINED" and a.control_present == "NO")
        if not is_precursor:
            continue
        rows.append({
            "id": r.id, "report_id": r.report_id, "date": r.date, "site": s.name, "location": r.location, "sif": r.sif_signal in ("SIF_POTENTIAL", "SIF_EVENT"),
            "activity": f.get("activity"), "barriers": failed, "energies": f.get("energies") or [], "lsr": r.primary_lsr, "description": r.description, "priority": r.priority_score or 0,
        })
    return rows


def _tokens(row: dict[str, Any]) -> set[str]:
    t = set()
    if row["activity"]:
        t.add("act:" + row["activity"])
    t |= {"bar:" + b for b in row["barriers"]}
    t |= {"en:" + e for e in row["energies"]}
    if row["lsr"]:
        t.add("lsr:" + row["lsr"])
    return t


def _signature(members: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(members)

    def modal(values: list[str], thresh: float) -> str | None:
        if not values:
            return None
        v, c = Counter(values).most_common(1)[0]
        return v if c / n >= thresh else None

    return {
        "activity": modal([m["activity"] for m in members if m["activity"]], 0.6),
        "barrier": modal([b for m in members for b in m["barriers"]], 0.5),
        "energy": modal([e for m in members for e in m["energies"]], 0.5),
        "lsr": modal([m["lsr"] for m in members if m["lsr"]], 0.6),
    }


def _cohesion(members: list[dict[str, Any]], sig: dict[str, Any]) -> float:
    parts = [(k, v) for k, v in sig.items() if v]
    if not parts:
        return 0.0
    score = 0.0
    for m in members:
        hit = 0
        for k, v in parts:
            have = {"activity": [m["activity"]], "barrier": m["barriers"], "energy": m["energies"], "lsr": [m["lsr"]]}[k]
            hit += v in have
        score += hit / len(parts)
    return score / len(members)


def _name(sig: dict[str, Any]) -> str:
    bits = []
    if sig.get("activity"):
        bits.append(sig["activity"].capitalize())
    if sig.get("barrier"):
        bits.append(f"{sig['barrier']} failure")
    if sig.get("energy"):
        bits.append(sig["energy"])
    if len(bits) < 2 and sig.get("lsr"):
        bits.append(LSR_NAMES.get(sig["lsr"], sig["lsr"]))
    name = " + ".join(bits)
    return name[:1].upper() + name[1:]


def _hdbscan_clusters(rows: list[dict[str, Any]], min_cluster_size: int) -> list[tuple[list[int], list[float]]]:
    from sklearn.cluster import HDBSCAN
    from sklearn.metrics import pairwise_distances

    vocab = sorted({t for r in rows for t in _tokens(r)})
    idx = {t: i for i, t in enumerate(vocab)}
    X = np.zeros((len(rows), len(vocab)), dtype=bool)
    for i, r in enumerate(rows):
        for t in _tokens(r):
            X[i, idx[t]] = True
    D = pairwise_distances(X, metric="jaccard")
    model = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=3, metric="precomputed", allow_single_cluster=False, copy=True).fit(D)
    out = []
    for lab in sorted(set(model.labels_) - {-1}):
        members = [i for i, l in enumerate(model.labels_) if l == lab]
        out.append((members, [float(model.probabilities_[i]) for i in members]))
    return out


def _frequency_clusters(rows: list[dict[str, Any]], min_size: int) -> list[tuple[list[int], list[float]]]:
    groups: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        key = (r["activity"], r["barriers"][0] if r["barriers"] else None, r["energies"][0] if r["energies"] else None)
        if sum(x is not None for x in key) >= 2:
            groups.setdefault(key, []).append(i)
    return [(m, [1.0] * len(m)) for m in groups.values() if len(m) >= min_size]


def mine_patterns(db: Session, actor: User | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rows = _precursor_rows(db)
    min_size = int(get_setting(db, "pattern_min_cluster_size"))
    method = "hdbscan"
    clusters: list[tuple[list[int], list[float]]] = []
    if len(rows) >= min_size * 2:
        try:
            clusters = _hdbscan_clusters(rows, min_size)
        except Exception:
            clusters = []
        if not clusters:
            method = "frequency"
            clusters = _frequency_clusters(rows, min_size - 1)

    all_dates = [d for (d,) in db.execute(select(Report.date)).all()]
    start = min(all_dates) if all_dates else today
    end = max(max(all_dates) if all_dates else today, today)

    # merge clusters that resolve to the same signature
    merged: dict[str, tuple[dict[str, Any], dict[int, float]]] = {}
    for members, probs in clusters:
        mrows = [rows[i] for i in members]
        sig = _signature(mrows)
        if sum(1 for v in sig.values() if v) < 2:
            continue
        key = "|".join(str(sig.get(k)) for k in ("activity", "barrier", "energy", "lsr"))
        if key not in merged:
            merged[key] = (sig, {})
        for i, p in zip(members, probs):
            merged[key][1][i] = max(p, merged[key][1].get(i, 0))

    run_id = uuid.uuid4().hex[:12]
    db.execute(update(Pattern).where(Pattern.is_current.is_(True)).values(is_current=False))
    created = []
    ranked = sorted(merged.values(), key=lambda t: -len(t[1]))
    for n, (sig, memb) in enumerate(ranked, start=1):
        mrows = [rows[i] for i in memb]
        if len(mrows) < min_size - 1:
            continue
        coh = _cohesion(mrows, sig)
        trend = detect_trend([m["date"] for m in mrows], start, end)

        def dist(values: list[str]) -> list[dict[str, Any]]:
            return [{"name": k, "count": v} for k, v in Counter(values).most_common()]

        p = Pattern(
            run_id=run_id, pattern_code=f"P-{n:02d}", name=_name(sig), method=method, signature=sig,
            occurrences=len(mrows), sif_occurrences=sum(1 for m in mrows if m["sif"]),
            sites=dist([m["site"] for m in mrows]), locations=dist([m["location"] for m in mrows]),
            activities=dist([m["activity"] or "Not stated" for m in mrows]), barriers=dist([b for m in mrows for b in m["barriers"]]),
            energy_sources=dist([e for m in mrows for e in m["energies"]]),
            associated_lsr=[{"code": k, "name": LSR_NAMES.get(k, k), "count": v} for k, v in Counter(m["lsr"] for m in mrows if m["lsr"]).most_common()],
            primary_lsr=sig.get("lsr") or Counter(m["lsr"] for m in mrows).most_common(1)[0][0],
            trend=trend["trend"], trend_detail=trend, cohesion=round(coh, 3),
            confidence=round(coh * (sum(memb.values()) / len(memb)), 3),
            first_seen=min(m["date"] for m in mrows), last_seen=max(m["date"] for m in mrows), is_current=True,
        )
        db.add(p)
        db.flush()
        for i, prob in memb.items():
            db.add(PatternReport(pattern_id=p.id, report_id=rows[i]["id"], membership=round(prob, 3)))
        created.append(p)
    # renumber by occurrences so P-01 is the largest
    for n, p in enumerate(sorted(created, key=lambda x: -x.occurrences), start=1):
        p.pattern_code = f"P-{n:02d}"
    log_event(db, "PATTERNS_MINED", f"{len(created)} recurring patterns mined from {len(rows)} precursor reports ({method})", entity_type="pattern_run", entity_id=run_id, actor=actor, details={"method": method, "precursor_reports": len(rows)})
    return {"run_id": run_id, "method": method, "patterns": len(created), "precursor_reports": len(rows)}
