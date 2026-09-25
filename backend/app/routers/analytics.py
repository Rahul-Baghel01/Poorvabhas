from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.dashboard import summary
from app.analytics.patterns import mine_patterns
from app.analytics.ranking import rank
from app.db import get_db
from app.models import Pattern, PatternReport, Report, User
from app.security import require_permission
from app.serializers import LSR_NAMES, report_row

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/dashboard")
def dashboard(days: int = Query(90, ge=7, le=3650), db: Session = Depends(get_db), _: User = Depends(require_permission("dashboard"))):
    return summary(db, days)


@router.get("/ranking")
def ranking(dimension: str = Query("site", pattern="^(site|activity|location)$"), days: int | None = Query(90, ge=7, le=3650), db: Session = Depends(get_db), _: User = Depends(require_permission("dashboard"))):
    return rank(db, dimension, days)


def pattern_out(p: Pattern) -> dict:
    return {
        "id": p.id, "code": p.pattern_code, "name": p.name, "method": p.method, "signature": p.signature, "occurrences": p.occurrences, "sif_occurrences": p.sif_occurrences,
        "sites": p.sites, "locations": p.locations, "activities": p.activities, "barriers": p.barriers, "energy_sources": p.energy_sources,
        "associated_lsr": p.associated_lsr, "primary_lsr": p.primary_lsr, "lsr_name": LSR_NAMES.get(p.primary_lsr or "", p.primary_lsr),
        "trend": p.trend, "trend_detail": p.trend_detail, "cohesion": p.cohesion, "confidence": p.confidence,
        "first_seen": p.first_seen.isoformat() if p.first_seen else None, "last_seen": p.last_seen.isoformat() if p.last_seen else None, "run_id": p.run_id, "created_at": p.created_at.isoformat(),
    }


@router.get("/patterns")
def patterns(db: Session = Depends(get_db), _: User = Depends(require_permission("patterns"))):
    rows = db.scalars(select(Pattern).where(Pattern.is_current.is_(True)).order_by(Pattern.occurrences.desc())).all()
    return {"items": [pattern_out(p) for p in rows], "method": rows[0].method if rows else None, "run_id": rows[0].run_id if rows else None, "mined_at": rows[0].created_at.isoformat() if rows else None}


@router.get("/patterns/{pattern_id}")
def pattern_detail(pattern_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("patterns"))):
    p = db.get(Pattern, pattern_id)
    if not p:
        raise HTTPException(404, "Pattern not found")
    members = db.execute(select(Report, PatternReport.membership).join(PatternReport, PatternReport.report_id == Report.id).where(PatternReport.pattern_id == p.id).order_by(Report.date.desc())).all()
    return {**pattern_out(p), "reports": [{**report_row(r), "membership": m} for r, m in members]}


@router.post("/patterns/mine")
def mine(db: Session = Depends(get_db), user: User = Depends(require_permission("patterns"))):
    result = mine_patterns(db, actor=user)
    db.commit()
    return result
