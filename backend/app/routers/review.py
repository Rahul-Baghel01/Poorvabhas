from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Report, ReportAnalysis, ReviewItem, User
from app.nlp.scoring import REVIEW_CATEGORIES
from app.routers.reports import DecisionIn
from app.security import require_permission
from app.serializers import review_item_out
from app.services.review_service import ReviewError, submit_decision

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("")
def list_queue(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("review")),
    category: str | None = None,
    status: str = "OPEN",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = "priority",
):
    q = select(ReviewItem).where(ReviewItem.status == status)
    if category:
        q = q.where(ReviewItem.category == category)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    order = ReviewItem.priority_score.desc() if sort == "priority" else ReviewItem.created_at.desc() if sort == "newest" else ReviewItem.created_at.asc()
    items = db.scalars(q.order_by(order, ReviewItem.id).offset((page - 1) * page_size).limit(page_size)).unique().all()
    analyses = {a.id: a for a in db.scalars(select(ReportAnalysis).where(ReportAnalysis.id.in_([i.report.current_analysis_id for i in items if i.report.current_analysis_id]))).all()}
    return {"items": [review_item_out(i, analyses.get(i.report.current_analysis_id)) for i in items], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(require_permission("review"))):
    rows = db.execute(select(ReviewItem.category, func.count(ReviewItem.id)).where(ReviewItem.status == "OPEN").group_by(ReviewItem.category)).all()
    counts = {c: n for c, n in rows}
    closed = db.scalar(select(func.count(ReviewItem.id)).where(ReviewItem.status == "CLOSED")) or 0
    human = db.execute(select(Report.status, func.count(Report.id)).where(Report.decision_source == "HUMAN").group_by(Report.status)).all()
    return {
        "open": sum(counts.values()),
        "closed": closed,
        "categories": [{"code": c, "label": REVIEW_CATEGORIES[c], "count": counts.get(c, 0)} for c in ["LOW_CONFIDENCE", "BORDERLINE", "INSUFFICIENT_INFORMATION", "RULE_CONFLICT", "MODEL_RULE_DISAGREEMENT", "MANUAL_REQUEST"]],
        "human_decisions": {s: n for s, n in human},
    }


@router.post("/{review_id}/decision")
def decide(review_id: int, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))):
    item = db.get(ReviewItem, review_id)
    if not item:
        raise HTTPException(404, "Review item not found")
    if item.status != "OPEN" and body.action.upper() != "NOTE":
        raise HTTPException(409, "Review item is already closed")
    try:
        d = submit_decision(db, item.report, user, body.action, scl_class=body.scl_class, sif_potential=body.sif_potential, primary_lsr=body.primary_lsr, reason=body.reason, note=body.note, review_id=item.id)
    except ReviewError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"decision_id": d.id, "report_id": item.report.report_id, "status": item.report.status, "review_status": item.status}
