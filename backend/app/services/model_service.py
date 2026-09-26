"""Controlled model training + honest evaluation.

- Classifier: TF-IDF + Logistic Regression trained on synthetic reference labels (train
  split) plus human feedback examples. Never retrained automatically per correction:
  retraining is an explicit admin action.
- Evaluation: held-out test split (deterministic hash split, 25%). Metrics are stored
  with an explicit `evaluation_basis`; nothing is reported unless it was computed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import log_event
from app.config import get_settings
from app.models import FeedbackExample, ModelArtifact, ModelVersion, Report, ReportAnalysis, User
from app.nlp.classifier import LSAEmbedder, TfidfLogRegClassifier, build_model_text
from app.services.analysis_service import _cached_classifier, _cached_embedder, _db_classifiers, _db_embedders, report_to_dict

SYNTHETIC_BASIS = (
    "Held-out 25% split of the SYNTHETIC demo dataset, scored against reference labels assigned by scenario "
    "design. Synthetic text is far more regular than real reports, so these figures are optimistic and are "
    "NOT an estimate of real-world performance."
)
ENGINE_CAVEAT = (
    "The deterministic vocabulary was developed alongside these synthetic templates, so its agreement is "
    "optimistic by construction. It is not an independent accuracy estimate."
)
MIN_HUMAN_EVAL = 20


def is_test_split(report_id: str) -> bool:
    return int(hashlib.md5(report_id.encode()).hexdigest()[:8], 16) % 100 < 25


def _binary_metrics(y_true: list[int], y_pred: list[int], y_prob: list[float] | None = None) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

    m: dict[str, Any] = {
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "confusion_matrix": {"labels": ["non-SIF", "SIF potential"], "matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()},
        "positives": int(sum(y_true)),
    }
    if y_prob is not None and len(set(y_true)) == 2:
        m["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
    return m


def _training_data(db: Session) -> tuple[list[Report], list[int], int]:
    reports = db.scalars(select(Report)).all()
    feedback = {f.report_id: f for f in db.scalars(select(FeedbackExample).order_by(FeedbackExample.created_at)).all() if f.label_sif_potential is not None}
    X: list[Report] = []
    y: list[int] = []
    n_fb = 0
    for r in reports:
        if is_test_split(r.report_id):
            continue  # never train on the held-out split (including human labels on it)
        if r.id in feedback:
            X.append(r)
            y.append(int(bool(feedback[r.id].label_sif_potential)))
            n_fb += 1
        elif r.reference_sif_potential is not None:
            X.append(r)
            y.append(int(r.reference_sif_potential))
    return X, y, n_fb


def train_classifier(db: Session, actor: User | None = None, note: str | None = None) -> tuple[ModelVersion, dict[int, float]]:
    """Train + evaluate. Returns the model version and out-of-fold / held-out
    probabilities per report id (so no report is scored by a model trained on it)."""
    from sklearn.model_selection import StratifiedKFold

    X_reports, y, n_fb = _training_data(db)
    if len(X_reports) < 20 or len(set(y)) < 2:
        raise ValueError("Not enough labelled examples to train (need >= 20 with both classes)")
    texts = [build_model_text(report_to_dict(r)) for r in X_reports]
    version = "clf-tfidf-lr-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:17]

    # out-of-fold probabilities for training reports
    oof: dict[int, float] = {}
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    y_arr = np.array(y)
    for tr, te in skf.split(texts, y_arr):
        m = TfidfLogRegClassifier(version=version).fit([texts[i] for i in tr], y_arr[tr].tolist())
        probs = m.predict_proba([texts[i] for i in te])
        for i, p in zip(te, probs):
            oof[X_reports[i].id] = float(p)

    clf = TfidfLogRegClassifier(version=version).fit(texts, y)

    test = [r for r in db.scalars(select(Report)).all() if is_test_split(r.report_id)]
    for r in test:
        oof[r.id] = float(clf.predict_proba([build_model_text(report_to_dict(r))])[0])
    labelled_test = [r for r in test if r.reference_sif_potential is not None]
    metrics: dict[str, Any] | None = None
    basis = None
    if len(labelled_test) >= 10 and len({r.reference_sif_potential for r in labelled_test}) == 2:
        yt = [int(r.reference_sif_potential) for r in labelled_test]
        pr = [oof[r.id] for r in labelled_test]
        metrics = {"synthetic_holdout": _binary_metrics(yt, [int(p >= 0.5) for p in pr], pr), "cross_validation_oof": _binary_metrics(y, [int(oof[r.id] >= 0.5) for r in X_reports], [oof[r.id] for r in X_reports])}
        basis = SYNTHETIC_BASIS

    path = clf.save(get_settings().model_path)
    db.add(ModelArtifact(version=version, payload=Path(path).read_bytes()))
    db.execute(update(ModelVersion).where(ModelVersion.component == "sif_classifier").values(is_active=False))
    mv = ModelVersion(version=version, component="sif_classifier", algorithm="TF-IDF (1-2 gram) + Logistic Regression (class-balanced)", params=clf.params, metrics=metrics, evaluation_basis=basis, n_train=len(X_reports), n_test=len(labelled_test), artifact_path=path, is_active=True,
                      notes=(note or "") + f" Trained on {len(X_reports) - n_fb} synthetic reference labels + {n_fb} human feedback labels.")
    db.add(mv)
    db.execute(update(FeedbackExample).where(FeedbackExample.used_in_model_version.is_(None)).values(used_in_model_version=version))
    _cached_classifier.cache_clear()
    _db_classifiers.clear()
    log_event(db, "MODEL_CHANGED", f"Classifier {version} trained ({len(X_reports)} examples) and activated", entity_type="model", entity_id=version, actor=actor, details={"n_train": len(X_reports), "n_feedback": n_fb, "metrics": metrics})
    return mv, oof


def fit_embedder(db: Session) -> ModelVersion:
    reports = db.scalars(select(Report)).all()
    texts = [build_model_text(report_to_dict(r)) for r in reports]
    version = "emb-lsa64-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:17]
    emb = LSAEmbedder(version=version).fit(texts)
    path = emb.save(get_settings().model_path)
    db.add(ModelArtifact(version=version, payload=Path(path).read_bytes()))
    db.execute(update(ModelVersion).where(ModelVersion.component == "embedder").values(is_active=False))
    mv = ModelVersion(version=version, component="embedder", algorithm="TF-IDF + TruncatedSVD (LSA), 64-d unit vectors", params={"dim": 64}, metrics=None, evaluation_basis=None, n_train=len(texts), artifact_path=path, is_active=True, notes="Used for similar-report retrieval (pgvector cosine distance).")
    db.add(mv)
    _cached_embedder.cache_clear()
    _db_embedders.clear()
    return mv


def evaluate_engine(db: Session) -> ModelVersion:
    """Deterministic engine vs synthetic reference labels (first AI analysis, pre-human)."""
    rows = db.execute(
        select(Report, ReportAnalysis).join(ReportAnalysis, ReportAnalysis.report_id == Report.id).where(Report.reference_scl_class.is_not(None)).order_by(ReportAnalysis.id)
    ).all()
    first: dict[int, tuple[Report, ReportAnalysis]] = {}
    for r, a in rows:
        first.setdefault(r.id, (r, a))

    def block(items: list[tuple[Report, ReportAnalysis]]) -> dict[str, Any]:
        lab = [(r, a) for r, a in items if r.reference_sif_potential is not None]
        decided = [(r, a) for r, a in lab if a.sif_potential is not None]
        out: dict[str, Any] = {"n_labelled": len(lab), "n_decided": len(decided), "coverage": round(len(decided) / len(lab), 4) if lab else None, "abstained_to_review": len(lab) - len(decided)}
        if decided and len({int(r.reference_sif_potential) for r, _ in decided}) == 2:
            out["sif_potential_on_decided"] = _binary_metrics([int(r.reference_sif_potential) for r, _ in decided], [int(a.sif_potential) for _, a in decided])
        scl = [(r, a) for r, a in items if r.reference_scl_class not in (None, "UNDETERMINED") and a.scl_class != "UNDETERMINED"]
        if scl:
            out["scl_class_agreement"] = {"n": len(scl), "agreement": round(sum(r.reference_scl_class == a.scl_class for r, a in scl) / len(scl), 4)}
        lsr = [(r, a) for r, a in items if r.reference_lsr]
        if lsr:
            out["lsr_top1_agreement"] = {"n": len(lsr), "agreement": round(sum(r.reference_lsr == a.primary_lsr for r, a in lsr) / len(lsr), 4)}
        return out

    items = list(first.values())
    metrics = {"synthetic_holdout": block([x for x in items if is_test_split(x[0].report_id)]), "synthetic_all": block(items)}
    version = "poorvabhas-engine-1.0"
    mv = db.scalars(select(ModelVersion).where(ModelVersion.version == version)).first()
    if mv is None:
        mv = ModelVersion(version=version, component="deterministic_engine", algorithm="Rule-based extraction + SCL decision tree + IOGP crosswalk", params={"extraction": "extract-det-1.0", "scl": "scl-det-1.0", "iogp": "iogp-crosswalk-1.0"}, is_active=True)
        db.add(mv)
    mv.metrics = metrics
    mv.evaluation_basis = SYNTHETIC_BASIS + " " + ENGINE_CAVEAT
    mv.n_test = metrics["synthetic_holdout"]["n_labelled"]
    return mv


def human_review_evaluation(db: Session) -> dict[str, Any]:
    fb = db.scalars(select(FeedbackExample)).all()
    usable = [f for f in fb if f.label_sif_potential is not None and f.predicted_sif_potential is not None]
    if len(usable) < MIN_HUMAN_EVAL:
        return {"status": "pending", "n": len(usable), "required": MIN_HUMAN_EVAL, "message": f"Evaluation pending - {len(usable)} of {MIN_HUMAN_EVAL} required human-reviewed decisions on reports where the engine gave a definite SIF answer ({len(fb)} feedback examples in total)"}
    return {"status": "computed", **_binary_metrics([int(f.label_sif_potential) for f in usable], [int(f.predicted_sif_potential) for f in usable]), "basis": "Engine prediction vs HSE reviewer decision on reviewed reports (selection-biased toward uncertain cases)."}
