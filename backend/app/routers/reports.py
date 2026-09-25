from __future__ import annotations

import re
from datetime import date

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.audit import log_event
from app.db import get_db, is_postgres
from app.models import Embedding, Report, Site, User
from app.nlp.pipeline import ValidationError
from app.nlp.vocabulary import INJURY_SEVERITIES, REPORT_TYPES
from app.security import require_permission
from app.serializers import report_detail, report_row
from app.services.analysis_service import analyze_and_store
from app.services.import_service import get_or_create_site
from app.services.review_service import ReviewError, request_review, submit_decision

router = APIRouter(prefix="/api/reports", tags=["reports"])

SORTS = {
    "date_desc": Report.date.desc(),
    "date_asc": Report.date.asc(),
    "priority_desc": Report.priority_score.desc().nulls_last(),
    "priority_asc": Report.priority_score.asc().nulls_last(),
    "confidence_asc": Report.confidence.asc().nulls_last(),
    "report_id": Report.report_id.asc(),
}


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports")),
    search: str | None = Query(None, max_length=200),
    report_type: str | None = None,
    site: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sif_signal: str | None = None,
    priority: str | None = None,
    scl_class: str | None = None,
    lsr: str | None = None,
    status: str | None = None,
    activity: str | None = None,
    location: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: str = "date_desc",
):
    q = select(Report).join(Site, Site.id == Report.site_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Report.report_id.ilike(like), Site.name.ilike(like), Report.location.ilike(like), Report.activity.ilike(like), Report.equipment.ilike(like), Report.description.ilike(like)))
    filters = {
        Report.report_type: report_type, Site.name: site, Report.sif_signal: sif_signal, Report.priority_level: priority,
        Report.scl_class: scl_class, Report.primary_lsr: lsr, Report.status: status, Report.location: location,
    }
    for col, val in filters.items():
        if val:
            vals = [v for v in val.split(",") if v]
            q = q.where(col.in_(vals))
    if activity:
        q = q.where(func.lower(Report.activity).in_([a.lower() for a in activity.split(",")]))
    if date_from:
        q = q.where(Report.date >= date_from)
    if date_to:
        q = q.where(Report.date <= date_to)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    q = q.order_by(SORTS.get(sort, Report.date.desc()), Report.id.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [report_row(r) for r in db.scalars(q).unique().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/facets")
def facets(db: Session = Depends(get_db), _: User = Depends(require_permission("reports"))):
    sites = db.scalars(select(Site).order_by(Site.name)).all()
    acts = db.scalars(select(Report.activity).distinct().order_by(Report.activity)).all()
    return {
        "report_types": list(REPORT_TYPES),
        "injury_severities": list(INJURY_SEVERITIES),
        "sites": [{"code": s.code, "name": s.name, "is_synthetic": s.is_synthetic} for s in sites],
        "activities": sorted({a.capitalize() for a in acts}),
        "sif_signals": ["SIF_EVENT", "SIF_POTENTIAL", "NON_SIF", "UNDETERMINED"],
        "priority_levels": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        "scl_classes": ["HSIF", "PSIF", "EXPOSURE", "CAPACITY", "SUCCESS", "LSIF", "LOW_SEVERITY", "UNDETERMINED"],
        "statuses": ["AI_ANALYZED", "REVIEW_REQUIRED", "HUMAN_CONFIRMED", "HUMAN_REJECTED"],
    }


class ReportIn(BaseModel):
    report_id: str | None = Field(None, max_length=40)
    report_type: str
    date: date
    site: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=160)
    activity: str = Field(min_length=1, max_length=120)
    equipment: str | None = Field(None, max_length=160)
    description: str = Field(min_length=15, max_length=5000)
    worker_role: str | None = Field(None, max_length=120)
    contractor: str | None = Field(None, max_length=120)
    injury_severity: str | None = Field(None, max_length=60)
    shift: str | None = Field(None, max_length=30)
    weather: str | None = Field(None, max_length=60)

    @field_validator("report_type")
    @classmethod
    def _rt(cls, v: str) -> str:
        if v not in REPORT_TYPES:
            raise ValueError(f"must be one of {', '.join(REPORT_TYPES)}")
        return v

    @field_validator("date")
    @classmethod
    def _d(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date cannot be in the future")
        return v

    @field_validator("report_id")
    @classmethod
    def _rid(cls, v: str | None) -> str | None:
        if v and not re.fullmatch(r"[A-Za-z0-9_\-/.]{3,40}", v.strip()):
            raise ValueError("3-40 characters: letters, digits, - _ / .")
        return v.strip() if v else None


def _next_report_id(db: Session) -> str:
    year = date.today().year
    prefix = f"RPT-{year}-"
    existing = db.scalars(select(Report.report_id).where(Report.report_id.like(prefix + "%"))).all()
    nums = [int(x[len(prefix):]) for x in existing if x[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1:04d}"


@router.post("", status_code=201)
def create_report(body: ReportIn, db: Session = Depends(get_db), user: User = Depends(require_permission("reports"))):
    rid = body.report_id or _next_report_id(db)
    if db.scalars(select(Report).where(Report.report_id == rid)).first():
        raise HTTPException(409, f"Report {rid} already exists")
    site = get_or_create_site(db, body.site)
    r = Report(report_id=rid, report_type=body.report_type, date=body.date, site_id=site.id, location=body.location.strip(), activity=body.activity.strip(), equipment=(body.equipment or "").strip() or None,
               description=body.description.strip(), worker_role=body.worker_role, contractor=body.contractor, injury_severity=body.injury_severity, shift=body.shift, weather=body.weather, data_source="manual", created_by=user.id, status="PENDING")
    db.add(r)
    db.flush()
    log_event(db, "REPORT_CREATED", f"{rid} created by {user.full_name}", entity_type="report", entity_id=rid, actor=user)
    try:
        _, out = analyze_and_store(db, r, actor=user, reason="new report")
    except ValidationError as e:
        db.rollback()
        raise HTTPException(422, str(e))
    db.commit()
    db.refresh(r)
    return {"report_id": rid, "trace": out.trace, "detail": report_detail(db, r)}


def _get(db: Session, report_id: str) -> Report:
    r = db.scalars(select(Report).where(Report.report_id == report_id)).first()
    if not r:
        raise HTTPException(404, f"Report {report_id} not found")
    return r


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("reports"))):
    return report_detail(db, _get(db, report_id))


@router.get("/{report_id}/similar")
def similar_reports(report_id: str, k: int = Query(5, ge=1, le=20), db: Session = Depends(get_db), _: User = Depends(require_permission("reports"))):
    r = _get(db, report_id)
    emb = db.scalars(select(Embedding).where(Embedding.report_id == r.id)).first()
    if not emb:
        return {"items": [], "method": "unavailable", "note": "No embedding stored for this report"}
    method = "numpy cosine"
    ids_scores: list[tuple[int, float]] = []
    if is_postgres():
        try:
            rows = db.execute(text("SELECT report_id, 1 - (vector <=> (SELECT vector FROM embeddings WHERE report_id = :rid)) AS sim FROM embeddings WHERE report_id != :rid ORDER BY vector <=> (SELECT vector FROM embeddings WHERE report_id = :rid) LIMIT :k"), {"rid": r.id, "k": k}).all()
            ids_scores = [(int(a), float(b)) for a, b in rows]
            method = "pgvector cosine distance"
        except Exception:
            db.rollback()
            ids_scores = []
    if not ids_scores:
        allv = db.execute(select(Embedding.report_id, Embedding.vector).where(Embedding.report_id != r.id)).all()
        if allv:
            M = np.array([v for _, v in allv])
            sims = M @ np.array(emb.vector)
            top = np.argsort(-sims)[:k]
            ids_scores = [(allv[i][0], float(sims[i])) for i in top]
    reports = {x.id: x for x in db.scalars(select(Report).where(Report.id.in_([i for i, _ in ids_scores]))).all()}
    return {"method": method, "embedding_model": emb.model, "items": [{**report_row(reports[i]), "similarity": round(s, 3)} for i, s in ids_scores if i in reports]}


@router.post("/{report_id}/reanalyze")
def reanalyze(report_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("analysis"))):
    r = _get(db, report_id)
    _, out = analyze_and_store(db, r, actor=user, reason="manual re-analysis")
    db.commit()
    return {"trace": out.trace, "detail": report_detail(db, r)}


class ReviewRequestIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/{report_id}/request-review")
def send_to_review(report_id: str, body: ReviewRequestIn, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))):
    r = _get(db, report_id)
    item = request_review(db, r, user, body.reason)
    db.commit()
    return {"review_id": item.id, "detail": report_detail(db, r)}


class DecisionIn(BaseModel):
    action: str
    scl_class: str | None = None
    sif_potential: bool | None = None
    primary_lsr: str | None = None
    reason: str | None = Field(None, max_length=2000)
    note: str | None = Field(None, max_length=4000)


@router.post("/{report_id}/decision")
def decide(report_id: str, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))):
    r = _get(db, report_id)
    try:
        submit_decision(db, r, user, body.action, scl_class=body.scl_class, sif_potential=body.sif_potential, primary_lsr=body.primary_lsr, reason=body.reason, note=body.note)
    except ReviewError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return report_detail(db, r)
