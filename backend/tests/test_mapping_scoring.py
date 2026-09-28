import pytest

from app.nlp.extraction import ExtractionEngine
from app.nlp.iogp import CROSSWALK_DISCLAIMER, CROSSWALK_LABEL, DEFAULT_RULES, IOGPMapper
from app.nlp.pipeline import AnalysisPipeline, ValidationError, validate_report
from app.nlp.scoring import DEFAULT_PRIORITY_WEIGHTS

EX = ExtractionEngine()
MAPPER = IOGPMapper()


def primary(text, activity=None):
    return MAPPER.map(EX.extract({"description": text, "activity": activity}), activity)


@pytest.mark.parametrize(
    "text,activity,code",
    [
        ("During pump maintenance, isolation was not verified. Residual pressure was observed.", "Pump maintenance", "ENERGY_ISOLATION"),
        ("During hot work, gas testing was not completed before welding began.", "Hot work", "HOT_WORK"),
        ("During lifting operations, a worker entered the exclusion zone while a suspended load was moving.", "Lifting", "SAFE_MECHANICAL_LIFTING"),
        ("Worker entered a confined space without atmospheric monitoring.", "Confined-space entry", "CONFINED_SPACE"),
        ("Vehicle movement occurred while a pedestrian was working nearby.", "Vehicle movement", "DRIVING"),
        ("Welding continued after the hot work permit had expired; crew worked without a valid permit.", None, "WORK_AUTHORIZATION"),
        ("Painter on the tank roof was working near the unprotected edge without a harness.", "Work at height", "WORKING_AT_HEIGHT"),
        ("The ESD interlock on the compressor was bypassed without authorisation.", "Maintenance", "BYPASSING_SAFETY_CONTROLS"),
        ("A spanner fell from the monkey board and landed a metre from the floorman. Tools were not tethered.", "Drilling", "LINE_OF_FIRE"),
        ("Gas release from the flowline flange gasket; loss of containment isolated by the operator.", "Pipeline work", "PROCESS_SAFETY_NA"),
    ],
)
def test_deterministic_mapping(text, activity, code):
    assert primary(text, activity).primary.code == code


def test_lifting_has_line_of_fire_secondary():
    m = primary("During lifting operations, a worker entered the exclusion zone while a suspended load was moving.", "Lifting")
    assert "LINE_OF_FIRE" in [c.code for c in m.secondary]
    assert m.primary.evidence and 0 < m.confidence <= 1


def test_no_rule_falls_back_and_is_labelled():
    m = primary("Faded signage at the entrance of the pump house.")
    assert m.primary.code == "PROCESS_SAFETY_NA"
    d = m.to_dict()
    assert d["label"] == CROSSWALK_LABEL == "Proposed IOGP LSR crosswalk"
    assert d["disclaimer"] == CROSSWALK_DISCLAIMER == "Requires independent HSE expert validation"


def test_nine_rules_plus_fallback():
    assert len([r for r in DEFAULT_RULES if r["rule_number"]]) == 9
    assert sum(1 for r in DEFAULT_RULES if r.get("is_fallback")) == 1


def test_inactive_rule_is_not_mapped():
    rules = [dict(r, is_active=(r["code"] != "HOT_WORK")) for r in DEFAULT_RULES]
    m = IOGPMapper(rules).map(EX.extract({"description": "During hot work, gas testing was not completed before welding began."}))
    assert m.primary.code != "HOT_WORK"


def test_priority_is_transparent_and_bounded():
    p = AnalysisPipeline()
    out = p.run({"report_type": "Near Miss", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Pump maintenance", "description": "During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed.", "contractor": "C-1", "shift": "Night"})
    assert 0 <= out.priority_score <= 100
    assert abs(sum(x["points"] for x in out.priority_breakdown) - out.priority_score) < 0.2
    assert {x["key"] for x in out.priority_breakdown} == set(DEFAULT_PRIORITY_WEIGHTS)
    for part in out.priority_breakdown:
        assert 0 <= part["points"] <= part["max"]


def test_custom_weights_change_score():
    base = {"report_type": "Near Miss", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Hot work", "description": "During hot work, gas testing was not completed before welding began."}
    a = AnalysisPipeline().run(base).priority_score
    w = {"energy_exposure": 10, "barrier_failure": 60, "precursor_severity": 10, "recurrence": 10, "exposure_context": 10}
    b = AnalysisPipeline(priority_weights=w).run(base).priority_score
    assert a != b


def test_confidence_is_explained():
    out = AnalysisPipeline().run({"report_type": "Near Miss", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Pump maintenance", "description": "During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed."})
    comps = out.confidence_breakdown["components"]
    assert {c["key"] for c in comps} == {"extraction", "classification", "completeness", "mapping"}
    assert 0 < out.confidence < 1
    vague = AnalysisPipeline().run({"report_type": "Unsafe Condition", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Maintenance", "description": "Unsafe condition noticed near pump house."})
    assert vague.confidence < out.confidence


def test_review_routing_reasons():
    out = AnalysisPipeline().run({"report_type": "Unsafe Condition", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Vehicle movement", "description": "Vehicle movement occurred while a pedestrian was working nearby."})
    assert out.review_category == "INSUFFICIENT_INFORMATION"
    ok = AnalysisPipeline().run({"report_type": "Unsafe Act", "date": "2026-01-01", "site": "X", "location": "Y", "activity": "Hot work", "description": "During hot work, gas testing was not completed before welding began. Work was stopped."})
    assert ok.review_category is None
    assert [s["stage"] for s in ok.trace][-1] == "REVIEW_DECISION" and len(ok.trace) == 9


def test_validation():
    assert validate_report({"description": "short"})
    with pytest.raises(ValidationError):
        AnalysisPipeline().run({"description": "x"})
