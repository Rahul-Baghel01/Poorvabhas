import pytest

from app.nlp.extraction import ExtractionEngine
from app.nlp.scl import INS, NO, YES, SCLEngine

EX = ExtractionEngine()
SCL = SCLEngine()


def classify(text, rtype="Near Miss", injury=None, activity=None):
    ex = EX.extract({"description": text, "activity": activity})
    return SCL.classify(ex, rtype, injury)


@pytest.mark.parametrize(
    "text,rtype,injury,expected",
    [
        ("During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped.", "Near Miss", "None", "EXPOSURE"),
        ("While opening the flange, residual pressure was released and crude sprayed towards the fitter. Isolation had not been verified. No injury.", "Near Miss", None, "PSIF"),
        ("A joint of drill pipe dropped from the elevator and struck the floorman. He was hospitalised with a fracture.", "Incident", "Serious Injury", "HSIF"),
        ("Scaffolder slipped at 6 m and the fall arrest system arrested the fall. Harness was tied off to an anchor point. No injury.", "Near Miss", None, "CAPACITY"),
        ("LOTO was applied and verified before the pump seal change; the line was depressurised.", "Unsafe Condition", None, "SUCCESS"),
        ("Operator slipped on an oily walkway and fell on the same level. He was hospitalised with a fractured wrist.", "Incident", "Lost Time Injury", "LSIF"),
        ("Housekeeping poor near the workshop, clutter on the walkway.", "Unsafe Condition", None, "LOW_SEVERITY"),
    ],
)
def test_seven_scl_classes(text, rtype, injury, expected):
    assert classify(text, rtype, injury).scl_class == expected


def test_sif_potential_definition_is_psif_plus_exposure():
    assert classify("Worker entered a confined space without atmospheric monitoring.", "Unsafe Act").sif_potential is True
    assert classify("LOTO was applied and verified before the pump seal change; the line was depressurised.", "Unsafe Condition").sif_potential is False
    hsif = classify("A pipe dropped and struck the floorman. He was hospitalised with a fracture.", "Incident", "Serious Injury")
    assert hsif.scl_class == "HSIF" and hsif.sif_signal == "SIF_EVENT"


def test_insufficient_information_is_not_assumed():
    r = classify("Vehicle movement occurred while a pedestrian was working nearby.", "Unsafe Condition")
    assert r.gates["direct_control"].answer == INS
    assert r.scl_class == "UNDETERMINED"
    assert r.sif_signal == "UNDETERMINED"
    assert set(r.candidates) == {"SUCCESS", "EXPOSURE"}


def test_vague_report_has_no_energy():
    r = classify("Unsafe condition noticed near the pump house. Informed supervisor.", "Unsafe Condition")
    assert r.gates["high_energy"].answer == INS
    assert r.scl_class == "UNDETERMINED"


def test_gates_carry_evidence():
    r = classify("During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed.", "Near Miss")
    assert r.gates["high_energy"].answer == YES
    assert any("Residual pressure" in e.text for e in r.gates["high_energy"].evidence)
    assert r.gates["direct_control"].answer == NO
    assert r.gates["direct_control"].evidence[0].text == "isolation was not verified"


def test_resolver_counterfactual():
    r = classify("During pump maintenance, isolation was not verified. Residual pressure was observed.", "Near Miss")
    # Exposure -> PSIF if an energy release had occurred: still SIF-potential
    assert SCL.flip_changes_signal(r, "high_energy_event") is False
    # Exposure -> Success if the control had been in place: outcome changes
    assert SCL.flip_changes_signal(r, "direct_control") is True


def test_configurable_sif_definition():
    engine = SCLEngine(("PSIF", "EXPOSURE", "HSIF"))
    ex = EX.extract({"description": "A pipe dropped and struck the floorman. He was hospitalised with a fracture."})
    assert engine.classify(ex, "Incident", "Serious Injury").sif_potential is True
