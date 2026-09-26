"""Seed roles, demo users, sites, taxonomy, the synthetic dataset, models and patterns.

Run:  python -m app.seed.seed [--reset]
"""

from __future__ import annotations

import argparse
import time
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.patterns import mine_patterns
from app.audit import log_event
from app.config import get_settings
from app.db import Base, get_engine, init_db, session_factory
from app.models import DashboardSnapshot, ModelArtifact, Report, Role, Site, TaxonomyRule, User
from app.nlp.iogp import DEFAULT_RULES
from app.security import ROLE_PERMISSIONS, hash_password
from app.seed.generator import SITES, generate_reports
from app.services.analysis_service import analyze_and_store, build_pipeline
from app.services.model_service import evaluate_engine, fit_embedder, train_classifier

DEMO_USERS = [
    {"username": "admin", "full_name": "HSE Admin (demo)", "email": "hse.admin@demo.local", "password": "Admin@2026", "role": "HSE_ADMIN"},
    {"username": "officer", "full_name": "HSE Officer (demo)", "email": "hse.officer@demo.local", "password": "Officer@2026", "role": "HSE_OFFICER"},
    {"username": "reviewer", "full_name": "HSE Reviewer (demo)", "email": "hse.reviewer@demo.local", "password": "Reviewer@2026", "role": "HSE_OFFICER"},
]


def seed_reference(db: Session) -> None:
    if not db.scalars(select(Role)).first():
        db.add_all([Role(name="HSE_OFFICER", label="HSE Officer", permissions=ROLE_PERMISSIONS["HSE_OFFICER"]), Role(name="HSE_ADMIN", label="HSE Admin", permissions=ROLE_PERMISSIONS["HSE_ADMIN"])])
        db.flush()
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for u in DEMO_USERS:
        if not db.scalars(select(User).where(User.username == u["username"])).first():
            db.add(User(username=u["username"], full_name=u["full_name"], email=u["email"], password_hash=hash_password(u["password"]), role_id=roles[u["role"]].id))
    for s in SITES:
        if not db.scalars(select(Site).where(Site.code == s["code"])).first():
            db.add(Site(**s, is_synthetic=True))
    for r in DEFAULT_RULES:
        if not db.scalars(select(TaxonomyRule).where(TaxonomyRule.code == r["code"])).first():
            db.add(TaxonomyRule(code=r["code"], rule_number=r["rule_number"], name=r["name"], description=r["description"], keywords=r["keywords"], phrases=r["phrases"], weight=r["weight"], is_active=True, is_fallback=r.get("is_fallback", False), updated_by="seed"))
    db.flush()


def seed_dataset(db: Session, n: int, seed: int, verbose: bool = True) -> None:
    t0 = time.time()
    sites = {s.code: s for s in db.scalars(select(Site)).all()}
    records = generate_reports(n=n, seed=seed, today=date.today())
    reports: list[Report] = []
    for rec in records:
        r = Report(
            report_id=rec["report_id"], report_type=rec["report_type"], date=rec["date"], site_id=sites[rec["site"]].id, location=rec["location"], activity=rec["activity"],
            equipment=rec["equipment"], description=rec["description"], worker_role=rec["worker_role"], contractor=rec["contractor"], injury_severity=rec["injury_severity"],
            shift=rec["shift"], weather=rec["weather"], data_source="synthetic_demo", reference_scl_class=rec["reference_scl_class"],
            reference_sif_potential=rec["reference_sif_potential"], reference_lsr=rec["reference_lsr"], status="PENDING",
        )
        db.add(r)
        reports.append(r)
    db.flush()
    if verbose:
        print(f"  inserted {len(reports)} synthetic reports ({time.time() - t0:.1f}s)")

    fit_embedder(db)
    mv, oof = train_classifier(db, note="Initial seed model.")
    db.flush()
    if verbose:
        print(f"  trained {mv.version} on {mv.n_train} examples ({time.time() - t0:.1f}s)")

    pipeline = build_pipeline(db)
    for r in sorted(reports, key=lambda x: x.date):
        ml = (oof[r.id], mv.version) if r.id in oof else None
        analyze_and_store(db, r, pipeline=pipeline, ml_override=ml, reason="seed", audit=False)
    db.flush()
    if verbose:
        print(f"  analysed {len(reports)} reports ({time.time() - t0:.1f}s)")

    evaluate_engine(db)
    result = mine_patterns(db)
    if verbose:
        print(f"  mined {result['patterns']} patterns via {result['method']} ({time.time() - t0:.1f}s)")
    log_event(db, "DATASET_SEEDED", f"Synthetic demo dataset seeded: {len(reports)} reports", entity_type="dataset", entity_id="synthetic_demo", details={"reports": len(reports), "seed": seed})
    from app.analytics.dashboard import summary

    db.add(DashboardSnapshot(trigger="seed", payload={"kpis": summary(db, 90)["kpis"]}))


def ensure_model_artifacts(db: Session, verbose: bool = True) -> None:
    """Model files live outside the database (volume / local folder). If the database
    outlived them, retrain rather than silently running without the classifier."""
    from pathlib import Path

    from sqlalchemy import select as _select

    from app.models import Embedding
    from app.nlp.classifier import build_model_text
    from app.services.analysis_service import active_embedder, active_model, report_to_dict

    for component in ("embedder", "sif_classifier"):
        mv = active_model(db, component)
        if mv and db.get(ModelArtifact, mv.version):
            continue
        if mv and mv.artifact_path and Path(mv.artifact_path).exists():
            db.add(ModelArtifact(version=mv.version, payload=Path(mv.artifact_path).read_bytes()))
            db.flush()
            continue
        if verbose:
            print(f"  {component} artefact missing - retraining")
        if component == "embedder":
            fit_embedder(db)
            db.flush()
            emb = active_embedder(db)
            existing = {e.report_id: e for e in db.scalars(_select(Embedding)).all()}
            for r in db.scalars(_select(Report)).all():
                vec = emb.embed([build_model_text(report_to_dict(r))])[0].tolist()
                if r.id in existing:
                    existing[r.id].vector, existing[r.id].model = vec, emb.version
                else:
                    db.add(Embedding(report_id=r.id, model=emb.version, vector=vec))
        else:
            train_classifier(db, note="Retrained at startup: artefact missing.")
        db.flush()


def seed_all(reset: bool = False, verbose: bool = True) -> None:
    settings = get_settings()
    if reset:
        Base.metadata.drop_all(get_engine())
    init_db()
    db = session_factory()()
    try:
        seed_reference(db)
        db.commit()
        has_reports = db.scalar(select(func.count(Report.id))) or 0
        if has_reports == 0:
            if verbose:
                print(f"Seeding synthetic dataset ({settings.seed_reports} reports)...")
            seed_dataset(db, settings.seed_reports, settings.seed_random_state, verbose)
            db.commit()
        else:
            if verbose:
                print(f"Database already has {has_reports} reports - dataset seed skipped.")
            ensure_model_artifacts(db, verbose)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = ap.parse_args()
    seed_all(reset=args.reset)
