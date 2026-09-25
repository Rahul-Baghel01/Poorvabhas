# SCL engine

*Judge the hazard, not the outcome.* The Safety Classification and Learning (SCL) engine decides whether a report describes a situation with serious-injury-or-fatality potential. It judges the energy and the controls, not how the event happened to turn out.

Code: `backend/app/nlp/scl.py`, `extraction.py`, `scoring.py`.

## The four gates

Each gate returns **YES**, **NO** or **INSUFFICIENT**, with a confidence, the evidence spans used, and a one-line rationale. A gate is never answered from an assumption: if the report does not support an answer it is INSUFFICIENT.

| Gate | YES when | NO when | INSUFFICIENT when |
|---|---|---|---|
| Q1 High energy present? | A high-energy source is extracted (pressure, stored energy, electrical, suspended load, dropped object, height, mobile equipment in motion, rotating equipment, hydrocarbons / ignition, toxic atmosphere, thermal, excavation), **or** a direct control that only exists for such energy is mentioned (isolation, fall protection, gas testing) | Only low-energy hazards are described (housekeeping, same-level slip, signage) or the energy is explicitly absent | No energy is stated |
| Q2 High-energy event (release / contact)? | Release or contact language not negated ("released", "sprayed", "dropped", "struck", "ignited", "kick", "gas alarm activated") | "task was stopped", "observed", "found"; or report type *Unsafe Act / Unsafe Condition* with no release language; *Near Miss* with no release language (weak, 0.58) | Incident report that does not say |
| Q3 Direct control in place? | A direct control is present ("LOTO was applied and verified", "harness tied off") | A direct control failed or was absent ("isolation was not verified", "without atmospheric monitoring", "entered the exclusion zone"); a partially implemented barrier counts as failed; only administrative controls described and they failed (0.6) | No control stated, or contradictory statements |
| Q4 Serious injury? | Injury field *Serious Injury / Fatality*, or text ("hospitalised", "fracture", "amputation") | Field *None / First Aid / Medical Treatment*, text "no injury", or report type UA / UC / Near Miss | Lost-time injury with no detail, or incident with no injury information |

### Direct vs administrative controls

A **direct control** targets the high-energy source and stays effective even if someone makes an unintentional mistake: energy isolation, machine guarding, interlocks and trips, fall protection, exclusion zones and barricades, gas testing and ventilation, pedestrian segregation, seat belts, dropped-object prevention, shoring, earthing, well-control barriers. **Administrative controls** — permits, spotters and banksmen, JSAs, PPE, alarms, speed limits — are extracted and shown but do not by themselves satisfy Q3.

### Barrier state detection

For each barrier mention the engine inspects its clause (sentences split at `;`, `but`, `while`, `, and`, …):

- failure cues **before** the term: *without, no, missing, lack of, not wearing, failed to …, bypassed, before, entered / inside / crossed …*
- failure cues **after** the term: *was not verified / completed / in place / tied off …, had expired, was removed, bypassed, damaged …*
- presence cues: *was applied / verified / in place / worn / tied off, functioned, arrested …*

The closest cue wins; a negated cue ("not wearing a") beats its positive substring ("wearing a"). Some elements present and others failed on the same barrier ("harness was worn but the lanyard was not attached") gives **failed (partial)**.

## Decision tree

```
Q1 High energy?
├─ NO  ─ Q4 Serious injury?  YES → LSIF        NO → LOW_SEVERITY
├─ INSUFFICIENT → UNDETERMINED (candidates depend on Q4)
└─ YES ─ Q2 High-energy event?
         ├─ YES ─ Q4?  YES → HSIF
         │             NO  ─ Q3 Direct control?  YES → CAPACITY   NO → PSIF
         ├─ NO  ─ Q3 Direct control?  YES → SUCCESS   NO → EXPOSURE
         └─ INSUFFICIENT → UNDETERMINED (candidates from Q3 / Q4)
```

| Class | Meaning |
|---|---|
| HSIF | High-energy incident with serious injury or fatality (shown as **SIF event**) |
| PSIF | High-energy incident, no direct control, no serious injury — luck |
| Exposure | High energy present without a direct control; no release |
| Capacity | High-energy incident absorbed by a direct control |
| Success | High energy controlled by a direct control |
| LSIF | Serious injury from a low-energy source |
| Low severity | Low energy, no serious injury |
| Undetermined | Evidence missing; the remaining candidate classes are listed |

When the class is Undetermined but **all** remaining candidates agree on SIF potential (e.g. {PSIF, Exposure}), the SIF-potential answer is still given.

### Worked example (demo case 1)

> *During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped.*

| Gate | Answer | Evidence |
|---|---|---|
| High energy | YES (0.94) | "Residual pressure" |
| Energy event | NO (0.82) | "was observed" / "task was stopped" |
| Direct control | NO (0.92) | "isolation was not verified" |
| Serious injury | NO (not on path) | injury field "None" |

Path: `high_energy=YES → high_energy_event=NO → direct_control=NO` → **Exposure** → **SIF potential: YES**.

Had the residual pressure actually been released, the same report would be **PSIF**. Both classes are SIF-potential under the prototype definition.

## SIF-potential definition

Default: **PSIF + Exposure** (setting `sif_potential_classes`). The SCL class is always stored separately, so the definition can change in Settings without losing information. HSIF is flagged as *SIF event* for incident investigation rather than counted as a "potential".

## Confidence (explainable)

`confidence = 0.25·extraction + 0.35·gates + 0.20·completeness + 0.20·mapping`, then × 0.85 if the classifier strongly disagrees and × 0.85 if control statements conflict.

- extraction — mean confidence of the energy and barrier entities used
- gates — geometric mean of the confidences on the decision path (halved if any gate is INSUFFICIENT)
- completeness — share of path gates answered, key fields present, description length
- mapping — IOGP mapping confidence

Levels: HIGH ≥ 0.75, MEDIUM ≥ 0.55, LOW below that.

## Priority (transparent 100-point model)

| Factor | Default weight | Scoring |
|---|---|---|
| Energy exposure | 25 | gate confidence if high energy; 25% if unstated |
| Barrier / control failure | 25 | gate confidence if no direct control; 30% if unstated; 80% for HSIF with unstated control (energy reached a person) |
| Precursor severity (SCL) | 20 | HSIF/PSIF 1.0 · Exposure 0.8 · Capacity 0.5 · LSIF 0.45 · Success 0.2 · Low 0 |
| Recurrence | 15 | similar SIF-signal reports on the same rule in the last 90 days, saturating at 8 |
| Exposure / context | 15 | 0.2 each: contractor, night / low light, adverse weather, SIMOPS, multiple energies, person in line of fire |

Levels: CRITICAL ≥ 85, HIGH ≥ 70, MEDIUM ≥ 45, else LOW. Weights and thresholds are editable in Settings (weights must total 100); every change is audited.

## Review routing

See the README table. Borderline uses a **counterfactual test**: a weak gate only triggers review if flipping its answer would change the SIF outcome. A weak "energy event" gate on an Exposure case doesn't qualify, because PSIF is SIF-potential too.
