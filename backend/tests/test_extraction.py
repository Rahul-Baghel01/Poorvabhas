from app.nlp.extraction import ExtractionEngine
from app.nlp.normalize import expand_abbreviations, normalize_for_model

ENGINE = ExtractionEngine()


def canon(result, etype):
    return {e.canonical for e in result.of(etype)}


def test_case1_pump_isolation_residual_pressure():
    text = "During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped."
    r = ENGINE.extract({"description": text, "activity": "Pump maintenance"})
    assert "pump maintenance" in canon(r, "activity")
    assert "residual pressure" in canon(r, "energy_source")
    iso = [b for b in r.of("barrier") if b.canonical == "energy isolation"][0]
    assert iso.polarity == "failed"
    ev = iso.evidence[0]
    assert text[ev.start : ev.end] == ev.text == "isolation was not verified"


def test_case2_hot_work_gas_testing():
    r = ENGINE.extract({"description": "During hot work, gas testing was not completed before welding began. Work was stopped when the issue was identified.", "activity": "Hot work"})
    assert "hot work" in canon(r, "activity")
    assert "ignition source" in canon(r, "energy_source")
    assert "fire / explosion" in canon(r, "hazard")
    gas = [b for b in r.of("barrier") if b.canonical == "gas testing"][0]
    assert gas.polarity == "failed"


def test_case3_lifting_exclusion_zone():
    r = ENGINE.extract({"description": "During lifting operations, a worker entered the exclusion zone while a suspended load was moving.", "activity": "Lifting"})
    assert "suspended load" in canon(r, "energy_source")
    assert "entered danger zone" in canon(r, "human_behavior")
    ez = [b for b in r.of("barrier") if b.canonical == "exclusion zone"][0]
    assert ez.polarity == "failed"


def test_case4_confined_space_missing_monitoring():
    r = ENGINE.extract({"description": "Worker entered a confined space without atmospheric monitoring.", "activity": "Confined-space entry"})
    assert "confined space atmosphere" in canon(r, "energy_source")
    gas = [b for b in r.of("barrier") if b.canonical == "gas testing"][0]
    assert gas.polarity == "absent"
    assert "toxic or oxygen-deficient atmosphere" in canon(r, "hazard")


def test_case5_vehicle_pedestrian():
    r = ENGINE.extract({"description": "Vehicle movement occurred while a pedestrian was working nearby.", "activity": "Vehicle movement"})
    assert "mobile equipment" in canon(r, "energy_source")
    assert "pedestrian exposure" in canon(r, "human_behavior")


def test_not_stated_and_no_invention():
    r = ENGINE.extract({"description": "Housekeeping poor near the workshop, clutter on the walkway."})
    assert not r.high_energies  # nothing invented
    ns = r.not_stated()
    assert "energy_source" in ns and "failure_mode" in ns


def test_every_text_span_points_into_source():
    text = "Scaffolder working at 5 m was not tied off; harness was worn but the lanyard was not attached. LOTO applied on the pump."
    r = ENGINE.extract({"description": text})
    for e in r.entities:
        for ev in e.evidence:
            if ev.start is not None:
                assert text[ev.start : ev.end] == ev.text


def test_partial_barrier_is_failed():
    r = ENGINE.extract({"description": "Scaffolder working at 5 m was not tied off; harness was worn but the lanyard was not attached."})
    fp = [b for b in r.of("barrier") if b.canonical == "fall protection"][0]
    assert fp.polarity == "failed"


def test_abbreviation_normalisation():
    assert "lockout tagout" in expand_abbreviations("LOTO not applied")
    assert "permit to work" in normalize_for_model("PTW expired")
    r = ENGINE.extract({"description": "Lock out was not applied; lock-out tag-out missing."})
    assert "energy isolation" in canon(r, "barrier")


def test_parked_vehicle_is_not_kinetic_energy():
    r = ENGINE.extract({"description": "Tanker hose leaked during unloading."})
    assert "mobile equipment" not in canon(r, "energy_source")
