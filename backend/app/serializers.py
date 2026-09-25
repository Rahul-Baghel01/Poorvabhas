"""Model -> JSON serialisers shared by routers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Entity, EvidenceSpan, Pattern, PatternReport, Report, ReportAnalysis, ReviewDecision, ReviewItem, RuleMapping, User
from app.nlp.iogp import CROSSWALK_DISCLAIMER, CROSSWALK_LABEL, DEFAULT_RULES
from app.nlp.scl import SCL_DESCRIPTIONS, SCL_LABELS
from app.nlp.scoring import REVIEW_CATEGORIES

LSR_NAMES = {r["code"]: r["name"] for r in DEFAULT_RULES}


def user_out(u: User) -> dict[str, Any]:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email, "role": u.role.name, "role_label": u.role.label, "permissions": u.role.permissions}


def report_row(r: Report) -> dict[str, Any]:
    return {
        "id": r.id,
        "report_id": r.report_id,
        "report_type": r.report_type,
        "date": r.date.isoformat(),
        "site": r.site.name,
        "site_code": r.site.code,
        "location": r.location,
        "activity": r.activity,
        "equipment": r.equipment,
        "description": r.description,
        "status": r.status,
        "scl_class": r.scl_class,
        "scl_label": SCL_LABELS.get(r.scl_class or "", r.scl_class),
        "sif_potential": r.sif_potential,
        "sif_signal": r.sif_signal,
        "primary_lsr": r.primary_lsr,
        "lsr_name": LSR_NAMES.get(r.primary_lsr or "", r.primary_lsr),
        "priority_score": r.priority_score,
        "priority_level": r.priority_level,
        "confidence": r.confidence,
        "decision_source": r.decision_source,
        "data_source": r.data_source,
    }


def audit_out(a: AuditLog) -> dict[str, Any]:
    return {"id": a.id, "event_type": a.event_type, "entity_type": a.entity_type, "entity_id": a.entity_id, "actor": a.actor_name, "summary": a.summary, "details": a.details, "created_at": a.created_at.isoformat()}


def decision_out(d: ReviewDecision) -> dict[str, Any]:
    return {"id": d.id, "action": d.action, "original_prediction": d.original_prediction, "decision": d.decision, "reviewer": d.reviewer_name, "reason": d.reason, "note": d.note, "created_at": d.created_at.isoformat()}


def review_item_out(it: ReviewItem, analysis: ReportAnalysis | None = None, include_evidence: bool = True) -> dict[str, Any]:
    r = it.report
    out: dict[str, Any] = {
        "id": it.id,
        "category": it.category,
        "category_label": REVIEW_CATEGORIES.get(it.category, it.category),
        "reasons": [{**x, "label": REVIEW_CATEGORIES.get(x.get("code", ""), x.get("code"))} for x in it.reasons],
        "suggested_action": it.suggested_action,
        "status": it.status,
        "source": it.source,
        "requested_by": it.requested_by,
        "priority_score": it.priority_score,
        "created_at": it.created_at.isoformat(),
        "closed_at": it.closed_at.isoformat() if it.closed_at else None,
        "report": report_row(r),
    }
    if include_evidence and analysis is not None:
        ext = analysis.extraction or {}
        scl = ext.get("scl") or {}
        mapping = ext.get("mapping") or {}
        out["analysis"] = {
            "confidence": analysis.confidence,
            "confidence_level": analysis.confidence_level,
            "ml_probability": analysis.ml_probability,
            "scl_class": analysis.scl_class,
            "scl_candidates": analysis.scl_candidates,
            "sif_signal": analysis.sif_signal,
            "gates": scl.get("gates", []),
            "suggested_lsr": mapping.get("primary"),
            "secondary_lsr": mapping.get("secondary", []),
            "reasoning_summary": analysis.reasoning_summary,
        }
    return out


def report_detail(db: Session, r: Report) -> dict[str, Any]:
    a = db.get(ReportAnalysis, r.current_analysis_id) if r.current_analysis_id else None
    out: dict[str, Any] = {
        "report": {**report_row(r), "worker_role": r.worker_role, "contractor": r.contractor, "injury_severity": r.injury_severity, "shift": r.shift, "weather": r.weather, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(), "is_synthetic": r.data_source == "synthetic_demo"},
        "analysis": None,
    }
    if a:
        ents = db.scalars(select(Entity).where(Entity.analysis_id == a.id)).all()
        spans = db.scalars(select(EvidenceSpan).where(EvidenceSpan.analysis_id == a.id)).all()
        by_ent: dict[int, list[EvidenceSpan]] = {}
        for s in spans:
            if s.entity_id:
                by_ent.setdefault(s.entity_id, []).append(s)
        ext = a.extraction or {}
        mappings = db.scalars(select(RuleMapping).where(RuleMapping.analysis_id == a.id).order_by(RuleMapping.rank)).all()
        out["analysis"] = {
            "id": a.id,
            "model_version": a.model_version,
            "created_at": a.created_at.isoformat(),
            "entities": [
                {"id": e.id, "entity_type": e.entity_type, "value": e.value, "canonical": e.canonical, "polarity": e.polarity, "confidence": e.confidence, "source": e.source,
                 "evidence": [{"text": s.text, "start": s.start_offset, "end": s.end_offset, "confidence": s.confidence, "source": s.source} for s in by_ent.get(e.id, [])]}
                for e in ents
            ],
            "not_stated": ext.get("not_stated", []),
            "features": ext.get("features", {}),
            "scl": {**(ext.get("scl") or {}), "scl_description": SCL_DESCRIPTIONS.get(a.scl_class, "")},
            "sif_potential": a.sif_potential,
            "sif_signal": a.sif_signal,
            "mapping": {**(ext.get("mapping") or {}), "label": CROSSWALK_LABEL, "disclaimer": CROSSWALK_DISCLAIMER},
            "mapping_rows": [{"rule_code": m.rule_code, "name": LSR_NAMES.get(m.rule_code, m.rule_code), "rank": m.rank, "is_primary": m.is_primary, "score": m.score, "confidence": m.confidence} for m in mappings],
            "priority_score": a.priority_score,
            "priority_level": a.priority_level,
            "priority_breakdown": a.priority_breakdown,
            "confidence": a.confidence,
            "confidence_level": a.confidence_level,
            "confidence_breakdown": a.confidence_breakdown,
            "ml_probability": a.ml_probability,
            "ml_model_version": a.ml_model_version,
            "ml_explanation": a.ml_explanation,
            "reasoning_summary": a.reasoning_summary,
            "pipeline_trace": a.pipeline_trace,
            "review_reasons": [{**x, "label": REVIEW_CATEGORIES.get(x.get("code", ""), x.get("code"))} for x in a.review_reasons],
            "context": ext.get("context", {}),
        }
    open_item = db.scalars(select(ReviewItem).where(ReviewItem.report_id == r.id, ReviewItem.status == "OPEN")).first()
    out["review"] = review_item_out(open_item, a, include_evidence=False) if open_item else None
    out["decisions"] = [decision_out(d) for d in db.scalars(select(ReviewDecision).where(ReviewDecision.report_id == r.id).order_by(ReviewDecision.created_at.desc())).all()]
    out["audit"] = [audit_out(x) for x in db.scalars(select(AuditLog).where(AuditLog.entity_type == "report", AuditLog.entity_id == r.report_id).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(50)).all()]
    pats = db.execute(select(Pattern).join(PatternReport, PatternReport.pattern_id == Pattern.id).where(PatternReport.report_id == r.id, Pattern.is_current.is_(True))).scalars().all()
    out["patterns"] = [{"id": p.id, "code": p.pattern_code, "name": p.name, "occurrences": p.occurrences, "trend": p.trend} for p in pats]
    out["analysis_count"] = db.query(ReportAnalysis).filter(ReportAnalysis.report_id == r.id).count()
    return out
