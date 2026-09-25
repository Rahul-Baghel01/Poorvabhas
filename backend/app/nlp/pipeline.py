"""End-to-end analysis pipeline (pure: no database access).

Report -> validation -> normalisation -> segmentation -> entity extraction -> energy /
barrier analysis -> SCL reasoning -> SIF classification -> IOGP mapping -> pattern
check -> priority -> review decision. Each stage is recorded in a trace for the UI.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.nlp.classifier import SafetyClassifier, build_model_text
from app.nlp.extraction import ExtractionEngine, ExtractionResult
from app.nlp.iogp import IOGPMapper, MappingResult
from app.nlp.normalize import clean_text, normalize_for_model, sentence_segments
from app.nlp.scl import DEFAULT_SIF_POTENTIAL_CLASSES, SCL_LABELS, SCLEngine, SCLResult
from app.nlp.scoring import compute_confidence, compute_priority, primary_category, route_review

ENGINE_VERSION = "poorvabhas-engine-1.0"

STAGES = [
    ("INGESTED", "Ingested"),
    ("TEXT_PROCESSED", "Text processed"),
    ("ENTITIES_EXTRACTED", "Entities extracted"),
    ("ENERGY_CONTROL", "Energy + control analysis"),
    ("SCL_CLASSIFICATION", "SCL classification"),
    ("IOGP_MAPPING", "IOGP mapping"),
    ("PATTERN_CHECK", "Pattern check"),
    ("PRIORITY", "Priority"),
    ("REVIEW_DECISION", "Review decision"),
]

REQUIRED_FIELDS = ("report_type", "date", "site", "location", "activity", "description")


class ValidationError(ValueError):
    pass


def validate_report(report: dict[str, Any]) -> list[str]:
    errors = [f"'{f}' is required" for f in REQUIRED_FIELDS if not str(report.get(f) or "").strip()]
    desc = str(report.get("description") or "")
    if desc and len(desc.strip()) < 15:
        errors.append("'description' must be at least 15 characters")
    if report.get("report_type") and report["report_type"] not in ("Unsafe Act", "Unsafe Condition", "Near Miss", "Incident"):
        errors.append("'report_type' must be one of Unsafe Act, Unsafe Condition, Near Miss, Incident")
    return errors


@dataclass
class ContextInfo:
    recurrence_count: int = 0
    matching_patterns: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AnalysisOutput:
    extraction: ExtractionResult
    scl: SCLResult
    mapping: MappingResult
    ml_probability: float | None
    ml_model_version: str | None
    ml_explanation: list[dict[str, Any]]
    confidence: float
    confidence_level: str
    confidence_breakdown: dict[str, Any]
    priority_score: float
    priority_level: str
    priority_breakdown: list[dict[str, Any]]
    review_reasons: list[dict[str, Any]]
    review_category: str | None
    context: ContextInfo
    reasoning_summary: str
    trace: list[dict[str, Any]]
    normalized_text: str
    model_version: str = ENGINE_VERSION


class AnalysisPipeline:
    def __init__(
        self,
        rules: list[dict[str, Any]] | None = None,
        classifier: SafetyClassifier | None = None,
        sif_classes: tuple[str, ...] = DEFAULT_SIF_POTENTIAL_CLASSES,
        priority_weights: dict[str, float] | None = None,
        priority_thresholds: dict[str, float] | None = None,
        review_thresholds: dict[str, float] | None = None,
    ):
        self.extractor = ExtractionEngine()
        self.scl_engine = SCLEngine(sif_classes)
        self.mapper = IOGPMapper(rules)
        self.classifier = classifier
        self.priority_weights = priority_weights
        self.priority_thresholds = priority_thresholds
        self.review_thresholds = review_thresholds

    def run(
        self,
        report: dict[str, Any],
        context_lookup: Callable[[ExtractionResult, MappingResult, SCLResult], ContextInfo] | None = None,
        ml_override: tuple[float, str] | None = None,
    ) -> AnalysisOutput:
        """`ml_override` = (probability, version) lets the seeder supply out-of-fold
        predictions so training reports are never scored by a model that saw them."""
        trace: list[dict[str, Any]] = []
        t0 = time.perf_counter()

        def stage(key: str, detail: str, data: dict[str, Any] | None = None, status: str = "done") -> None:
            nonlocal t0
            now = time.perf_counter()
            trace.append({"stage": key, "label": dict(STAGES)[key], "status": status, "detail": detail, "data": data or {}, "ms": round((now - t0) * 1000, 2)})
            t0 = now

        errors = validate_report(report)
        if errors:
            raise ValidationError("; ".join(errors))
        stage("INGESTED", f"{report.get('report_type')} report validated", {"fields": [f for f in REQUIRED_FIELDS if report.get(f)]})

        normalized = normalize_for_model(report.get("description") or "")
        n_sent = len(sentence_segments(clean_text(report.get("description") or "")))
        stage("TEXT_PROCESSED", f"{n_sent} sentence(s), {len(normalized.split())} tokens; abbreviations normalised", {"sentences": n_sent})

        ex = self.extractor.extract(report)

        n_ent = len([e for e in ex.entities if e.source != "structured_field"])
        stage("ENTITIES_EXTRACTED", f"{n_ent} entities from text; not stated: {', '.join(ex.not_stated()) or 'none'}", {"entities": n_ent, "not_stated": ex.not_stated()})

        scl = self.scl_engine.classify(ex, report.get("report_type"), report.get("injury_severity"))
        g = scl.gates
        stage("ENERGY_CONTROL", f"High energy: {g['high_energy'].answer} · Direct control: {g['direct_control'].answer}", {"high_energy": g["high_energy"].answer, "direct_control": g["direct_control"].answer})

        ml_prob = None
        ml_version = None
        ml_expl: list[dict[str, Any]] = []
        if ml_override is not None:
            ml_prob, ml_version = ml_override
            if self.classifier is not None:
                ml_expl = self.classifier.explain(build_model_text(report))
        elif self.classifier is not None:
            try:
                text = build_model_text(report)
                ml_prob = float(self.classifier.predict_proba([text])[0])
                ml_version = self.classifier.version
                ml_expl = self.classifier.explain(text)
            except Exception:
                ml_prob = None
        stage("SCL_CLASSIFICATION", f"SCL {scl.scl_class} → {scl.sif_signal.replace('_', ' ')}" + (f" · classifier P(SIF)={ml_prob:.2f}" if ml_prob is not None else " · classifier unavailable"), {"scl_class": scl.scl_class, "sif_signal": scl.sif_signal, "ml_probability": ml_prob})

        mapping = self.mapper.map(ex, report.get("activity"))
        stage("IOGP_MAPPING", f"Primary: {mapping.primary.name}" + (f" · secondary: {', '.join(c.name for c in mapping.secondary)}" if mapping.secondary else ""), {"primary": mapping.primary.code, "confidence": mapping.confidence})

        ctx = context_lookup(ex, mapping, scl) if context_lookup else ContextInfo()
        stage("PATTERN_CHECK", f"{ctx.recurrence_count} similar recent precursor(s); {len(ctx.matching_patterns)} matching pattern(s)", {"recurrence": ctx.recurrence_count, "patterns": ctx.matching_patterns})

        score, level, breakdown = compute_priority(ex, scl, ctx.recurrence_count, report, self.priority_weights, self.priority_thresholds)
        conf, conf_level, conf_breakdown = compute_confidence(ex, scl, mapping, ml_prob, report)
        stage("PRIORITY", f"Priority {int(score + 0.5)}/100 ({level}) · confidence {conf:.2f} ({conf_level})", {"priority": score, "level": level, "confidence": conf})

        reasons = route_review(scl, conf, mapping, ml_prob, self.review_thresholds, engine=self.scl_engine)
        category = primary_category(reasons)
        stage("REVIEW_DECISION", f"Routed to human review: {category.replace('_', ' ').lower()}" if category else "No review trigger - AI analysed", {"review_required": bool(reasons), "category": category})

        summary = self._summary(ex, scl, mapping, score, level)
        return AnalysisOutput(ex, scl, mapping, ml_prob, ml_version, ml_expl, conf, conf_level, conf_breakdown, score, level, breakdown, reasons, category, ctx, summary, trace, normalized)

    @staticmethod
    def _summary(ex: ExtractionResult, scl: SCLResult, mapping: MappingResult, score: float, level: str) -> str:
        g = scl.gates
        bits = []
        if g["high_energy"].answer == "YES":
            bits.append("High energy present (" + ", ".join(sorted({e.canonical or "" for e in ex.high_energies})) + ")")
        elif g["high_energy"].answer == "NO":
            bits.append("No high-energy source identified")
        else:
            bits.append("Energy source not stated")
        dc = g["direct_control"]
        bits.append({"YES": "direct control in place", "NO": "direct control absent or failed", "INSUFFICIENT": "control status not stated"}[dc.answer])
        if g["high_energy_event"].used:
            bits.append({"YES": "energy was released / contacted", "NO": "no release occurred", "INSUFFICIENT": "release not stated"}[g["high_energy_event"].answer])
        cls = SCL_LABELS[scl.scl_class]
        sig = {"SIF_EVENT": "an actual SIF event", "SIF_POTENTIAL": "SIF-potential", "NON_SIF": "not SIF-potential", "UNDETERMINED": "undetermined - needs human review"}[scl.sif_signal]
        return f"{'; '.join(bits)}. SCL class: {cls} → {sig}. Proposed Life-Saving Rule: {mapping.primary.name}. Priority {int(score + 0.5)}/100 ({level})."
