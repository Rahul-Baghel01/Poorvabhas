"""Engine 1 - evidence-preserving safety extraction.

Deterministic Level-1 extraction (dictionaries + regex + phrase matching + synonym
normalisation). Every entity keeps: value, canonical form, confidence and the exact
source span(s) in the original description. Nothing is invented: if a field cannot be
supported by text or a structured field, it is reported as "Not stated".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.nlp import vocabulary as V
from app.nlp.normalize import Segment, clause_segments, clean_text, segment_containing, sentence_segments

NOT_STATED = "Not stated"

ENTITY_TYPES = (
    "activity",
    "site",
    "location",
    "equipment",
    "energy_source",
    "hazard",
    "barrier",
    "control",
    "failure_mode",
    "human_behavior",
    "report_type",
    "injury_outcome",
    "environmental_context",
)


@dataclass
class Evidence:
    text: str
    start: int | None
    end: int | None
    confidence: float
    source: str = "description"  # description | structured_field | rule

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end, "confidence": round(self.confidence, 3), "source": self.source}


@dataclass
class ExtractedEntity:
    entity_type: str
    value: str
    canonical: str | None
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    polarity: str | None = None  # present | failed | absent | mentioned | conflict
    source: str = "description"
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "canonical": self.canonical,
            "confidence": round(self.confidence, 3),
            "polarity": self.polarity,
            "source": self.source,
            "attrs": self.attrs,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class ExtractionResult:
    text: str
    entities: list[ExtractedEntity]
    sentences: list[Segment]

    def of(self, entity_type: str) -> list[ExtractedEntity]:
        return [e for e in self.entities if e.entity_type == entity_type]

    @property
    def energies(self) -> list[ExtractedEntity]:
        return [e for e in self.of("energy_source") if e.polarity != "absent"]

    @property
    def high_energies(self) -> list[ExtractedEntity]:
        return [e for e in self.energies if e.attrs.get("high")]

    @property
    def all_controls(self) -> list[ExtractedEntity]:
        return self.of("barrier") + self.of("control")

    @property
    def primary_activity(self) -> str | None:
        acts = self.of("activity")
        prim = [a for a in acts if a.attrs.get("primary")]
        return (prim or acts or [None])[0].canonical if (prim or acts) else None

    def not_stated(self) -> list[str]:
        present = {e.entity_type for e in self.entities}
        return [t for t in ENTITY_TYPES if t not in present]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "not_stated": self.not_stated(),
            "sentences": [{"text": s.text, "start": s.start, "end": s.end} for s in self.sentences],
        }


# --------------------------------------------------------------------------- regex helpers


@lru_cache(maxsize=4096)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _alt(patterns: tuple[str, ...]) -> str:
    return "(?:" + "|".join(patterns) + ")"


_FAIL_PREFIX_RE = re.compile(r"(?:" + _alt(V.BARRIER_FAIL_PREFIX) + r")\s+(?:[\w-]+\s+){0,1}$", re.IGNORECASE)
_OK_PREFIX_RE = re.compile(r"(?:" + _alt(V.BARRIER_OK_PREFIX) + r")\s*(?:[\w-]+\s+){0,1}$", re.IGNORECASE)
_FAIL_SUFFIX_RE = re.compile(r"^[\s,]*(?:[\w'-]+\s+){0,4}?" + _alt(V.BARRIER_FAIL_SUFFIX), re.IGNORECASE)
_OK_SUFFIX_RE = re.compile(r"^[\s,]*(?:[\w'-]+\s+){0,3}?" + _alt(V.BARRIER_OK_SUFFIX), re.IGNORECASE)
_MOVEMENT_RE = re.compile(r"\b(?:moving|movement|reversing|reversed|driving|drove|driven|travell?ing|manoeuvr\w*|maneuver\w*|speeding|speed|collid\w*|collision|backing|turning|overtak\w*|km/?h|rolled|parked on a slope|in motion|convoy)\b", re.IGNORECASE)
_ENERGY_NEG_PREFIX =re.compile(r"(?:\bno|\bzero|\bwithout|\bfree of|\bnil)\s+(?:[\w-]+\s+){0,1}$", re.IGNORECASE)
_ENERGY_NEG_SUFFIX = re.compile(r"^\s*(?:was|were)\s+(?:not (?:present|detected|found)|absent|zero|nil)", re.IGNORECASE)


def _find_terms(text: str, terms: tuple[V.Term, ...]) -> list[tuple[int, int, V.Term]]:
    """All non-overlapping matches, preferring longer spans."""
    raw: list[tuple[int, int, V.Term]] = []
    for term in terms:
        for pat in term.patterns:
            for m in _rx(pat).finditer(text):
                if m.end() > m.start():
                    raw.append((m.start(), m.end(), term))
    raw.sort(key=lambda r: (-(r[1] - r[0]), r[0]))
    taken: list[tuple[int, int, V.Term]] = []
    for s, e, t in raw:
        if all(e <= ts or s >= te for ts, te, _ in taken):
            taken.append((s, e, t))
    taken.sort(key=lambda r: r[0])
    return taken


def _group(entity_type: str, text: str, matches: list[tuple[int, int, V.Term]], source: str = "description") -> dict[str, ExtractedEntity]:
    out: dict[str, ExtractedEntity] = {}
    for s, e, term in matches:
        ev = Evidence(text[s:e], s, e, term.confidence, source)
        if term.canonical in out:
            ent = out[term.canonical]
            ent.evidence.append(ev)
            # repeated independent mentions raise confidence slightly
            ent.confidence = min(0.99, ent.confidence + 0.02)
        else:
            out[term.canonical] = ExtractedEntity(entity_type, text[s:e], term.canonical, term.confidence, [ev], source=source, attrs=dict(term.attrs))
    return out


def _barrier_state(text: str, clauses: list[Segment], start: int, end: int) -> tuple[str, float, int, int]:
    """Return (polarity, confidence, span_start, span_end) for a barrier mention."""
    clause = segment_containing(clauses, start) or Segment(text, 0, len(text))
    prefix = text[max(clause.start, start - 48) : start]
    suffix = text[end : min(clause.end, end + 64)]
    fail_p = _FAIL_PREFIX_RE.search(prefix)
    fail_s = _FAIL_SUFFIX_RE.search(suffix)
    ok_p = _OK_PREFIX_RE.search(prefix)
    ok_s = _OK_SUFFIX_RE.search(suffix)
    # a negated cue ("not wearing a") contains its positive form ("wearing a")
    if fail_p and ok_p and fail_p.start() <= ok_p.start():
        ok_p = None
    if fail_s and ok_s and ok_s.end() <= fail_s.end() + 12 and ok_s.start() <= fail_s.start():
        ok_s = None

    fail_dist = min([len(prefix) - fail_p.start() if fail_p else 999, fail_s.end() if fail_s else 999])
    ok_dist = min([len(prefix) - ok_p.start() if ok_p else 999, ok_s.end() if ok_s else 999])

    if fail_dist == 999 and ok_dist == 999:
        return "mentioned", 0.5, start, end
    # Opposite cues on opposite sides at similar distance -> genuinely conflicting text
    opposite_sides = (fail_p and ok_s and not fail_s) or (ok_p and fail_s and not fail_p)
    if fail_dist < 999 and ok_dist < 999 and opposite_sides and abs(fail_dist - ok_dist) < 3:
        return "conflict", 0.5, max(clause.start, start - 20), min(clause.end, end + 30)
    if fail_dist <= ok_dist:
        s = start - (len(prefix) - fail_p.start()) if fail_p and (len(prefix) - fail_p.start()) == fail_dist else start
        e = end + fail_s.end() if fail_s and fail_s.end() == fail_dist else end
        cue = (text[s:start] + text[end:e]).lower()
        polarity = "absent" if re.search(r"without|\bno\b|missing|lack|absence|not wearing|did not (?:have|use|wear)", cue) else "failed"
        return polarity, 0.9 if fail_dist < 30 else 0.78, s, e
    s = start - (len(prefix) - ok_p.start()) if ok_p and (len(prefix) - ok_p.start()) == ok_dist else start
    e = end + ok_s.end() if ok_s and ok_s.end() == ok_dist else end
    return "present", 0.88 if ok_dist < 30 else 0.75, s, e


def _canon_activity(value: str | None) -> str | None:
    if not value:
        return None
    m = _find_terms(value, V.ACTIVITIES)
    if m:
        # prefer specific over generic activity names
        specific = [x for x in m if x[2].canonical not in ("maintenance", "inspection")]
        return (specific or m)[0][2].canonical
    return value.strip().lower()


def canonical_activity(value: str | None) -> str | None:
    return _canon_activity(value)


class ExtractionEngine:
    version = "extract-det-1.0"

    def extract(self, report: dict[str, Any]) -> ExtractionResult:
        text = clean_text(report.get("description") or "")
        sentences = sentence_segments(text)
        clauses = clause_segments(text)
        entities: list[ExtractedEntity] = []

        # ---- structured fields (confidence 1.0 - they were entered by the reporter)
        def structured(etype: str, key: str, canonical: str | None = None, conf: float = 1.0) -> None:
            val = (report.get(key) or "").strip() if isinstance(report.get(key), str) else report.get(key)
            if val:
                entities.append(ExtractedEntity(etype, str(val), canonical or str(val), conf, [Evidence(str(val), None, None, conf, "structured_field")], source="structured_field", attrs={"field": key}))

        structured("site", "site")
        structured("location", "location")
        structured("report_type", "report_type")

        # ---- activity
        act_field = report.get("activity")
        field_canon = _canon_activity(act_field) if act_field else None
        text_acts = _group("activity", text, _find_terms(text, V.ACTIVITIES))
        if field_canon:
            in_text = field_canon in text_acts
            ent = ExtractedEntity("activity", act_field, field_canon, 0.97 if in_text else 0.9, [Evidence(act_field, None, None, 0.9, "structured_field")], source="structured_field", attrs={"primary": True, "corroborated_by_text": in_text})
            if in_text:
                ent.evidence.extend(text_acts.pop(field_canon).evidence)
            entities.append(ent)
        elif text_acts:
            best = sorted(text_acts.values(), key=lambda a: (a.canonical in ("maintenance", "inspection"), -a.confidence))[0]
            best.attrs["primary"] = True
        # generic "maintenance"/"inspection" add nothing when a specific activity exists
        if field_canon or any(a.canonical not in ("maintenance", "inspection") for a in text_acts.values()):
            for g in ("maintenance", "inspection"):
                if g in text_acts and not text_acts[g].attrs.get("primary"):
                    text_acts.pop(g)
        entities.extend(text_acts.values())

        # ---- equipment
        eq_field = report.get("equipment")
        if eq_field:
            entities.append(ExtractedEntity("equipment", eq_field, eq_field.strip().lower(), 1.0, [Evidence(eq_field, None, None, 1.0, "structured_field")], source="structured_field"))
        eq_text = _group("equipment", text, _find_terms(text, V.EQUIPMENT_PATTERNS))
        if eq_field:
            for k in list(eq_text):
                if k.split(" ")[0] in eq_field.lower():
                    eq_text.pop(k)
        entities.extend(eq_text.values())

        # ---- energy sources (with negation -> "absent")
        energies = _group("energy_source", text, _find_terms(text, V.ENERGY))
        mob = energies.get("mobile equipment")
        if mob and not (_MOVEMENT_RE.search(text) or field_canon == "vehicle movement"):
            # A parked vehicle is not a kinetic-energy source; keep it as equipment only
            energies.pop("mobile equipment")
        for ent in energies.values():
            polar = "present"
            for ev in ent.evidence:
                pre = text[max(0, (ev.start or 0) - 30) : ev.start or 0]
                suf = text[ev.end or 0 : (ev.end or 0) + 40]
                if _ENERGY_NEG_PREFIX.search(pre) or _ENERGY_NEG_SUFFIX.search(suf):
                    polar = "absent"
                else:
                    polar = "present"
                    break
            ent.polarity = polar
            if ent.attrs.get("implied"):
                ent.attrs["note"] = "Energy implied by domain rule (confined-space entry implies potential hazardous atmosphere)"
        entities.extend(energies.values())

        low = _group("hazard", text, _find_terms(text, V.LOW_ENERGY))
        for ent in low.values():
            ent.attrs["low_energy"] = True
        entities.extend(low.values())

        # ---- derived hazards (rule-based, evidence = energy spans)
        present_energy = {e.canonical: e for e in energies.values() if e.polarity == "present"}
        for hazard, triggers in V.HAZARD_RULES:
            hits = [present_energy[t] for t in triggers if t in present_energy]
            if hits:
                evs = [ev for h in hits for ev in h.evidence][:3]
                entities.append(ExtractedEntity("hazard", hazard, hazard, round(max(h.confidence for h in hits) * 0.95, 3), [Evidence(ev.text, ev.start, ev.end, ev.confidence, "rule") for ev in evs], source="rule", attrs={"derived_from": [h.canonical for h in hits]}))

        # ---- human behaviour
        behaviours = _group("human_behavior", text, _find_terms(text, V.HUMAN_BEHAVIOR))
        entities.extend(behaviours.values())

        # ---- barriers / controls with polarity
        barrier_ents: dict[str, ExtractedEntity] = {}
        for s, e, term in _find_terms(text, V.BARRIERS):
            polarity, pconf, ss, ee = _barrier_state(text, clauses, s, e)
            etype = "barrier" if term.attrs.get("direct") else "control"
            key = term.canonical
            ev = Evidence(text[ss:ee], ss, ee, round(term.confidence * pconf / 0.9, 3) if polarity != "mentioned" else 0.5)
            if key not in barrier_ents:
                barrier_ents[key] = ExtractedEntity(etype, text[s:e], key, round(min(0.97, term.confidence * (pconf / 0.9)), 3), [ev], polarity=polarity, attrs=dict(term.attrs))
            else:
                ent = barrier_ents[key]
                ent.evidence.append(ev)
                order = {"failed": 3, "absent": 3, "conflict": 2, "present": 1, "mentioned": 0}
                if "present" in {ent.polarity, polarity} and ({ent.polarity, polarity} & {"failed", "absent"}):
                    # Some elements in place, others failed (e.g. harness worn, lanyard not
                    # attached): a barrier is only effective when complete -> failed (partial).
                    ent.polarity = "failed"
                    ent.confidence = round(min(ent.confidence, term.confidence) * 0.9, 3)
                    ent.attrs["partial"] = True
                    ent.attrs["note"] = "Some elements of this barrier were in place but others failed"
                elif order[polarity] > order.get(ent.polarity or "mentioned", 0):
                    ent.polarity = polarity
                    ent.confidence = max(ent.confidence, round(term.confidence * (pconf / 0.9), 3))

        # A worker positioned in the line of fire implies the exclusion control failed
        dz = behaviours.get("entered danger zone")
        if dz and not (barrier_ents.get("exclusion zone") and barrier_ents["exclusion zone"].polarity in ("failed", "absent")):
            ev = dz.evidence[0]
            barrier_ents["exclusion zone"] = ExtractedEntity("barrier", ev.text, "exclusion zone", 0.82, [Evidence(ev.text, ev.start, ev.end, 0.82, "rule")], polarity="failed", source="rule", attrs={"direct": True, "lsr": "LINE_OF_FIRE", "note": "Worker positioned inside the danger zone implies the separation control was not effective"})
        entities.extend(barrier_ents.values())

        # ---- failure modes (barrier + failure cue span)
        for b in barrier_ents.values():
            if b.polarity in ("failed", "absent"):
                ev = max(b.evidence, key=lambda x: (x.end or 0) - (x.start or 0))
                label = f"{b.canonical} {'absent' if b.polarity == 'absent' else 'failed / not verified'}"
                entities.append(ExtractedEntity("failure_mode", ev.text, label, b.confidence, [ev], polarity=b.polarity, source=b.source, attrs={"barrier": b.canonical, "direct": b.attrs.get("direct")}))

        # ---- environment
        env = _group("environmental_context", text, _find_terms(text, V.ENVIRONMENT))
        entities.extend(env.values())
        for key in ("shift", "weather"):
            val = report.get(key)
            if val and str(val).strip() and str(val).strip().lower() not in ("day", "clear", "normal", "n/a", "none"):
                entities.append(ExtractedEntity("environmental_context", str(val), f"{key}: {str(val).lower()}", 1.0, [Evidence(str(val), None, None, 1.0, "structured_field")], source="structured_field", attrs={"field": key}))

        # ---- injury outcome
        sev = (report.get("injury_severity") or "").strip()
        if sev:
            entities.append(ExtractedEntity("injury_outcome", sev, sev.lower(), 1.0, [Evidence(sev, None, None, 1.0, "structured_field")], source="structured_field", attrs={"field": "injury_severity"}))
        for pats, label in ((V.INJURY_YES, "serious injury described"), (V.INJURY_NO, "no / minor injury described")):
            for p in pats:
                m = _rx(p).search(text)
                if m:
                    entities.append(ExtractedEntity("injury_outcome", m.group(0), label, 0.9, [Evidence(m.group(0), m.start(), m.end(), 0.9)], attrs={"serious": label.startswith("serious")}))
                    break

        return ExtractionResult(text=text, entities=entities, sentences=sentences)
