"""Taxonomy, model / analysis, settings and audit endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import EVENT_TYPES, log_event
from app.config import get_settings
from app.db import get_db, is_postgres
from app.models import AuditLog, Embedding, FeedbackExample, ModelVersion, Report, ReviewDecision, TaxonomyRule, User
from app.nlp.extraction import ExtractionEngine
from app.nlp.iogp import CROSSWALK_DISCLAIMER, CROSSWALK_LABEL, IOGPMapper
from app.nlp.pipeline import ENGINE_VERSION, STAGES
from app.security import require_permission
from app.serializers import audit_out
from app.services import settings_service as ss
from app.services.analysis_service import active_model, analyze_and_store, build_pipeline, rules_from_db
from app.services.model_service import human_review_evaluation, train_classifier

router = APIRouter(prefix="/api", tags=["admin"])


# ------------------------------------------------------------------ taxonomy
def rule_out(r: TaxonomyRule) -> dict[str, Any]:
    return {"id": r.id, "code": r.code, "rule_number": r.rule_number, "name": r.name, "description": r.description, "keywords": r.keywords, "phrases": r.phrases, "weight": r.weight, "is_active": r.is_active, "is_fallback": r.is_fallback, "updated_at": r.updated_at.isoformat(), "updated_by": r.updated_by}


@router.get("/taxonomy")
def taxonomy(db: Session = Depends(get_db), _: User = Depends(require_permission("taxonomy"))):
    rows = db.scalars(select(TaxonomyRule).order_by(TaxonomyRule.rule_number.is_(None), TaxonomyRule.rule_number)).all()
    return {"items": [rule_out(r) for r in rows], "label": CROSSWALK_LABEL, "disclaimer": CROSSWALK_DISCLAIMER, "warning": "Taxonomy changes affect the deterministic analysis engine."}


class RuleUpdate(BaseModel):
    keywords: list[str] | None = None
    phrases: list[str] | None = None
    weight: float | None = Field(None, ge=0.1, le=3.0)
    is_active: bool | None = None


def _clean_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    for t in terms:
        t = " ".join(str(t).split())[:80]
        if t and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    return out[:200]


@router.put("/taxonomy/{code}")
def update_rule(code: str, body: RuleUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("taxonomy"))):
    r = db.scalars(select(TaxonomyRule).where(TaxonomyRule.code == code)).first()
    if not r:
        raise HTTPException(404, "Rule not found")
    before = rule_out(r)
    if body.keywords is not None:
        r.keywords = _clean_terms(body.keywords)
    if body.phrases is not None:
        r.phrases = _clean_terms(body.phrases)
    if body.weight is not None:
        r.weight = round(body.weight, 2)
    if body.is_active is not None:
        if r.is_fallback and not body.is_active:
            raise HTTPException(422, "The fallback bucket cannot be deactivated")
        r.is_active = body.is_active
    r.updated_by = user.full_name
    changes = {k: {"from": before[k], "to": getattr(r, k)} for k in ("keywords", "phrases", "weight", "is_active") if before[k] != getattr(r, k)}
    log_event(db, "TAXONOMY_CHANGED", f"{r.name} updated by {user.full_name}", entity_type="taxonomy_rule", entity_id=r.code, actor=user, details={"changes": changes})
    db.commit()
    return rule_out(r)


class TestIn(BaseModel):
    text: str = Field(min_length=5, max_length=5000)
    activity: str | None = None


@router.post("/taxonomy/test")
def test_mapping(body: TestIn, db: Session = Depends(get_db), _: User = Depends(require_permission("taxonomy"))):
    ex = ExtractionEngine().extract({"description": body.text, "activity": body.activity})
    return IOGPMapper(rules_from_db(db)).map(ex, body.activity).to_dict()


# ------------------------------------------------------------------ model / analysis
@router.get("/model/status")
def model_status(db: Session = Depends(get_db), _: User = Depends(require_permission("analysis"))):
    versions = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    fb_total = db.scalar(select(func.count(FeedbackExample.id))) or 0
    fb_corr = db.scalar(select(func.count(FeedbackExample.id)).where(FeedbackExample.is_correction.is_(True))) or 0
    fb_unused = db.scalar(select(func.count(FeedbackExample.id)).where(FeedbackExample.used_in_model_version.is_(None))) or 0
    clf = active_model(db, "sif_classifier")
    emb_count = db.scalar(select(func.count(Embedding.id))) or 0
    transformer = False
    try:
        import transformers  # noqa: F401

        transformer = True
    except Exception:
        pass

    def mv_out(m: ModelVersion) -> dict[str, Any]:
        return {"version": m.version, "component": m.component, "algorithm": m.algorithm, "params": m.params, "metrics": m.metrics, "evaluation_basis": m.evaluation_basis, "n_train": m.n_train, "n_test": m.n_test, "is_active": m.is_active, "notes": m.notes, "created_at": m.created_at.isoformat()}

    return {
        "engine": {"name": "Hybrid Deterministic NLP + ML", "version": ENGINE_VERSION, "external_llm": False, "stages": [{"key": k, "label": v} for k, v in STAGES]},
        "components": [
            {"key": "preprocessing", "name": "Text preprocessing", "status": "active", "detail": "Unicode normalisation, abbreviation expansion (LOTO, PTW, PPE, JSA, BOP, SIMOPS...), sentence + clause segmentation (spaCy sentencizer, regex fallback)"},
            {"key": "ner", "name": "NER extraction", "status": "active", "detail": "Dictionary + regex safety entity recogniser with evidence offsets for 13 entity types"},
            {"key": "vocabulary", "name": "Safety vocabulary", "status": "active", "detail": "Structured energy / barrier / activity / behaviour vocabularies with synonym normalisation and barrier-state cues"},
            {"key": "scl", "name": "SCL decision engine", "status": "active", "detail": "4 evidence gates -> 7 SCL classes; INSUFFICIENT when unsupported"},
            {"key": "classifier", "name": "Classification model", "status": "active" if clf else "unavailable", "detail": (clf.algorithm + " - " + clf.version) if clf else "No trained classifier - deterministic engine only"},
            {"key": "mapper", "name": "Rule mapper", "status": "active", "detail": f"Deterministic IOGP Life-Saving Rule crosswalk ({CROSSWALK_LABEL.lower()}; {CROSSWALK_DISCLAIMER.lower()})"},
            {"key": "patterns", "name": "Pattern mining", "status": "active", "detail": "HDBSCAN over Jaccard distance with frequency-grouping fallback; EWMA + CUSUM trend tests"},
            {"key": "ranking", "name": "Ranking engine", "status": "active", "detail": "Empirical-Bayes Beta-Binomial rates and Gamma-Poisson exposure densities"},
            {"key": "embeddings", "name": "Similarity embeddings", "status": "active" if emb_count else "unavailable", "detail": f"LSA 64-d vectors in {'pgvector' if is_postgres() else 'JSON'} ({emb_count} stored)"},
            {"key": "transformer", "name": "Transformer classifier (optional)", "status": "installed" if transformer else "not installed", "detail": "HuggingFace DistilBERT-style drop-in via SafetyClassifier interface; falls back to TF-IDF + LogReg"},
        ],
        "versions": [mv_out(m) for m in versions],
        "feedback": {"total": fb_total, "corrections": fb_corr, "not_yet_used_for_training": fb_unused},
        "human_review_evaluation": human_review_evaluation(db),
    }


@router.post("/model/train")
def retrain(db: Session = Depends(get_db), user: User = Depends(require_permission("model"))):
    try:
        mv, _ = train_classifier(db, actor=user, note="Manual retrain.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"version": mv.version, "n_train": mv.n_train, "metrics": mv.metrics}


@router.post("/model/reanalyze-all")
def reanalyze_all(db: Session = Depends(get_db), user: User = Depends(require_permission("model"))):
    pipeline = build_pipeline(db)
    n = 0
    for r in db.scalars(select(Report).order_by(Report.date)).all():
        analyze_and_store(db, r, pipeline=pipeline, actor=user, reason="bulk re-analysis", audit=False)
        n += 1
    from app.analytics.patterns import mine_patterns

    mine_patterns(db, actor=user)
    log_event(db, "MODEL_CHANGED", f"All {n} reports re-analysed with the current engine / taxonomy", entity_type="engine", entity_id=ENGINE_VERSION, actor=user, details={"reports": n})
    db.commit()
    return {"reanalyzed": n}


# ------------------------------------------------------------------ settings
@router.get("/settings")
def get_settings_ep(db: Session = Depends(get_db), _: User = Depends(require_permission("settings"))):
    s = get_settings()
    counts = {"reports": db.scalar(select(func.count(Report.id))) or 0, "synthetic_reports": db.scalar(select(func.count(Report.id)).where(Report.data_source == "synthetic_demo")) or 0, "decisions": db.scalar(select(func.count(ReviewDecision.id))) or 0, "audit_events": db.scalar(select(func.count(AuditLog.id))) or 0}
    pgv = False
    if is_postgres():
        from sqlalchemy import text

        pgv = bool(db.execute(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")).scalar())
    return {
        "engine": ss.all_settings(db),
        "environment": {"environment": s.environment, "demo_mode": s.demo_mode, "data_mode": "Synthetic Demo Dataset" if s.demo_mode else "Configured data source", "label": "DEMO ENVIRONMENT — SYNTHETIC SAFETY DATA" if s.demo_mode else None},
        "database": {"dialect": "PostgreSQL" if is_postgres() else "SQLite", "pgvector": pgv, "counts": counts},
        "models": {m.component: m.version for m in db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))).all()},
        "security": {"auth": "JWT (HS256) in httpOnly SameSite=Lax cookie", "password_hashing": "bcrypt", "roles": ["HSE_OFFICER", "HSE_ADMIN"], "token_minutes": s.access_token_minutes, "secure_cookie": s.cookie_secure},
        "audit": {"event_types": list(EVENT_TYPES)},
    }


class SettingIn(BaseModel):
    value: Any


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingIn, db: Session = Depends(get_db), user: User = Depends(require_permission("settings"))):
    if key not in ss.DEFAULTS:
        raise HTTPException(404, "Unknown setting")
    value = body.value
    try:
        if key == "priority_weights":
            value = ss.validate_priority_weights(value)
        elif key == "priority_thresholds":
            value = {k: float(value[k]) for k in ("CRITICAL", "HIGH", "MEDIUM")}
            if not (100 >= value["CRITICAL"] > value["HIGH"] > value["MEDIUM"] > 0):
                raise ValueError("thresholds must satisfy 100 >= CRITICAL > HIGH > MEDIUM > 0")
        elif key == "review_thresholds":
            value = {k: float(value[k]) for k in ss.DEFAULTS["review_thresholds"]}
            if any(not 0 <= v <= 1 for v in value.values()):
                raise ValueError("review thresholds must be between 0 and 1")
        elif key == "sif_potential_classes":
            allowed = {"HSIF", "PSIF", "EXPOSURE", "CAPACITY", "SUCCESS", "LSIF", "LOW_SEVERITY"}
            if not value or not set(value) <= allowed:
                raise ValueError("choose one or more SCL classes")
        elif key in ("recurrence_window_days", "pattern_min_cluster_size"):
            value = int(value)
            if value < (3 if key == "pattern_min_cluster_size" else 7):
                raise ValueError("value too small")
        elif key == "use_classifier":
            value = bool(value)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"Invalid value: {e}")
    before = ss.get_setting(db, key)
    ss.set_setting(db, key, value, user.full_name)
    log_event(db, "SETTINGS_CHANGED", f"Setting '{key}' changed by {user.full_name}", entity_type="setting", entity_id=key, actor=user, details={"from": before, "to": value, "note": "Applies to new analyses; run 'Re-analyse all' to apply retroactively."})
    db.commit()
    return {"key": key, "value": value}


# ------------------------------------------------------------------ audit
@router.get("/audit")
def audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit")),
    event_type: str | None = None,
    exclude: str | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    q = select(AuditLog)
    if event_type:
        q = q.where(AuditLog.event_type.in_(event_type.split(",")))
    if exclude:
        q = q.where(AuditLog.event_type.not_in(exclude.split(",")))
    if search:
        like = f"%{search}%"
        q = q.where((AuditLog.summary.ilike(like)) | (AuditLog.entity_id.ilike(like)) | (AuditLog.actor_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [audit_out(a) for a in rows], "total": total, "page": page, "pages": max(1, -(-total // page_size)), "event_types": list(EVENT_TYPES)}
