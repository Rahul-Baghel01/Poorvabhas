"""Engine 3 - IOGP Life-Saving Rule mapping (PROPOSED CROSSWALK).

This SCL/precursor-to-IOGP mapping is the Poorvabhas team's proposed crosswalk. It is
NOT an official IOGP mapping and requires independent HSE expert validation.

Deterministic scoring = taxonomy keywords + phrases (admin-editable, weighted) plus
structural signals from the extraction engine (e.g. a failed isolation barrier).
Returns primary rule, secondary rules, evidence and a mapping confidence.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.nlp.extraction import ExtractionResult

CROSSWALK_LABEL = "Proposed IOGP LSR crosswalk"
CROSSWALK_DISCLAIMER = "Requires independent HSE expert validation"
FALLBACK_CODE = "PROCESS_SAFETY_NA"

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "code": "BYPASSING_SAFETY_CONTROLS", "rule_number": 1, "name": "Bypassing Safety Controls",
        "description": "Obtain authorisation before overriding or disabling safety-critical equipment, guards, trips or alarms.",
        "keywords": ["bypass", "bypassed", "override", "overridden", "defeated", "disabled", "jumper", "inhibited", "interlock", "guard removed", "trip"],
        "phrases": ["safety device disabled", "alarm inhibited", "guard was removed", "interlock bypassed", "trip overridden"],
        "weight": 1.0,
    },
    {
        "code": "CONFINED_SPACE", "rule_number": 2, "name": "Confined Space",
        "description": "Obtain authorisation before entering a confined space; confirm atmosphere testing, isolation and a standby person.",
        "keywords": ["confined space", "vessel entry", "tank entry", "manhole", "pit", "sump", "atmospheric", "oxygen", "standby person", "attendant"],
        "phrases": ["entered the tank", "entered the vessel", "without atmospheric monitoring", "oxygen deficient", "confined space permit"],
        "weight": 1.0,
    },
    {
        "code": "DRIVING", "rule_number": 3, "name": "Driving",
        "description": "Follow safe driving rules: seat belt, speed limits, no phone use, fit to drive, journey management.",
        "keywords": ["vehicle", "driving", "driver", "truck", "tanker", "speeding", "seat belt", "reversing", "forklift", "journey", "road"],
        "phrases": ["vehicle movement", "speed limit", "mobile phone while driving", "reversing vehicle", "journey management"],
        "weight": 1.0,
    },
    {
        "code": "ENERGY_ISOLATION", "rule_number": 4, "name": "Energy Isolation",
        "description": "Verify isolation and zero energy before work begins; use the specified life-protecting equipment.",
        "keywords": ["isolation", "isolated", "lockout", "lock out", "loto", "tagout", "de-energised", "de-energized", "residual pressure", "stored energy", "depressurised", "zero energy", "blind"],
        "phrases": ["isolation was not verified", "lockout tagout", "residual pressure", "zero energy", "double block and bleed", "positive isolation"],
        "weight": 1.0,
    },
    {
        "code": "HOT_WORK", "rule_number": 5, "name": "Hot Work",
        "description": "Control flammables and ignition sources; gas test before and during hot work.",
        "keywords": ["hot work", "welding", "grinding", "gas cutting", "sparks", "ignition", "flammable", "gas test", "gas testing", "fire watch", "LEL"],
        "phrases": ["gas testing was not completed", "hot work permit", "welding began", "ignition source", "fire watch"],
        "weight": 1.0,
    },
    {
        "code": "LINE_OF_FIRE", "rule_number": 6, "name": "Line of Fire",
        "description": "Keep yourself and others out of the line of fire: moving objects, dropped objects, releasing energy, vehicles.",
        "keywords": ["line of fire", "exclusion zone", "drop zone", "pinch point", "struck by", "caught between", "swing radius", "pedestrian", "dropped object"],
        "phrases": ["entered the exclusion zone", "under the suspended load", "in the line of fire", "working nearby", "stood in the path"],
        "weight": 1.0,
    },
    {
        "code": "SAFE_MECHANICAL_LIFTING", "rule_number": 7, "name": "Safe Mechanical Lifting",
        "description": "Plan lifting operations and control the area; use certified equipment and competent persons.",
        "keywords": ["lifting", "lift", "crane", "hoist", "rigging", "sling", "suspended load", "tag line", "load chart", "banksman", "spotter", "hydra"],
        "phrases": ["lifting operations", "suspended load", "lift plan", "rigging inspection", "load swung"],
        "weight": 1.0,
    },
    {
        "code": "WORK_AUTHORIZATION", "rule_number": 8, "name": "Work Authorization",
        "description": "Work with a valid work permit when required.",
        "keywords": ["permit", "ptw", "work permit", "authorisation", "authorization", "unauthorised", "unauthorized", "permit to work"],
        "phrases": ["without a permit", "permit had expired", "work without permit", "permit was not obtained", "without authorisation"],
        "weight": 1.0,
    },
    {
        "code": "WORKING_AT_HEIGHT", "rule_number": 9, "name": "Working at Height",
        "description": "Protect yourself against a fall when working at height.",
        "keywords": ["height", "scaffold", "ladder", "harness", "lanyard", "fall arrest", "guardrail", "handrail", "roof", "edge", "elevated", "monkey board", "tie off"],
        "phrases": ["working at height", "not tied off", "fall from height", "unprotected edge", "without harness"],
        "weight": 1.0,
    },
    {
        "code": FALLBACK_CODE, "rule_number": None, "name": "Process Safety / No Applicable Rule",
        "description": "Process-safety events (loss of containment, well control) or reports that do not cleanly map to one of the nine Life-Saving Rules.",
        "keywords": ["leak", "loss of containment", "release", "gas release", "hydrocarbon", "well control", "kick", "psv", "corrosion", "overpressure"],
        "phrases": ["loss of containment", "gas release", "well control", "relief valve"],
        "weight": 1.0,
        "is_fallback": True,
    },
]

# Rule pairs that legitimately co-occur (not treated as a mapping conflict).
COMPLEMENTARY = {
    frozenset({"SAFE_MECHANICAL_LIFTING", "LINE_OF_FIRE"}),
    frozenset({"DRIVING", "LINE_OF_FIRE"}),
    frozenset({"HOT_WORK", "WORK_AUTHORIZATION"}),
    frozenset({"CONFINED_SPACE", "WORK_AUTHORIZATION"}),
    frozenset({"ENERGY_ISOLATION", "WORK_AUTHORIZATION"}),
    frozenset({"WORKING_AT_HEIGHT", "WORK_AUTHORIZATION"}),
    frozenset({"ENERGY_ISOLATION", "LINE_OF_FIRE"}),
    frozenset({"CONFINED_SPACE", "HOT_WORK"}),
    frozenset({"BYPASSING_SAFETY_CONTROLS", "ENERGY_ISOLATION"}),
}


@dataclass
class RuleCandidate:
    code: str
    name: str
    score: float
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "name": self.name, "score": round(self.score, 3), "confidence": round(self.confidence, 3), "evidence": self.evidence}


@dataclass
class MappingResult:
    primary: RuleCandidate
    secondary: list[RuleCandidate]
    all_candidates: list[RuleCandidate]
    confidence: float
    ambiguous: bool
    ambiguity_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary.to_dict(),
            "secondary": [c.to_dict() for c in self.secondary],
            "candidates": [c.to_dict() for c in self.all_candidates],
            "confidence": round(self.confidence, 3),
            "ambiguous": self.ambiguous,
            "ambiguity_note": self.ambiguity_note,
            "label": CROSSWALK_LABEL,
            "disclaimer": CROSSWALK_DISCLAIMER,
        }


def _term_regex(term: str) -> re.Pattern[str]:
    t = re.escape(term.strip()).replace(r"\ ", r"[\s-]+")
    return re.compile(r"(?<![A-Za-z])" + t + r"(?![A-Za-z])", re.IGNORECASE)


class IOGPMapper:
    version = "iogp-crosswalk-1.0"

    def __init__(self, rules: list[dict[str, Any]] | None = None):
        rules = rules if rules is not None else DEFAULT_RULES
        self.rules = [r for r in rules if r.get("is_active", True)]
        self.names = {r["code"]: r["name"] for r in (rules or [])}
        self.names.setdefault(FALLBACK_CODE, "Process Safety / No Applicable Rule")

    def _structural(self, ex: ExtractionResult) -> dict[str, list[tuple[float, str, dict]]]:
        """Signals derived from extracted entities: code -> [(points, label, evidence)]."""
        sig: dict[str, list[tuple[float, str, dict]]] = {}

        def add(code: str, pts: float, label: str, ent) -> None:
            ev = ent.evidence[0] if ent.evidence else None
            sig.setdefault(code, []).append((pts, label, {"kind": "signal", "term": label, "text": ev.text if ev else "", "start": ev.start if ev else None, "end": ev.end if ev else None}))

        energies = {e.canonical: e for e in ex.energies}
        acts = {a.canonical: a for a in ex.of("activity")}
        behaviours = {b.canonical: b for b in ex.of("human_behavior")}
        controls = {c.canonical: c for c in ex.all_controls}

        def failed(name: str) -> bool:
            c = controls.get(name)
            return bool(c and c.polarity in ("failed", "absent"))

        if "energy isolation" in controls:
            add("ENERGY_ISOLATION", 2.5 if failed("energy isolation") else 1.0, "isolation barrier " + (controls["energy isolation"].polarity or ""), controls["energy isolation"])
        for en in ("residual pressure", "stored energy"):
            if en in energies:
                add("ENERGY_ISOLATION", 1.5, f"energy: {en}", energies[en])
        if "electrical" in energies and ("maintenance" in " ".join(acts) or "energy isolation" in controls):
            add("ENERGY_ISOLATION", 1.5, "electrical energy during work", energies["electrical"])
        # The rule that governs a FAILED control is the most actionable mapping
        for c in controls.values():
            if c.polarity in ("failed", "absent") and c.attrs.get("lsr"):
                code = c.attrs["lsr"]
                if c.canonical == "exclusion zone" and ("suspended load" in energies or "lifting" in acts):
                    code = "SAFE_MECHANICAL_LIFTING"  # lift exclusion zones are a lifting-rule control
                add(code, 1.5, f"failed control governed by this rule: {c.canonical}", c)
        if "hot work" in acts:
            add("HOT_WORK", 1.5, "activity: hot work", acts["hot work"])
        if "ignition source" in energies:
            add("HOT_WORK", 1.5, "ignition source present", energies["ignition source"])
        if "gas testing" in controls and ("ignition source" in energies or "hot work" in acts):
            add("HOT_WORK", 2.0 if failed("gas testing") else 0.8, "gas testing " + (controls["gas testing"].polarity or ""), controls["gas testing"])
        if "suspended load" in energies:
            add("SAFE_MECHANICAL_LIFTING", 2.0, "suspended load", energies["suspended load"])
        if "lifting" in acts:
            add("SAFE_MECHANICAL_LIFTING", 1.5, "activity: lifting", acts["lifting"])
        if "lifting controls" in controls:
            add("SAFE_MECHANICAL_LIFTING", 1.0, "lifting controls " + (controls["lifting controls"].polarity or ""), controls["lifting controls"])
        if "entered danger zone" in behaviours:
            add("LINE_OF_FIRE", 2.5, "person inside danger zone", behaviours["entered danger zone"])
        if "pedestrian exposure" in behaviours and "mobile equipment" in energies:
            add("LINE_OF_FIRE", 2.0, "pedestrian exposed to moving vehicle", behaviours["pedestrian exposure"])
        if "dropped object" in energies:
            add("LINE_OF_FIRE", 2.5, "dropped object", energies["dropped object"])
        for en in ("pinch point", "rotating equipment"):
            if en in energies:
                add("LINE_OF_FIRE", 1.5, f"energy: {en}", energies[en])
        if failed("exclusion zone"):
            add("LINE_OF_FIRE", 1.0, "exclusion zone breached", controls["exclusion zone"])
        if "confined-space entry" in acts:
            add("CONFINED_SPACE", 2.0, "activity: confined-space entry", acts["confined-space entry"])
        if "confined space atmosphere" in energies:
            add("CONFINED_SPACE", 1.5, "confined space atmosphere", energies["confined space atmosphere"])
        if "gas testing" in controls and "confined space atmosphere" in energies:
            add("CONFINED_SPACE", 1.5 if failed("gas testing") else 0.5, "atmospheric testing " + (controls["gas testing"].polarity or ""), controls["gas testing"])
        if "mobile equipment" in energies:
            add("DRIVING", 1.5, "mobile equipment", energies["mobile equipment"])
        if "vehicle movement" in acts:
            add("DRIVING", 1.5, "activity: vehicle movement", acts["vehicle movement"])
        for c in ("seat belt", "speed limit", "pedestrian separation"):
            if c in controls:
                add("DRIVING", 1.0, f"{c} {controls[c].polarity}", controls[c])
        if failed("permit to work"):
            add("WORK_AUTHORIZATION", 2.5, "permit / authorisation failed", controls["permit to work"])
        if "height" in energies:
            add("WORKING_AT_HEIGHT", 1.5, "energy: height", energies["height"])
        if "fall protection" in controls:
            add("WORKING_AT_HEIGHT", 2.0 if failed("fall protection") else 1.0, "fall protection " + (controls["fall protection"].polarity or ""), controls["fall protection"])
        if "bypassed control" in behaviours:
            add("BYPASSING_SAFETY_CONTROLS", 2.5, "safety control bypassed", behaviours["bypassed control"])
        for c in ("safety interlock / trip", "machine guarding"):
            if failed(c):
                add("BYPASSING_SAFETY_CONTROLS", 1.5, f"{c} defeated / missing", controls[c])
        for en in ("hydrocarbon / flammable", "well pressure"):
            if en in energies:
                add(FALLBACK_CODE, 1.5, f"process energy: {en}", energies[en])
        loc = re.search(r"loss of containment|\bleak(?:ed|ing|age)?\b|gas release|\bspill(?:ed)?\b|overflow\w*|\bkick\b|\binflux\b", ex.text, re.IGNORECASE)
        if loc:
            sig.setdefault(FALLBACK_CODE, []).append((2.0, "loss of containment / well control event", {"kind": "signal", "term": "loss of containment", "text": loc.group(0), "start": loc.start(), "end": loc.end()}))
        return sig

    def map(self, ex: ExtractionResult, activity_field: str | None = None) -> MappingResult:
        text = ex.text + ("  " + activity_field if activity_field else "")
        structural = self._structural(ex)
        cands: list[RuleCandidate] = []
        for rule in self.rules:
            score = 0.0
            evidence: list[dict[str, Any]] = []
            seen: set[str] = set()
            for kind, terms, pts in (("phrase", rule.get("phrases", []), 1.5), ("keyword", rule.get("keywords", []), 1.0)):
                for term in terms:
                    if not term or term.lower() in seen:
                        continue
                    m = _term_regex(term).search(text)
                    if m:
                        # skip keywords wholly contained in an already-matched phrase span
                        if kind == "keyword" and any(e.get("start") is not None and e["start"] <= m.start() and m.end() <= e["end"] for e in evidence):
                            continue
                        seen.add(term.lower())
                        score += pts
                        inside = m.start() < len(ex.text)
                        evidence.append({"kind": kind, "term": term, "text": m.group(0), "start": m.start() if inside else None, "end": m.end() if inside else None})
            for pts, _label, ev in structural.get(rule["code"], []):
                score += pts
                evidence.append(ev)
            score *= float(rule.get("weight", 1.0))
            if score > 0:
                cands.append(RuleCandidate(rule["code"], rule["name"], score, evidence=evidence))

        cands.sort(key=lambda c: -c.score)

        def supported(c: RuleCandidate) -> bool:
            # a single loose keyword is not enough: need a structural signal, a phrase, or 2+ keywords
            kinds = [e["kind"] for e in c.evidence]
            return "signal" in kinds or "phrase" in kinds or kinds.count("keyword") >= 2

        named = [c for c in cands if c.code != FALLBACK_CODE and c.score >= 1.5 and supported(c)]
        fb_c = next((c for c in cands if c.code == FALLBACK_CODE), None)
        if named and fb_c and any(e["kind"] == "signal" for e in fb_c.evidence) and fb_c.score > named[0].score:
            # a genuine process-safety event outranks weak Life-Saving Rule matches
            named = [fb_c] + named
        if not named:
            fb = next((c for c in cands if c.code == FALLBACK_CODE), None)
            if fb and fb.score >= 1.0:
                fb.confidence = round(min(0.8, 0.45 + 0.08 * fb.score), 3)
                note = "Process-safety signal without a clean Life-Saving Rule match"
            else:
                fb = RuleCandidate(FALLBACK_CODE, self.names[FALLBACK_CODE], 0.0, 0.5, [{"kind": "signal", "term": "no rule matched", "text": "", "start": None, "end": None}])
                note = "No Life-Saving Rule keywords or signals matched"
            return MappingResult(fb, [], cands[:5], fb.confidence, False, note)

        top = named[0]
        second = named[1].score if len(named) > 1 else 0.0
        sat = 1 - math.exp(-top.score / 3.0)
        sep = top.score / (top.score + second)
        conf = min(0.97, sat * (0.5 + 0.5 * sep) + 0.1)
        for c in named:
            c.confidence = round(min(0.97, (1 - math.exp(-c.score / 3.0)) * (c.score / top.score)), 3)
        top.confidence = round(conf, 3)
        secondary = [c for c in named[1:] if c.score >= 0.4 * top.score][:3]
        ambiguous = False
        note = None
        if len(named) > 1 and named[1].score >= 0.85 * top.score and frozenset({top.code, named[1].code}) not in COMPLEMENTARY:
            ambiguous = True
            note = f"{top.name} and {named[1].name} score within 15% - primary rule is ambiguous"
            conf *= 0.8
        return MappingResult(top, secondary, cands[:6], round(conf, 3), ambiguous, note)
