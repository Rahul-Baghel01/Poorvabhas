# IOGP Life-Saving Rule mapping — proposed crosswalk

> **Proposed crosswalk. Requires independent HSE expert validation.**
> This mapping from SCL precursors to IOGP Life-Saving Rules is the Poorvabhas team's proposal. It is not published or endorsed by IOGP and has not been validated by OIL HSE experts. The UI repeats this label wherever a rule is shown.

Code: `backend/app/nlp/iogp.py`. Admin UI: **Taxonomy**.

## Rules

| # | Code | Rule | Typical trigger |
|---|---|---|---|
| 1 | `BYPASSING_SAFETY_CONTROLS` | Bypassing Safety Controls | defeated guard, bypassed trip / interlock, override |
| 2 | `CONFINED_SPACE` | Confined Space | confined-space / vessel / tank entry, atmosphere testing, attendant |
| 3 | `DRIVING` | Driving | vehicle in motion, speeding, seat belt, pedestrian interaction |
| 4 | `ENERGY_ISOLATION` | Energy Isolation | isolation / LOTO / residual or stored energy |
| 5 | `HOT_WORK` | Hot Work | welding, grinding, ignition source, gas testing |
| 6 | `LINE_OF_FIRE` | Line of Fire | person in danger zone, dropped objects, pinch points, rotating equipment |
| 7 | `SAFE_MECHANICAL_LIFTING` | Safe Mechanical Lifting | suspended load, crane, rigging, lift exclusion zone |
| 8 | `WORK_AUTHORIZATION` | Work Authorization | no / expired permit, unauthorised work |
| 9 | `WORKING_AT_HEIGHT` | Working at Height | elevation, harness, guardrail, fall arrest |
| — | `PROCESS_SAFETY_NA` | Process Safety / No Applicable Rule | loss of containment, well control, or no clean match |

## Scoring

For each active rule:

```
score = weight × ( Σ keyword matches × 1.0
                 + Σ phrase matches × 1.5
                 + Σ structural signals )
```

**Structural signals** come from the extraction engine, not raw keywords. Examples:

| Signal | Rule | Points |
|---|---|---|
| energy-isolation barrier failed / absent | Energy Isolation | 2.5 |
| residual pressure / stored energy | Energy Isolation | 1.5 |
| failed control governed by the rule (e.g. permit → Work Authorization, gas testing → Hot Work) | that rule | 1.5 |
| lift exclusion zone breached while a suspended load is present | Safe Mechanical Lifting | 1.5 |
| suspended load | Safe Mechanical Lifting | 2.0 |
| person inside a danger zone | Line of Fire | 2.5 |
| pedestrian + moving vehicle | Line of Fire | 2.0 |
| dropped object | Line of Fire | 2.5 |
| confined-space activity | Confined Space | 2.0 |
| loss of containment / kick / influx | Process Safety | 2.0 |

A rule needs a structural signal, a phrase or at least two keywords to be a candidate; a single loose keyword ("tanker") is not enough.

## Output

- **Primary rule** — highest score
- **Secondary rules** — other candidates scoring ≥ 40% of the primary (max 3), e.g. Lifting → *Line of Fire*
- **Evidence** — every keyword, phrase and signal with its text span
- **Confidence** — `(1 − e^(−top/3)) × (0.5 + 0.5 × top/(top+second)) + 0.1`, capped at 0.97
- **Ambiguity** — flagged (→ *Rule conflict* review) when the top two score within 15% and are not a known complementary pair (Lifting + Line of Fire, Hot Work + Work Authorization, …)

A genuine process-safety event (loss-of-containment signal) outranks weak Life-Saving Rule matches. When nothing matches, the report maps to *Process Safety / No Applicable Rule* with confidence 0.5.

## Editing the taxonomy

HSE Admins can edit keywords, phrases, weight (0.1–3.0) and active status per rule. The fallback bucket cannot be deactivated. Changes:

1. apply immediately to new analyses,
2. are recorded as `TAXONOMY_CHANGED` with a before/after diff,
3. apply to existing reports only after **Model / Analysis → Re-analyse all**.

The **Test mapping** console runs the current taxonomy on any text without saving anything.
