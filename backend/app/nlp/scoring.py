"""Explainable confidence, transparent priority scoring, and human-review routing."""

from __future__ import annotations

import math
from typing import Any

from app.nlp.extraction import ExtractionResult
from app.nlp.iogp import MappingResult
from app.nlp.scl import INS, NO, YES, SCLEngine, SCLResult

# --------------------------------------------------------------------------- defaults (configurable)
DEFAULT_PRIORITY_WEIGHTS = {
    "energy_exposure": 25,
    "barrier_failure": 25,
    "precursor_severity": 20,
    "recurrence": 15,
    "exposure_context": 15,
}
DEFAULT_PRIORITY_THRESHOLDS = {"CRITICAL": 85, "HIGH": 70, "MEDIUM": 45}
DEFAULT_REVIEW_THRESHOLDS = {
    "low_confidence": 0.55,
    "borderline_gate": 0.65,
    "ml_disagree_high": 0.70,
    "ml_disagree_low": 0.30,
}
DEFAULT_CONFIDENCE_WEIGHTS = {"extraction": 0.25, "classification": 0.35, "completeness": 0.2, "mapping": 0.2}

SEVERITY_FACTOR = {
    "HSIF": 1.0, "PSIF": 1.0, "EXPOSURE": 0.8, "CAPACITY": 0.5, "LSIF": 0.45, "SUCCESS": 0.2, "LOW_SEVERITY": 0.0, "UNDETERMINED": 0.5,
}

REVIEW_CATEGORIES = {
    "INSUFFICIENT_INFORMATION": "Insufficient information",
    "RULE_CONFLICT": "Rule conflict",
    "MODEL_RULE_DISAGREEMENT": "Model / rule disagreement",
    "BORDERLINE": "Borderline",
    "LOW_CONFIDENCE": "Low confidence",
    "MANUAL_REQUEST": "Manual request",
}
CATEGORY_PRECEDENCE = ["INSUFFICIENT_INFORMATION", "RULE_CONFLICT", "MODEL_RULE_DISAGREEMENT", "BORDERLINE", "LOW_CONFIDENCE"]


def level_for_confidence(c: float) -> str:
    return "HIGH" if c >= 0.75 else "MEDIUM" if c >= 0.55 else "LOW"


# --------------------------------------------------------------------------- confidence
def compute_confidence(ex: ExtractionResult, scl: SCLResult, mapping: MappingResult, ml_prob: float | None, report: dict[str, Any], weights: dict[str, float] | None = None) -> tuple[float, str, dict[str, Any]]:
    w = weights or DEFAULT_CONFIDENCE_WEIGHTS
    key_ents = ex.high_energies + [b for b in ex.of("barrier") if b.polarity != "mentioned"]
    extraction = sum(e.confidence for e in key_ents) / len(key_ents) if key_ents else 0.45

    used = [g for g in scl.gates.values() if g.used]
    answered = [g.confidence for g in used if g.answer != INS]
    if used and len(answered) == len(used):
        classification = math.exp(sum(math.log(max(c, 1e-3)) for c in answered) / len(answered))
    elif answered:
        classification = 0.5 * (sum(answered) / len(answered))
    else:
        classification = 0.2

    gates_answered = sum(1 for g in used if g.answer != INS) / max(1, len(used))
    fields = ["activity", "location", "equipment"]
    fields_present = sum(1 for f in fields if report.get(f)) / len(fields)
    desc_len = min(1.0, len((report.get("description") or "").split()) / 18)
    completeness = 0.6 * gates_answered + 0.2 * fields_present + 0.2 * desc_len

    mapping_c = mapping.confidence
    value = w["extraction"] * extraction + w["classification"] * classification + w["completeness"] * completeness + w["mapping"] * mapping_c

    ml_agreement = None
    penalty = 1.0
    if ml_prob is not None and scl.sif_potential is not None:
        ml_agreement = ml_prob if scl.sif_potential else 1 - ml_prob
        if ml_agreement < 0.3:
            penalty = 0.85
    if scl.conflicts:
        penalty *= 0.85
    value = max(0.0, min(0.99, value * penalty))
    breakdown = {
        "components": [
            {"key": "extraction", "label": "Extraction confidence", "value": round(extraction, 3), "weight": w["extraction"], "explanation": f"Mean confidence of {len(key_ents)} energy/barrier entities" if key_ents else "No energy or barrier entities extracted"},
            {"key": "classification", "label": "SCL gate confidence", "value": round(classification, 3), "weight": w["classification"], "explanation": f"Geometric mean over {len(used)} gate(s) on the decision path"},
            {"key": "completeness", "label": "Evidence completeness", "value": round(completeness, 3), "weight": w["completeness"], "explanation": f"{sum(1 for g in used if g.answer != INS)}/{len(used)} gates answered, {int(fields_present * 3)}/3 key fields, description length"},
            {"key": "mapping", "label": "Rule mapping confidence", "value": round(mapping_c, 3), "weight": w["mapping"], "explanation": "IOGP crosswalk score separation and strength"},
        ],
        "ml_agreement": round(ml_agreement, 3) if ml_agreement is not None else None,
        "penalty": round(penalty, 3),
        "penalty_reasons": (["ML model strongly disagrees"] if penalty < 1 and ml_agreement is not None and ml_agreement < 0.3 else []) + (["conflicting control statements"] if scl.conflicts else []),
    }
    return round(value, 3), level_for_confidence(value), breakdown


# --------------------------------------------------------------------------- priority
def compute_priority(ex: ExtractionResult, scl: SCLResult, recurrence_count: int, report: dict[str, Any], weights: dict[str, float] | None = None, thresholds: dict[str, float] | None = None) -> tuple[float, str, list[dict[str, Any]]]:
    w = {**DEFAULT_PRIORITY_WEIGHTS, **(weights or {})}
    th = {**DEFAULT_PRIORITY_THRESHOLDS, **(thresholds or {})}
    g = scl.gates
    parts: list[dict[str, Any]] = []

    e = g["high_energy"]
    if e.answer == YES:
        n = len(ex.high_energies)
        f = min(1.0, e.confidence * (1.0 if n == 1 else 1.1))
        why = f"High energy present ({', '.join(sorted({x.canonical or '' for x in ex.high_energies}))})"
    elif e.answer == INS:
        f, why = 0.25, "Energy not stated - partial weight pending review"
    else:
        f, why = 0.0, "Low-energy hazard only"
    parts.append({"key": "energy_exposure", "label": "Energy exposure", "points": round(w["energy_exposure"] * f, 1), "max": w["energy_exposure"], "rationale": why})

    c = g["direct_control"]
    if c.answer == NO:
        f, why = c.confidence, "Direct control absent / failed"
    elif c.answer == INS and scl.scl_class == "HSIF":
        f, why = 0.8, "Energy reached a person - barrier failure established by outcome"
    elif c.answer == INS:
        f, why = 0.3, "Control status not stated"
    else:
        admin_failed = [x for x in ex.of("control") if x.polarity in ("failed", "absent")]
        f, why = (0.2, "Direct control held; administrative control failed") if admin_failed else (0.0, "Direct control in place")
    parts.append({"key": "barrier_failure", "label": "Barrier / control failure", "points": round(w["barrier_failure"] * min(1.0, f), 1), "max": w["barrier_failure"], "rationale": why})

    f = SEVERITY_FACTOR.get(scl.scl_class, 0.5)
    if scl.scl_class == "UNDETERMINED":
        f = max(SEVERITY_FACTOR[x] for x in scl.candidates) * 0.7 if scl.candidates else 0.5
    parts.append({"key": "precursor_severity", "label": "Precursor severity (SCL)", "points": round(w["precursor_severity"] * f, 1), "max": w["precursor_severity"], "rationale": f"SCL class {scl.scl_class}"})

    f = min(1.0, recurrence_count / 8)
    parts.append({"key": "recurrence", "label": "Recurrence", "points": round(w["recurrence"] * f, 1), "max": w["recurrence"], "rationale": f"{recurrence_count} similar precursor report(s) in the last 90 days" if recurrence_count else "No similar recent reports"})

    ctx: list[str] = []
    if report.get("contractor"):
        ctx.append("contractor workforce")
    if str(report.get("shift") or "").lower() == "night" or any(x.canonical == "night / low light" for x in ex.of("environmental_context")):
        ctx.append("night / low light")
    if any(x.canonical == "adverse weather" for x in ex.of("environmental_context")) or str(report.get("weather") or "").lower() in ("rain", "storm", "fog", "high wind", "heavy rain"):
        ctx.append("adverse weather")
    if any(x.canonical == "simultaneous operations" for x in ex.of("environmental_context")):
        ctx.append("SIMOPS")
    if len({x.canonical for x in ex.high_energies}) > 1:
        ctx.append("multiple energy sources")
    if any(x.canonical in ("entered danger zone", "pedestrian exposure") for x in ex.of("human_behavior")):
        ctx.append("person in line of fire")
    f = min(1.0, 0.2 * len(ctx))
    parts.append({"key": "exposure_context", "label": "Exposure / context", "points": round(w["exposure_context"] * f, 1), "max": w["exposure_context"], "rationale": ", ".join(ctx) if ctx else "No aggravating context stated"})

    total = round(sum(p["points"] for p in parts), 1)
    level = "CRITICAL" if total >= th["CRITICAL"] else "HIGH" if total >= th["HIGH"] else "MEDIUM" if total >= th["MEDIUM"] else "LOW"
    return total, level, parts


# --------------------------------------------------------------------------- review routing
SUGGESTED_ACTIONS = {
    "INSUFFICIENT_INFORMATION": "Contact the reporter / supervisor to establish the missing facts, then set the SCL class.",
    "RULE_CONFLICT": "Resolve the conflicting control statements or ambiguous Life-Saving Rule and confirm the primary rule.",
    "MODEL_RULE_DISAGREEMENT": "Classifier and deterministic engine disagree - read the evidence and decide SIF potential.",
    "BORDERLINE": "A decision gate rests on weak evidence - confirm or correct the SCL path.",
    "LOW_CONFIDENCE": "Overall confidence is low - verify extraction and classification before acting.",
    "MANUAL_REQUEST": "Reviewer requested by HSE officer - validate the engine classification.",
}


def route_review(scl: SCLResult, confidence: float, mapping: MappingResult, ml_prob: float | None, thresholds: dict[str, float] | None = None, engine: "SCLEngine | None" = None) -> list[dict[str, Any]]:
    th = {**DEFAULT_REVIEW_THRESHOLDS, **(thresholds or {})}
    reasons: list[dict[str, Any]] = []
    used = [g for g in scl.gates.values() if g.used]
    missing = [g for g in used if g.answer == INS]
    if scl.scl_class == "UNDETERMINED" or scl.sif_signal == "UNDETERMINED":
        reasons.append({"code": "INSUFFICIENT_INFORMATION", "detail": "Required information missing: " + ", ".join(g.question for g in missing) if missing else "SCL path could not be resolved"})
    if scl.conflicts:
        reasons.append({"code": "RULE_CONFLICT", "detail": "; ".join(scl.conflicts)})
    if mapping.ambiguous:
        reasons.append({"code": "RULE_CONFLICT", "detail": mapping.ambiguity_note or "Ambiguous Life-Saving Rule mapping"})
    if ml_prob is not None and scl.sif_potential is not None:
        if scl.sif_potential is False and ml_prob >= th["ml_disagree_high"]:
            reasons.append({"code": "MODEL_RULE_DISAGREEMENT", "detail": f"Engine: not SIF-potential; classifier P(SIF)={ml_prob:.2f}"})
        elif scl.sif_potential is True and ml_prob <= th["ml_disagree_low"]:
            reasons.append({"code": "MODEL_RULE_DISAGREEMENT", "detail": f"Engine: SIF-potential; classifier P(SIF)={ml_prob:.2f}"})
    weak = [g for g in used if g.answer != INS and g.confidence < th["borderline_gate"]]
    if engine is not None:
        # only weak gates whose inversion would change the SIF outcome make a case borderline
        weak = [g for g in weak if engine.flip_changes_signal(scl, g.key)]
    if weak:
        reasons.append({"code": "BORDERLINE", "detail": "Weak evidence that could change the SIF outcome: " + ", ".join(f"{g.question} ({g.confidence:.2f})" for g in weak)})
    if confidence < th["low_confidence"]:
        reasons.append({"code": "LOW_CONFIDENCE", "detail": f"Overall confidence {confidence:.2f} below {th['low_confidence']:.2f}"})
    return reasons


def primary_category(reasons: list[dict[str, Any]]) -> str | None:
    codes = {r["code"] for r in reasons}
    for c in CATEGORY_PRECEDENCE:
        if c in codes:
            return c
    return next(iter(codes), None)
