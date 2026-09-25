"""Engine 2 - Structured SCL (Safety Classification and Learning) reasoning.

Four evidence-based gates, each answered YES / NO / INSUFFICIENT with confidence and
evidence. Answers are never assumed: when the report does not support an answer the
gate returns INSUFFICIENT and the case can reach human review.

Decision tree (after the EEI / Hallowell et al. SCL model):

  Q1 High energy present?
    NO  -> Q4 serious injury?  YES -> LSIF        NO -> LOW_SEVERITY
    YES -> Q2 high-energy incident (release / contact) occurred?
        YES -> Q4 serious injury?  YES -> HSIF
                                   NO  -> Q3 direct control present?  YES -> CAPACITY   NO -> PSIF
        NO  -> Q3 direct control present?  YES -> SUCCESS   NO -> EXPOSURE

SIF-potential (prototype definition, configurable) = PSIF + EXPOSURE.
The underlying SCL class is always preserved separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.nlp import vocabulary as V
from app.nlp.extraction import Evidence, ExtractionResult

YES, NO, INS = "YES", "NO", "INSUFFICIENT"

SCL_CLASSES = ("HSIF", "PSIF", "EXPOSURE", "CAPACITY", "SUCCESS", "LSIF", "LOW_SEVERITY")
UNDETERMINED = "UNDETERMINED"
DEFAULT_SIF_POTENTIAL_CLASSES = ("PSIF", "EXPOSURE")

SCL_LABELS = {
    "HSIF": "High-energy SIF",
    "PSIF": "Potential SIF",
    "EXPOSURE": "Exposure",
    "CAPACITY": "Capacity",
    "SUCCESS": "Success",
    "LSIF": "Low-energy SIF",
    "LOW_SEVERITY": "Low severity",
    "UNDETERMINED": "Undetermined",
}

SCL_DESCRIPTIONS = {
    "HSIF": "High-energy incident occurred and a serious injury or fatality resulted.",
    "PSIF": "High-energy incident occurred without a direct control; no serious injury (by chance).",
    "EXPOSURE": "High energy was present without a direct control; no release occurred.",
    "CAPACITY": "High-energy incident occurred; a direct control was present and absorbed it.",
    "SUCCESS": "High energy was present and a direct control was in place; no incident.",
    "LSIF": "Serious injury from a low-energy source.",
    "LOW_SEVERITY": "Low-energy hazard with no serious injury.",
    "UNDETERMINED": "The report does not contain enough evidence to resolve the SCL path.",
}

IMPLIED_ENERGY = {
    "energy isolation": "hazardous stored / process energy",
    "fall protection": "work at height",
    "gas testing": "flammable or toxic atmospheres",
}

GATES = (
    ("high_energy", "Was high energy present?"),
    ("high_energy_event", "Did a high-energy incident occur?"),
    ("direct_control", "Was a direct control / barrier in place?"),
    ("serious_injury", "Was serious injury present?"),
)


@dataclass
class GateResult:
    key: str
    question: str
    answer: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    rationale: str = ""
    used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "question": self.question,
            "answer": self.answer,
            "confidence": round(self.confidence, 3),
            "evidence": [e.to_dict() for e in self.evidence],
            "rationale": self.rationale,
            "used_in_path": self.used,
        }


@dataclass
class SCLResult:
    gates: dict[str, GateResult]
    scl_class: str
    candidates: list[str]
    decision_path: list[str]
    sif_potential: bool | None
    sif_signal: str  # SIF_EVENT | SIF_POTENTIAL | NON_SIF | UNDETERMINED
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gates": [g.to_dict() for g in self.gates.values()],
            "scl_class": self.scl_class,
            "scl_label": SCL_LABELS[self.scl_class],
            "scl_description": SCL_DESCRIPTIONS[self.scl_class],
            "candidates": self.candidates,
            "decision_path": self.decision_path,
            "sif_potential": self.sif_potential,
            "sif_signal": self.sif_signal,
            "conflicts": self.conflicts,
        }


def _rx_search(patterns: tuple[str, ...], text: str) -> list[re.Match[str]]:
    out = []
    for p in patterns:
        out.extend(re.finditer(p, text, re.IGNORECASE))
    return sorted(out, key=lambda m: m.start())


class SCLEngine:
    version = "scl-det-1.0"

    def __init__(self, sif_potential_classes: tuple[str, ...] = DEFAULT_SIF_POTENTIAL_CLASSES):
        self.sif_classes = tuple(sif_potential_classes)

    # ------------------------------------------------------------------ gates
    def gate_high_energy(self, ex: ExtractionResult) -> GateResult:
        q = dict(GATES)["high_energy"]
        high = ex.high_energies
        if high:
            best = max(high, key=lambda e: e.confidence)
            evid = [ev for e in sorted(high, key=lambda e: -e.confidence)[:3] for ev in e.evidence[:1]]
            names = ", ".join(sorted({e.canonical for e in high if e.canonical}))
            conf = min(0.98, best.confidence + 0.03 * (len(high) - 1))
            return GateResult("high_energy", q, YES, conf, evid, f"High-energy source(s) identified in text: {names}.")
        # A direct control that exists only for a hazardous energy (isolation, fall
        # protection, atmospheric testing) is itself evidence that the energy was present.
        implied = [b for b in ex.of("barrier") if b.canonical in IMPLIED_ENERGY and b.polarity in ("present", "failed", "absent")]
        if implied:
            b = implied[0]
            return GateResult("high_energy", q, YES, 0.74, [b.evidence[0]], f"'{b.canonical}' is only applied to {IMPLIED_ENERGY[b.canonical]}; energy inferred from the control.")
        absent = [e for e in ex.of("energy_source") if e.polarity == "absent"]
        low = [e for e in ex.of("hazard") if e.attrs.get("low_energy")]
        if low:
            evid = [e.evidence[0] for e in low[:2]]
            return GateResult("high_energy", q, NO, 0.72, evid, "Only low-energy hazards are described (" + ", ".join(e.canonical or "" for e in low) + ").")
        if absent:
            return GateResult("high_energy", q, NO, 0.7, [absent[0].evidence[0]], f"Energy explicitly stated as absent ({absent[0].canonical}).")
        return GateResult("high_energy", q, INS, 0.0, [], "No energy source is stated in the report.")

    def gate_high_energy_event(self, ex: ExtractionResult, report_type: str | None) -> GateResult:
        q = dict(GATES)["high_energy_event"]
        text = ex.text
        yes = []
        for m in _rx_search(V.EVENT_YES, text):
            pre = text[max(0, m.start() - 25) : m.start()]
            if re.search(V.EVENT_NEGATION + r"[\w\s]{0,12}$", pre, re.IGNORECASE):
                continue
            yes.append(m)
        no = _rx_search(V.EVENT_NO, text)
        rt = (report_type or "").lower()
        if yes:
            evid = [Evidence(m.group(0), m.start(), m.end(), 0.85) for m in yes[:3]]
            conf = 0.9 if len(yes) > 1 else 0.82
            if no and rt in ("unsafe act", "unsafe condition"):
                conf -= 0.12
            return GateResult("high_energy_event", q, YES, conf, evid, "Text describes a release of, or contact with, the energy source.")
        if no:
            evid = [Evidence(m.group(0), m.start(), m.end(), 0.8) for m in no[:2]]
            return GateResult("high_energy_event", q, NO, 0.82, evid, "Hazard was observed / work stopped before any release occurred.")
        if rt in ("unsafe act", "unsafe condition"):
            ev = Evidence(report_type or "", None, None, 0.72, "structured_field")
            return GateResult("high_energy_event", q, NO, 0.72, [ev], f"Report type '{report_type}' records a precondition; no release or contact is described.")
        if rt == "near miss":
            ev = Evidence(report_type or "", None, None, 0.58, "structured_field")
            return GateResult("high_energy_event", q, NO, 0.58, [ev], "Near miss with no release language detected - weak evidence, verify.")
        return GateResult("high_energy_event", q, INS, 0.0, [], "Report does not state whether energy was released or contacted.")

    def gate_direct_control(self, ex: ExtractionResult) -> tuple[GateResult, list[str]]:
        q = dict(GATES)["direct_control"]
        conflicts: list[str] = []
        direct = ex.of("barrier")
        admin = ex.of("control")
        failed = [b for b in direct if b.polarity in ("failed", "absent")]
        ok = [b for b in direct if b.polarity == "present"]
        conflict = [b for b in direct if b.polarity == "conflict"]
        for b in conflict:
            conflicts.append(f"Conflicting statements about '{b.canonical}'")
        if failed:
            best = max(failed, key=lambda b: b.confidence)
            evid = [b.evidence[-1] for b in failed[:3]]
            conf = best.confidence * (0.8 if conflict else 1.0)
            why = "Direct control absent or failed: " + ", ".join(sorted({b.canonical or "" for b in failed})) + "."
            if ok:
                # one control holding does not protect against the energy another failed control guards
                why += " Other controls in place (" + ", ".join(sorted({b.canonical or "" for b in ok})) + ") do not replace the failed one."
                conf *= 0.92
            return GateResult("direct_control", q, NO, conf, evid, why), conflicts
        if ok:
            best = max(ok, key=lambda b: b.confidence)
            evid = [b.evidence[0] for b in ok[:3]]
            return GateResult("direct_control", q, YES, best.confidence * (0.8 if conflict else 1.0), evid, "Direct control in place: " + ", ".join(sorted({b.canonical or "" for b in ok})) + "."), conflicts
        if conflict:
            return GateResult("direct_control", q, INS, 0.3, [conflict[0].evidence[0]], "Conflicting statements about the direct control."), conflicts
        admin_failed = [c for c in admin if c.polarity in ("failed", "absent")]
        if admin_failed:
            evid = [c.evidence[-1] for c in admin_failed[:2]]
            return GateResult("direct_control", q, NO, 0.6, evid, "Only administrative controls are described and they failed (" + ", ".join(sorted({c.canonical or "" for c in admin_failed})) + "); no direct control is identified."), conflicts
        return GateResult("direct_control", q, INS, 0.0, [], "No direct control or barrier is stated in the report."), conflicts

    def gate_serious_injury(self, ex: ExtractionResult, report_type: str | None, injury_severity: str | None) -> GateResult:
        q = dict(GATES)["serious_injury"]
        text_yes = [e for e in ex.of("injury_outcome") if e.source == "description" and e.attrs.get("serious")]
        text_no = [e for e in ex.of("injury_outcome") if e.source == "description" and e.attrs.get("serious") is False]
        sev = (injury_severity or "").strip().lower()
        if sev in V.INJURY_SEVERITY_FIELD:
            ans, conf = V.INJURY_SEVERITY_FIELD[sev]
            ev = Evidence(injury_severity or "", None, None, conf, "structured_field")
            if ans == INS and text_yes:
                return GateResult("serious_injury", q, YES, 0.8, [ev, text_yes[0].evidence[0]], "Lost-time injury with serious-injury description in text.")
            if ans == INS and text_no:
                return GateResult("serious_injury", q, NO, 0.7, [ev, text_no[0].evidence[0]], "Lost-time injury; text indicates it was not life-altering.")
            if ans == NO and text_yes:
                return GateResult("serious_injury", q, YES, 0.6, [ev, text_yes[0].evidence[0]], "Structured severity says minor but text describes serious injury - conflict.")
            label = {YES: "serious injury recorded", NO: "no serious injury recorded", INS: "severity does not establish whether injury was life-altering"}[ans]
            return GateResult("serious_injury", q, ans, conf, [ev], f"Injury severity field: '{injury_severity}' ({label}).")
        if text_yes:
            return GateResult("serious_injury", q, YES, 0.85, [text_yes[0].evidence[0]], "Serious injury described in text.")
        if text_no:
            return GateResult("serious_injury", q, NO, 0.88, [text_no[0].evidence[0]], "Text states no / minor injury.")
        rt = (report_type or "").lower()
        if rt in ("unsafe act", "unsafe condition", "near miss"):
            ev = Evidence(report_type or "", None, None, 0.85, "structured_field")
            return GateResult("serious_injury", q, NO, 0.85, [ev], f"Report type '{report_type}' by definition records no injury.")
        return GateResult("serious_injury", q, INS, 0.0, [], "Injury outcome is not stated.")

    # ------------------------------------------------------------------ tree
    def resolve(self, answers: dict[str, str]) -> tuple[str, list[str], list[str], bool | None, str]:
        """Pure SCL tree over gate answers -> (class, candidates, gates used, sif_potential, sif_signal)."""
        used: list[str] = []

        def use(key: str) -> str:
            used.append(key)
            return answers[key]

        cls: str
        candidates: list[str]
        e = use("high_energy")
        if e == NO:
            i = use("serious_injury")
            cls, candidates = {YES: ("LSIF", ["LSIF"]), NO: ("LOW_SEVERITY", ["LOW_SEVERITY"])}.get(i, (UNDETERMINED, ["LSIF", "LOW_SEVERITY"]))
        elif e == INS:
            i = use("serious_injury")
            cls = UNDETERMINED
            candidates = ["HSIF", "LSIF"] if i == YES else ["PSIF", "EXPOSURE", "CAPACITY", "SUCCESS", "LOW_SEVERITY"] if i == NO else list(SCL_CLASSES)
        else:
            v = use("high_energy_event")
            if v == YES:
                i = use("serious_injury")
                if i == YES:
                    cls, candidates = "HSIF", ["HSIF"]
                elif i == NO:
                    c = use("direct_control")
                    cls, candidates = {YES: ("CAPACITY", ["CAPACITY"]), NO: ("PSIF", ["PSIF"])}.get(c, (UNDETERMINED, ["PSIF", "CAPACITY"]))
                else:
                    cls, candidates = UNDETERMINED, ["HSIF", "PSIF", "CAPACITY"]
            elif v == NO:
                c = use("direct_control")
                cls, candidates = {YES: ("SUCCESS", ["SUCCESS"]), NO: ("EXPOSURE", ["EXPOSURE"])}.get(c, (UNDETERMINED, ["SUCCESS", "EXPOSURE"]))
            else:
                c = use("direct_control")
                i = use("serious_injury")
                if i == YES:
                    cls, candidates = UNDETERMINED, ["HSIF"]
                elif c == NO:
                    cls, candidates = UNDETERMINED, ["PSIF", "EXPOSURE"]
                elif c == YES:
                    cls, candidates = UNDETERMINED, ["CAPACITY", "SUCCESS"]
                else:
                    cls, candidates = UNDETERMINED, ["PSIF", "EXPOSURE", "CAPACITY", "SUCCESS"]

        # If every remaining candidate agrees, the SIF-potential answer is still determined.
        in_sif = [c in self.sif_classes for c in candidates]
        sif_potential: bool | None = True if all(in_sif) else False if not any(in_sif) else None
        if cls == "HSIF" or (cls == UNDETERMINED and candidates == ["HSIF"]):
            sif_signal = "SIF_EVENT"
        elif sif_potential is True:
            sif_signal = "SIF_POTENTIAL"
        elif sif_potential is False:
            sif_signal = "NON_SIF"
        else:
            sif_signal = "UNDETERMINED"
        return cls, candidates, used, sif_potential, sif_signal

    def flip_changes_signal(self, result: "SCLResult", gate_key: str) -> bool:
        """Counterfactual: would inverting this gate's answer change the SIF outcome?"""
        answers = {k: g.answer for k, g in result.gates.items()}
        if answers[gate_key] not in (YES, NO):
            return False
        answers[gate_key] = NO if answers[gate_key] == YES else YES
        return self.resolve(answers)[4] != result.sif_signal

    def classify(self, ex: ExtractionResult, report_type: str | None, injury_severity: str | None) -> SCLResult:
        g1 = self.gate_high_energy(ex)
        g2 = self.gate_high_energy_event(ex, report_type)
        g3, conflicts = self.gate_direct_control(ex)
        g4 = self.gate_serious_injury(ex, report_type, injury_severity)
        gates = {g.key: g for g in (g1, g2, g3, g4)}
        cls, candidates, used, sif_potential, sif_signal = self.resolve({k: g.answer for k, g in gates.items()})
        for k in used:
            gates[k].used = True
        path = [f"{k}={gates[k].answer}" for k in used]
        return SCLResult(gates, cls, candidates, path, sif_potential, sif_signal, conflicts)
