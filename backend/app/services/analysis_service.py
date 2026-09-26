"""Runs the pipeline for a stored report and persists every output with its evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
import logging
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audit import log_event
from app.config import get_settings
from app.models import (
    Embedding,
    Entity,
    EvidenceSpan,
    ModelVersion,
    ModelArtifact,
    Pattern,
    Report,
    ReportAnalysis,
    ReviewItem,
    RuleMapping,
    SCLClassification,
    TaxonomyRule,
    User,
)
from app.nlp.classifier import LSAEmbedder, SafetyClassifier, TfidfLogRegClassifier, build_model_text, load_classifier
from app.nlp.extraction import ExtractionResult
from app.nlp.iogp import MappingResult
from app.nlp.pipeline import AnalysisOutput, AnalysisPipeline, ContextInfo
from app.nlp.scl import SCLResult
from app.nlp.scoring import REVIEW_CATEGORIES, SUGGESTED_ACTIONS
from app.services.settings_service import get_setting

STATUS_AI = "AI_ANALYZED"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_CONFIRMED = "HUMAN_CONFIRMED"
STATUS_REJECTED = "HUMAN_REJECTED"
_db_classifiers: dict[str, SafetyClassifier] = {}
_db_embedders: dict[str, LSAEmbedder] = {}
log = logging.getLogger(__name__)


def rules_from_db(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(TaxonomyRule).order_by(TaxonomyRule.rule_number.is_(None), TaxonomyRule.rule_number)).all()
    return [
        {"code": r.code, "rule_number": r.rule_number, "name": r.name, "keywords": r.keywords, "phrases": r.phrases, "weight": r.weight, "is_active": r.is_active, "is_fallback": r.is_fallback}
        for r in rows
    ]


@lru_cache(maxsize=4)
def _cached_classifier(model_dir: str, artifact_path: str | None) -> SafetyClassifier | None:
    return load_classifier(model_dir, artifact_path)


@lru_cache(maxsize=4)
def _cached_embedder(artifact_path: str) -> LSAEmbedder | None:
    try:
        return LSAEmbedder.load(artifact_path)
    except Exception:
        return None


def active_model(db: Session, component: str) -> ModelVersion | None:
    return db.scalars(select(ModelVersion).where(ModelVersion.component == component, ModelVersion.is_active.is_(True)).order_by(ModelVersion.created_at.desc())).first()


def active_classifier(db: Session) -> SafetyClassifier | None:
    if not get_setting(db, "use_classifier"):
        return None
    mv = active_model(db, "sif_classifier")
    if not mv:
        return None
    local = _cached_classifier(get_settings().model_path, mv.artifact_path)
    if local:
        return local
    if mv.version not in _db_classifiers:
        artifact = db.get(ModelArtifact, mv.version)
        if not artifact:
            return None
        try:
            import joblib

            data = joblib.load(BytesIO(artifact.payload))
            clf = TfidfLogRegClassifier.__new__(TfidfLogRegClassifier)
            clf.version = data["version"]
            clf.vectorizer = data["vectorizer"]
            clf.model = data["model"]
            clf.params = data.get("params", {})
            _db_classifiers[mv.version] = clf
        except Exception:
            log.exception("Classifier artifact %s could not be loaded", mv.version)
            return None
    return _db_classifiers[mv.version]


def active_embedder(db: Session) -> LSAEmbedder | None:
    mv = active_model(db, "embedder")
    if not mv:
        return None
    local = _cached_embedder(mv.artifact_path) if mv.artifact_path else None
    if local:
        return local
    if mv.version not in _db_embedders:
        artifact = db.get(ModelArtifact, mv.version)
        if not artifact:
            return None
        try:
            import joblib

            _db_embedders[mv.version] = joblib.load(BytesIO(artifact.payload))
        except Exception:
            log.exception("Embedder artifact %s could not be loaded", mv.version)
            return None
    return _db_embedders[mv.version]


def build_pipeline(db: Session, classifier: SafetyClassifier | None | bool = True) -> AnalysisPipeline:
    clf = active_classifier(db) if classifier is True else (classifier or None)
    return AnalysisPipeline(
        rules=rules_from_db(db),
        classifier=clf,
        sif_classes=tuple(get_setting(db, "sif_potential_classes")),
        priority_weights=get_setting(db, "priority_weights"),
        priority_thresholds=get_setting(db, "priority_thresholds"),
        review_thresholds=get_setting(db, "review_thresholds"),
    )


def report_to_dict(r: Report) -> dict[str, Any]:
    return {
        "report_id": r.report_id,
        "report_type": r.report_type,
        "date": r.date.isoformat() if r.date else None,
        "site": r.site.name if r.site else None,
        "location": r.location,
        "activity": r.activity,
        "equipment": r.equipment,
        "description": r.description,
        "worker_role": r.worker_role,
        "contractor": r.contractor,
        "injury_severity": r.injury_severity,
        "shift": r.shift,
        "weather": r.weather,
    }


def features_of(ex: ExtractionResult, mapping: MappingResult) -> dict[str, Any]:
    return {
        "activity": ex.primary_activity,
        "failed_barriers": sorted({b.canonical for b in ex.all_controls if b.polarity in ("failed", "absent") and b.canonical}),
        "present_barriers": sorted({b.canonical for b in ex.all_controls if b.polarity == "present" and b.canonical}),
        "energies": sorted({e.canonical for e in ex.high_energies if e.canonical}),
        "hazards": sorted({h.canonical for h in ex.of("hazard") if h.canonical and not h.attrs.get("low_energy")}),
        "lsr": mapping.primary.code,
    }


def pattern_matches(features: dict[str, Any], signature: dict[str, Any]) -> bool:
    hits = 0
    for key, feat_key in (("activity", "activity"), ("barrier", "failed_barriers"), ("energy", "energies"), ("lsr", "lsr")):
        val = signature.get(key)
        if not val:
            continue
        have = features.get(feat_key)
        ok = val in have if isinstance(have, list) else val == have
        if not ok:
            return False
        hits += 1
    return hits >= 2


def make_context_lookup(db: Session, report: Report):
    window = int(get_setting(db, "recurrence_window_days"))

    def lookup(ex: ExtractionResult, mapping: MappingResult, scl: SCLResult) -> ContextInfo:
        start = report.date - timedelta(days=window)
        q = select(func.count(Report.id)).where(
            Report.primary_lsr == mapping.primary.code,
            Report.sif_signal.in_(["SIF_POTENTIAL", "SIF_EVENT"]),
            Report.date >= start,
            Report.date <= report.date,
        )
        if report.id:
            q = q.where(Report.id != report.id)
        count = db.scalar(q) or 0
        feats = features_of(ex, mapping)
        pats = db.scalars(select(Pattern).where(Pattern.is_current.is_(True))).all()
        matching = [{"pattern_id": p.id, "code": p.pattern_code, "name": p.name, "occurrences": p.occurrences} for p in pats if pattern_matches(feats, p.signature)]
        return ContextInfo(recurrence_count=int(count), matching_patterns=matching)

    return lookup


def _entity_rows(out: AnalysisOutput, analysis: ReportAnalysis, report: Report) -> list[tuple[Entity, list[EvidenceSpan]]]:
    rows = []
    for e in out.extraction.entities:
        ent = Entity(analysis_id=analysis.id, report_id=report.id, entity_type=e.entity_type, value=e.value[:200], canonical=(e.canonical or "")[:120] or None, polarity=e.polarity, confidence=e.confidence, source=e.source)
        spans = [EvidenceSpan(analysis_id=analysis.id, report_id=report.id, field=e.entity_type, text=ev.text, start_offset=ev.start, end_offset=ev.end, confidence=ev.confidence, source=ev.source) for ev in e.evidence]
        rows.append((ent, spans))
    return rows


def analyze_and_store(
    db: Session,
    report: Report,
    actor: User | None = None,
    pipeline: AnalysisPipeline | None = None,
    ml_override: tuple[float, str] | None = None,
    reason: str = "analysis",
    audit: bool = True,
) -> tuple[ReportAnalysis, AnalysisOutput]:
    pipeline = pipeline or build_pipeline(db)
    out = pipeline.run(report_to_dict(report), make_context_lookup(db, report), ml_override=ml_override)
    scl = out.scl

    db.execute(update(ReportAnalysis).where(ReportAnalysis.report_id == report.id).values(is_current=False))
    analysis = ReportAnalysis(
        report_id=report.id,
        model_version=out.model_version,
        energy_present=scl.gates["high_energy"].answer,
        energy_confidence=scl.gates["high_energy"].confidence,
        control_present=scl.gates["direct_control"].answer,
        control_confidence=scl.gates["direct_control"].confidence,
        high_energy_event=scl.gates["high_energy_event"].answer,
        high_energy_event_confidence=scl.gates["high_energy_event"].confidence,
        serious_injury=scl.gates["serious_injury"].answer,
        serious_injury_confidence=scl.gates["serious_injury"].confidence,
        scl_class=scl.scl_class,
        scl_candidates=scl.candidates,
        sif_potential=scl.sif_potential,
        sif_signal=scl.sif_signal,
        confidence=out.confidence,
        confidence_level=out.confidence_level,
        confidence_breakdown=out.confidence_breakdown,
        priority_score=out.priority_score,
        priority_level=out.priority_level,
        priority_breakdown=out.priority_breakdown,
        ml_probability=out.ml_probability,
        ml_model_version=out.ml_model_version,
        ml_explanation=out.ml_explanation,
        primary_lsr=out.mapping.primary.code,
        mapping_confidence=out.mapping.confidence,
        extraction={**out.extraction.to_dict(), "features": features_of(out.extraction, out.mapping), "mapping": out.mapping.to_dict(), "scl": scl.to_dict(), "context": {"recurrence_count": out.context.recurrence_count, "matching_patterns": out.context.matching_patterns}},
        reasoning_summary=out.reasoning_summary,
        pipeline_trace=out.trace,
        review_reasons=out.review_reasons,
        is_current=True,
    )
    db.add(analysis)
    db.flush()

    pairs = _entity_rows(out, analysis, report)
    db.add_all([ent for ent, _ in pairs])
    db.flush()
    for ent, spans in pairs:
        for s in spans:
            s.entity_id = ent.id
        db.add_all(spans)
    for g in scl.gates.values():
        for ev in g.evidence:
            db.add(EvidenceSpan(analysis_id=analysis.id, report_id=report.id, field=f"gate.{g.key}", text=ev.text, start_offset=ev.start, end_offset=ev.end, confidence=ev.confidence, source=ev.source))
    db.add(SCLClassification(
        analysis_id=analysis.id, report_id=report.id,
        q_high_energy=scl.gates["high_energy"].answer, q_high_energy_event=scl.gates["high_energy_event"].answer,
        q_direct_control=scl.gates["direct_control"].answer, q_serious_injury=scl.gates["serious_injury"].answer,
        decision_path=scl.decision_path, gate_details=[g.to_dict() for g in scl.gates.values()],
        candidate_classes=scl.candidates, scl_class=scl.scl_class, sif_potential=scl.sif_potential, conflicts=scl.conflicts,
    ))
    ranked = [out.mapping.primary] + out.mapping.secondary
    for i, c in enumerate(ranked):
        db.add(RuleMapping(analysis_id=analysis.id, report_id=report.id, rule_code=c.code, rank=i + 1, is_primary=i == 0, score=c.score, confidence=c.confidence if i else out.mapping.confidence, evidence=c.evidence))

    human_decided = report.decision_source == "HUMAN"
    report.current_analysis_id = analysis.id
    if not human_decided:
        report.scl_class = scl.scl_class
        report.sif_potential = scl.sif_potential
        report.sif_signal = scl.sif_signal
        report.primary_lsr = out.mapping.primary.code
        report.decision_source = "AI"
    report.priority_score = out.priority_score
    report.priority_level = out.priority_level
    report.confidence = out.confidence

    open_item = db.scalars(select(ReviewItem).where(ReviewItem.report_id == report.id, ReviewItem.status == "OPEN")).first()
    if out.review_reasons and not human_decided:
        report.status = STATUS_REVIEW
        if open_item:
            open_item.analysis_id = analysis.id
            open_item.reasons = out.review_reasons
            open_item.category = out.review_category or open_item.category
            open_item.priority_score = out.priority_score
        else:
            db.add(ReviewItem(report_id=report.id, analysis_id=analysis.id, category=out.review_category or "LOW_CONFIDENCE", reasons=out.review_reasons, suggested_action=SUGGESTED_ACTIONS.get(out.review_category or "", ""), priority_score=out.priority_score))
            if audit:
                log_event(db, "REVIEW_STARTED", f"{report.report_id} routed to review: {REVIEW_CATEGORIES.get(out.review_category or '', '')}", entity_type="report", entity_id=report.report_id, actor=actor, details={"reasons": out.review_reasons})
    elif not human_decided:
        report.status = STATUS_AI
        if open_item and open_item.source == "AUTO":
            open_item.status = "CLOSED"
            open_item.closed_at = datetime.now(timezone.utc)

    emb = active_embedder(db)
    if emb is not None:
        vec = emb.embed([build_model_text(report_to_dict(report))])[0].tolist()
        existing = db.scalars(select(Embedding).where(Embedding.report_id == report.id)).first()
        if existing:
            existing.vector = vec
            existing.model = emb.version
        else:
            db.add(Embedding(report_id=report.id, model=emb.version, vector=vec))

    if not audit:
        return analysis, out
    log_event(db, "REPORT_ANALYZED", f"{report.report_id} analysed ({reason}) - priority {int(out.priority_score + 0.5)}", entity_type="report", entity_id=report.report_id, actor=actor, details={"analysis_id": analysis.id, "engine": out.model_version})
    log_event(db, "SIF_CLASSIFIED", f"{report.report_id}: SCL {scl.scl_class} -> {scl.sif_signal}", entity_type="report", entity_id=report.report_id, actor=actor, details={"scl_class": scl.scl_class, "sif_signal": scl.sif_signal, "confidence": out.confidence})
    log_event(db, "RULE_MAPPED", f"{report.report_id}: proposed rule {out.mapping.primary.name}", entity_type="report", entity_id=report.report_id, actor=actor, details={"primary": out.mapping.primary.code, "secondary": [c.code for c in out.mapping.secondary]})
    return analysis, out
