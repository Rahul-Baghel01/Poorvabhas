"""Human-in-the-loop review: decisions, feedback examples, manual review requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_event
from app.models import FeedbackExample, Report, ReportAnalysis, ReviewDecision, ReviewItem, User
from app.nlp.iogp import DEFAULT_RULES
from app.nlp.scl import SCL_CLASSES, UNDETERMINED
from app.nlp.scoring import SUGGESTED_ACTIONS
from app.services.analysis_service import STATUS_CONFIRMED, STATUS_REJECTED, STATUS_REVIEW
from app.services.settings_service import get_setting

ACTIONS = ("CONFIRM", "REJECT", "CHANGE", "INSUFFICIENT", "NOTE")
VALID_LSR = {r["code"] for r in DEFAULT_RULES}


class ReviewError(ValueError):
    pass


def derive_signal(scl_class: str | None, sif_potential: bool | None) -> str:
    if scl_class == "HSIF":
        return "SIF_EVENT"
    if sif_potential is True:
        return "SIF_POTENTIAL"
    if sif_potential is False:
        return "NON_SIF"
    return "UNDETERMINED"


def _prediction(analysis: ReportAnalysis | None, report: Report) -> dict[str, Any]:
    if analysis is None:
        return {"scl_class": report.scl_class, "sif_potential": report.sif_potential, "sif_signal": report.sif_signal, "primary_lsr": report.primary_lsr}
    return {
        "analysis_id": analysis.id,
        "scl_class": analysis.scl_class,
        "sif_potential": analysis.sif_potential,
        "sif_signal": analysis.sif_signal,
        "primary_lsr": analysis.primary_lsr,
        "confidence": analysis.confidence,
        "priority_score": analysis.priority_score,
        "ml_probability": analysis.ml_probability,
        "model_version": analysis.model_version,
    }


def submit_decision(db: Session, report: Report, reviewer: User, action: str, *, scl_class: str | None = None, sif_potential: bool | None = None, primary_lsr: str | None = None, reason: str | None = None, note: str | None = None, review_id: int | None = None) -> ReviewDecision:
    action = action.upper()
    if action not in ACTIONS:
        raise ReviewError(f"action must be one of {', '.join(ACTIONS)}")
    if scl_class is not None and scl_class not in (*SCL_CLASSES, UNDETERMINED):
        raise ReviewError("invalid SCL class")
    if primary_lsr is not None and primary_lsr not in VALID_LSR:
        raise ReviewError("invalid Life-Saving Rule code")
    if action == "NOTE" and not (note or "").strip():
        raise ReviewError("a note is required")
    if action in ("REJECT", "CHANGE") and not (reason or "").strip():
        raise ReviewError("a reason is required when rejecting or changing the AI classification")
    if action == "CHANGE" and scl_class is None and sif_potential is None and primary_lsr is None:
        raise ReviewError("CHANGE requires a new SCL class, SIF potential or Life-Saving Rule")

    analysis = db.get(ReportAnalysis, report.current_analysis_id) if report.current_analysis_id else None
    original = _prediction(analysis, report)
    sif_classes = set(get_setting(db, "sif_potential_classes"))

    final_scl = report.scl_class
    final_sif = report.sif_potential
    final_lsr = report.primary_lsr
    status = report.status
    if action == "CONFIRM":
        status = STATUS_CONFIRMED
    elif action == "REJECT":
        final_scl = scl_class or final_scl
        final_sif = sif_potential if sif_potential is not None else (final_scl in sif_classes if scl_class else not bool(final_sif))
        final_lsr = primary_lsr or final_lsr
        status = STATUS_REJECTED
    elif action == "CHANGE":
        if scl_class is not None:
            final_scl = scl_class
            final_sif = (scl_class in sif_classes) if scl_class != UNDETERMINED else None
        if sif_potential is not None:
            final_sif = sif_potential
        if primary_lsr is not None:
            final_lsr = primary_lsr
        status = STATUS_CONFIRMED
    elif action == "INSUFFICIENT":
        final_scl, final_sif = UNDETERMINED, None
        status = STATUS_CONFIRMED

    decision_values = {"scl_class": final_scl, "sif_potential": final_sif, "sif_signal": derive_signal(final_scl, final_sif), "primary_lsr": final_lsr, "status": status}
    item = db.get(ReviewItem, review_id) if review_id else db.scalars(select(ReviewItem).where(ReviewItem.report_id == report.id, ReviewItem.status == "OPEN")).first()

    decision = ReviewDecision(review_id=item.id if item else None, report_id=report.id, action=action, original_prediction=original, decision=decision_values if action != "NOTE" else {}, reviewer_id=reviewer.id, reviewer_name=reviewer.full_name, reason=reason, note=note)
    db.add(decision)
    db.flush()

    if action == "NOTE":
        log_event(db, "REVIEW_STARTED", f"Note added to {report.report_id}", entity_type="report", entity_id=report.report_id, actor=reviewer, details={"note": note})
        return decision

    report.scl_class = final_scl
    report.sif_potential = final_sif
    report.sif_signal = decision_values["sif_signal"]
    report.primary_lsr = final_lsr
    report.status = status
    report.decision_source = "HUMAN"
    if item and item.status == "OPEN":
        item.status = "CLOSED"
        item.closed_at = datetime.now(timezone.utc)

    changed = (original.get("scl_class"), original.get("sif_potential"), original.get("primary_lsr")) != (final_scl, final_sif, final_lsr)
    db.add(FeedbackExample(
        report_id=report.id, decision_id=decision.id, text=report.description,
        label_sif_potential=final_sif, label_scl_class=final_scl, label_lsr=final_lsr,
        predicted_sif_potential=original.get("sif_potential"), predicted_scl_class=original.get("scl_class"), predicted_lsr=original.get("primary_lsr"),
        is_correction=changed,
    ))
    log_event(db, "REVIEW_COMPLETED", f"{report.report_id} {action.lower()} by {reviewer.full_name}" + (" (corrected)" if changed else ""), entity_type="report", entity_id=report.report_id, actor=reviewer,
              details={"action": action, "original": original, "decision": decision_values, "reason": reason, "note": note})
    return decision


def request_review(db: Session, report: Report, user: User, reason: str) -> ReviewItem:
    existing = db.scalars(select(ReviewItem).where(ReviewItem.report_id == report.id, ReviewItem.status == "OPEN")).first()
    if existing:
        existing.reasons = list(existing.reasons) + [{"code": "MANUAL_REQUEST", "detail": reason}]
        return existing
    item = ReviewItem(report_id=report.id, analysis_id=report.current_analysis_id, category="MANUAL_REQUEST", reasons=[{"code": "MANUAL_REQUEST", "detail": reason or "Sent to reviewer"}], suggested_action=SUGGESTED_ACTIONS["MANUAL_REQUEST"], source="MANUAL", requested_by=user.full_name, priority_score=report.priority_score or 0)
    db.add(item)
    report.status = STATUS_REVIEW
    log_event(db, "REVIEW_STARTED", f"{report.report_id} sent to reviewer by {user.full_name}", entity_type="report", entity_id=report.report_id, actor=user, details={"reason": reason})
    return item
