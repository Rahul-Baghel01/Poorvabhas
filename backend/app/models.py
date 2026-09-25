"""SQLAlchemy ORM schema for Poorvabhas.

Portable between PostgreSQL (production/demo, with pgvector) and SQLite (unit tests).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base

EMBED_DIM = 64
_USE_PGVECTOR = False


def configure_vector_column(use_pgvector: bool) -> None:
    global _USE_PGVECTOR
    _USE_PGVECTOR = use_pgvector


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmbeddingVector(TypeDecorator):
    """pgvector `vector(64)` on Postgres when available, JSON float array otherwise."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and _USE_PGVECTOR:
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(EMBED_DIM))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(v) for v in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(v) for v in value]


# ---------------------------------------------------------------- identity


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)  # HSE_OFFICER | HSE_ADMIN
    label: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    role: Mapped[Role] = relationship(lazy="joined")


# ---------------------------------------------------------------- reference


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    site_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Synthetic exposure denominator (work-hours in the dataset window). Demo value only.
    exposure_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- reports


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    location: Mapped[str] = mapped_column(String(160))
    activity: Mapped[str] = mapped_column(String(120), index=True)
    equipment: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    worker_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contractor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    injury_severity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    shift: Mapped[str | None] = mapped_column(String(30), nullable=True)
    weather: Mapped[str | None] = mapped_column(String(60), nullable=True)
    data_source: Mapped[str] = mapped_column(String(30), default="manual")  # synthetic_demo | manual | csv_import

    # Synthetic reference labels assigned by scenario design (NOT by the engine).
    # Only present for the synthetic demo dataset; used for held-out evaluation.
    reference_scl_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference_sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reference_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Denormalised current decision (AI or human-overridden) for fast filtering.
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    scl_class: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    sif_signal: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    primary_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    priority_level: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_source: Mapped[str | None] = mapped_column(String(10), nullable=True)  # AI | HUMAN
    current_analysis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    site: Mapped[Site] = relationship(lazy="joined")


class ReportAnalysis(Base):
    __tablename__ = "report_analysis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(60))
    energy_present: Mapped[str] = mapped_column(String(20))  # YES | NO | INSUFFICIENT
    energy_confidence: Mapped[float] = mapped_column(Float)
    control_present: Mapped[str] = mapped_column(String(20))
    control_confidence: Mapped[float] = mapped_column(Float)
    high_energy_event: Mapped[str] = mapped_column(String(20))
    high_energy_event_confidence: Mapped[float] = mapped_column(Float)
    serious_injury: Mapped[str] = mapped_column(String(20))
    serious_injury_confidence: Mapped[float] = mapped_column(Float)
    scl_class: Mapped[str] = mapped_column(String(20))
    scl_candidates: Mapped[list[str]] = mapped_column(JSON, default=list)
    sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sif_signal: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    confidence_level: Mapped[str] = mapped_column(String(10))
    confidence_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority_score: Mapped[float] = mapped_column(Float)
    priority_level: Mapped[str] = mapped_column(String(20))
    priority_breakdown: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ml_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    primary_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mapping_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_explanation: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    extraction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reasoning_summary: Mapped[str] = mapped_column(Text)
    pipeline_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    review_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("report_analysis.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[str] = mapped_column(String(200))
    canonical: Mapped[str | None] = mapped_column(String(120), nullable=True)
    polarity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # present | failed | absent
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))


class EvidenceSpan(Base):
    __tablename__ = "evidence_spans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("report_analysis.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=True)
    field: Mapped[str] = mapped_column(String(60))  # e.g. energy_source, gate.direct_control
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))  # description | structured_field | rule


class SCLClassification(Base):
    __tablename__ = "scl_classifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("report_analysis.id", ondelete="CASCADE"), unique=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    q_high_energy: Mapped[str] = mapped_column(String(20))
    q_high_energy_event: Mapped[str] = mapped_column(String(20))
    q_direct_control: Mapped[str] = mapped_column(String(20))
    q_serious_injury: Mapped[str] = mapped_column(String(20))
    decision_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    gate_details: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    candidate_classes: Mapped[list[str]] = mapped_column(JSON, default=list)
    scl_class: Mapped[str] = mapped_column(String(20))
    sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    conflicts: Mapped[list[str]] = mapped_column(JSON, default=list)


# ---------------------------------------------------------------- taxonomy / mapping


class TaxonomyRule(Base):
    __tablename__ = "taxonomy_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    rule_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    phrases: Mapped[list[str]] = mapped_column(JSON, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)


class RuleMapping(Base):
    __tablename__ = "rule_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("report_analysis.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(40), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


# ---------------------------------------------------------------- patterns


class Pattern(Base):
    __tablename__ = "patterns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    pattern_code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(30))  # hdbscan | frequency
    signature: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurrences: Mapped[int] = mapped_column(Integer)
    sif_occurrences: Mapped[int] = mapped_column(Integer, default=0)
    sites: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    activities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    barriers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    energy_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    associated_lsr: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    primary_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trend: Mapped[str] = mapped_column(String(30))  # INCREASING | DECREASING | STABLE | INSUFFICIENT_HISTORY
    trend_detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cohesion: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    first_seen: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_seen: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatternReport(Base):
    __tablename__ = "pattern_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_id: Mapped[int] = mapped_column(ForeignKey("patterns.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    membership: Mapped[float] = mapped_column(Float, default=1.0)
    __table_args__ = (UniqueConstraint("pattern_id", "report_id"),)


# ---------------------------------------------------------------- human review


class ReviewItem(Base):
    __tablename__ = "review_queue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("report_analysis.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    suggested_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)  # OPEN | CLOSED
    source: Mapped[str] = mapped_column(String(20), default="AUTO")  # AUTO | MANUAL
    requested_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report: Mapped[Report] = relationship(lazy="joined")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("review_queue.id", ondelete="SET NULL"), nullable=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    original_prediction: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[dict[str, Any]] = mapped_column(JSON)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewer_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedbackExample(Base):
    __tablename__ = "feedback_examples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("review_decisions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    label_sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    label_scl_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    label_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    predicted_sif_potential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    predicted_scl_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    predicted_lsr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False)
    used_in_model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- models / vectors


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(60), unique=True)
    component: Mapped[str] = mapped_column(String(40))  # deterministic_engine | sif_classifier | embedder
    algorithm: Mapped[str] = mapped_column(String(120))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evaluation_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_train: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_test: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Embedding(Base):
    __tablename__ = "embeddings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), unique=True)
    model: Mapped[str] = mapped_column(String(60))
    dim: Mapped[int] = mapped_column(Integer, default=EMBED_DIM)
    vector: Mapped[list[float]] = mapped_column(EmbeddingVector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- audit / system


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120), default="system")
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DashboardSnapshot(Base):
    __tablename__ = "dashboard_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)


Index("ix_reports_site_date", Report.site_id, Report.date)
