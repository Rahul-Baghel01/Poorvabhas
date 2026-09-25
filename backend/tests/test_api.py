from datetime import date

from tests.conftest import login


def test_health(client):
    assert client.get("/api/health").json()["database"] == "up"


def test_auth_required_and_roles(client, officer):
    assert client.get("/api/dashboard").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    me = client.get("/api/auth/me", headers=officer).json()["user"]
    assert me["role"] == "HSE_OFFICER"
    assert client.get("/api/dashboard", headers=officer).status_code == 200
    for ep in ("/api/taxonomy", "/api/settings", "/api/audit"):
        assert client.get(ep, headers=officer).status_code == 403
    assert client.post("/api/model/train", headers=officer).status_code == 403


def test_cookie_session(client):
    r = client.post("/api/auth/login", json={"username": "reviewer", "password": "Reviewer@2026"})
    assert "pv_session" in r.cookies
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_report_search_filters_and_pagination(client, admin):
    all_ = client.get("/api/reports?page_size=5", headers=admin).json()
    assert all_["total"] >= 70 and len(all_["items"]) == 5
    s = client.get("/api/reports?search=SYN-DEMO-001", headers=admin).json()
    assert s["total"] == 1 and s["items"][0]["report_id"] == "SYN-DEMO-001"
    f = client.get("/api/reports?sif_signal=SIF_POTENTIAL&page_size=100", headers=admin).json()
    assert f["items"] and all(i["sif_signal"] == "SIF_POTENTIAL" for i in f["items"])
    t = client.get("/api/reports?report_type=Near%20Miss&lsr=ENERGY_ISOLATION", headers=admin).json()
    assert all(i["report_type"] == "Near Miss" and i["primary_lsr"] == "ENERGY_ISOLATION" for i in t["items"])


def test_report_detail_evidence(client, admin):
    d = client.get("/api/reports/SYN-DEMO-001", headers=admin).json()
    a = d["analysis"]
    assert a["scl"]["scl_class"] == "EXPOSURE" and a["sif_potential"] is True
    assert a["mapping"]["primary"]["code"] == "ENERGY_ISOLATION"
    assert a["mapping"]["label"] == "Proposed crosswalk"
    text = d["report"]["description"]
    spans = [ev for e in a["entities"] for ev in e["evidence"] if ev["start"] is not None]
    assert spans and all(text[ev["start"] : ev["end"]] == ev["text"] for ev in spans)
    assert len(a["pipeline_trace"]) == 9


def test_critical_end_to_end_flow(client, admin):
    before = client.get("/api/dashboard?days=30", headers=admin).json()
    body = {
        "report_type": "Unsafe Condition", "date": date.today().isoformat(), "site": "Digboi", "location": "Loading Gantry",
        "activity": "Vehicle movement", "equipment": "Tanker", "description": "Vehicle movement occurred while a pedestrian was working nearby.",
    }
    r = client.post("/api/reports", json=body, headers=admin)
    assert r.status_code == 201, r.text
    out = r.json()
    rid = out["report_id"]
    stages = [s["stage"] for s in out["trace"]]
    assert stages == ["INGESTED", "TEXT_PROCESSED", "ENTITIES_EXTRACTED", "ENERGY_CONTROL", "SCL_CLASSIFICATION", "IOGP_MAPPING", "PATTERN_CHECK", "PRIORITY", "REVIEW_DECISION"]
    a = out["detail"]["analysis"]
    ents = {e["canonical"] for e in a["entities"]}
    assert "mobile equipment" in ents and "pedestrian exposure" in ents
    gates = {g["key"]: g["answer"] for g in a["scl"]["gates"]}
    assert gates["high_energy"] == "YES" and gates["direct_control"] == "INSUFFICIENT"
    assert a["scl"]["scl_class"] == "UNDETERMINED"
    assert a["mapping"]["primary"]["code"] == "DRIVING"
    assert a["priority_score"] > 0
    # routed to the review queue
    assert out["detail"]["review"]["category"] == "INSUFFICIENT_INFORMATION"
    queue = client.get("/api/review?category=INSUFFICIENT_INFORMATION&page_size=50&sort=newest", headers=admin).json()
    item = next(i for i in queue["items"] if i["report"]["report_id"] == rid)

    mid = client.get("/api/dashboard?days=30", headers=admin).json()
    assert mid["kpis"]["total_reports"]["value"] == before["kpis"]["total_reports"]["value"] + 1
    assert mid["kpis"]["review_queue"]["value"] == before["kpis"]["review_queue"]["value"] + 1

    # reviewer changes the classification
    d = client.post(f"/api/review/{item['id']}/decision", json={"action": "CHANGE", "scl_class": "EXPOSURE", "reason": "No pedestrian segregation at the gantry - no direct control.", "note": "Raise traffic management action."}, headers=admin)
    assert d.status_code == 200, d.text
    assert d.json()["status"] == "HUMAN_CONFIRMED"

    detail = client.get(f"/api/reports/{rid}", headers=admin).json()
    assert detail["report"]["scl_class"] == "EXPOSURE" and detail["report"]["sif_signal"] == "SIF_POTENTIAL"
    assert detail["report"]["decision_source"] == "HUMAN" and detail["review"] is None
    dec = detail["decisions"][0]
    assert dec["original_prediction"]["scl_class"] == "UNDETERMINED" and dec["decision"]["scl_class"] == "EXPOSURE"
    assert dec["reviewer"] == "HSE Admin (demo)" and dec["reason"] and dec["note"]
    events = {e["event_type"] for e in detail["audit"]}
    assert {"REPORT_CREATED", "REPORT_ANALYZED", "SIF_CLASSIFIED", "RULE_MAPPED", "REVIEW_STARTED", "REVIEW_COMPLETED"} <= events

    after = client.get("/api/dashboard?days=30", headers=admin).json()
    assert after["kpis"]["review_queue"]["value"] == before["kpis"]["review_queue"]["value"]
    assert after["kpis"]["sif_potential_reports"]["value"] == mid["kpis"]["sif_potential_reports"]["value"] + 1

    fb = client.get("/api/model/status", headers=admin).json()["feedback"]
    assert fb["total"] >= 1 and fb["corrections"] >= 1


def test_review_decision_validation(client, admin):
    item = client.get("/api/review?page_size=1", headers=admin).json()["items"][0]
    assert client.post(f"/api/review/{item['id']}/decision", json={"action": "REJECT"}, headers=admin).status_code == 422
    assert client.post(f"/api/review/{item['id']}/decision", json={"action": "CHANGE", "reason": "x"}, headers=admin).status_code == 422
    assert client.post(f"/api/review/{item['id']}/decision", json={"action": "NOTE", "note": "Checked with area supervisor"}, headers=admin).status_code == 200
    ok = client.post(f"/api/review/{item['id']}/decision", json={"action": "CONFIRM"}, headers=admin)
    assert ok.status_code == 200 and ok.json()["review_status"] == "CLOSED"
    assert client.post(f"/api/review/{item['id']}/decision", json={"action": "CONFIRM"}, headers=admin).status_code == 409


def test_manual_review_request(client, admin):
    r = client.post("/api/reports/SYN-DEMO-002/request-review", json={"reason": "Confirm gas test status"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["detail"]["report"]["status"] == "REVIEW_REQUIRED"
    assert r.json()["detail"]["review"]["category"] == "MANUAL_REQUEST"


def test_create_report_validation(client, admin):
    bad = {"report_type": "Rumour", "date": "2026-01-01", "site": "Digboi", "location": "X", "activity": "Y", "description": "short"}
    assert client.post("/api/reports", json=bad, headers=admin).status_code == 422
    dup = {"report_id": "SYN-DEMO-001", "report_type": "Near Miss", "date": "2026-01-01", "site": "Digboi", "location": "X", "activity": "Y", "description": "A long enough description of something."}
    assert client.post("/api/reports", json=dup, headers=admin).status_code == 409


CSV = """report_id,report_type,date,site,location,activity,equipment,description,worker_role
T-CSV-1,Near Miss,2026-05-12,Digboi,GGS-2,Pump maintenance,Booster pump,"LOTO was not applied on the booster pump before seal replacement; residual pressure was noticed and work was halted.",Fitter
T-CSV-2,UA,12/05/2026,New Test Field,Pad 1,Hot work,Grinder,"Grinding near the tank manifold without a gas test; no fire watch present.",Welder
T-CSV-3,Rumour,2026-05-12,Digboi,X,Y,Z,"Bad report type row for validation",
T-CSV-1,Near Miss,2026-05-12,Digboi,GGS-2,Pump,Pump,"Duplicate id in file should be rejected here",
"""


def test_csv_validation_and_import(client, admin):
    v = client.post("/api/imports/validate", files={"file": ("reports.csv", CSV, "text/csv")}, headers=admin)
    assert v.status_code == 200, v.text
    j = v.json()
    assert j["rows_detected"] == 4 and j["valid_rows"] == 2 and j["invalid_rows"] == 2
    assert "New Test Field" in j["new_sites"]
    before = client.get("/api/dashboard?days=365", headers=admin).json()["kpis"]["total_reports"]["value"]
    c = client.post(f"/api/imports/{j['token']}/commit", headers=admin)
    assert c.status_code == 200, c.text
    assert c.json()["imported"] == 2 and c.json()["analyzed"] == 2
    assert client.get("/api/reports/T-CSV-2", headers=admin).json()["analysis"]["mapping"]["primary"]["code"] == "HOT_WORK"
    after = client.get("/api/dashboard?days=365", headers=admin).json()["kpis"]["total_reports"]["value"]
    assert after == before + 2
    assert client.post(f"/api/imports/{j['token']}/commit", headers=admin).status_code == 404


def test_csv_missing_columns(client, admin):
    r = client.post("/api/imports/validate", files={"file": ("x.csv", "report_id,date\n1,2026-01-01\n", "text/csv")}, headers=admin)
    assert r.status_code == 422 and "Missing required column" in r.json()["detail"]


def test_taxonomy_update_is_audited(client, admin):
    r = client.put("/api/taxonomy/HOT_WORK", json={"keywords": ["hot work", "welding", "brazing"], "weight": 1.2}, headers=admin)
    assert r.status_code == 200 and r.json()["weight"] == 1.2
    audit = client.get("/api/audit?event_type=TAXONOMY_CHANGED", headers=admin).json()
    assert audit["total"] >= 1
    assert client.put("/api/taxonomy/PROCESS_SAFETY_NA", json={"is_active": False}, headers=admin).status_code == 422
    t = client.post("/api/taxonomy/test", json={"text": "Brazing near the separator without a gas test."}, headers=admin).json()
    assert t["primary"]["code"] == "HOT_WORK"


def test_settings_validation(client, admin):
    assert client.put("/api/settings/priority_weights", json={"value": {"energy_exposure": 50, "barrier_failure": 50, "precursor_severity": 50, "recurrence": 0, "exposure_context": 0}}, headers=admin).status_code == 422
    ok = {"energy_exposure": 25, "barrier_failure": 25, "precursor_severity": 20, "recurrence": 15, "exposure_context": 15}
    assert client.put("/api/settings/priority_weights", json={"value": ok}, headers=admin).status_code == 200
    s = client.get("/api/settings", headers=admin).json()
    assert s["environment"]["label"] == "DEMO ENVIRONMENT — SYNTHETIC SAFETY DATA"


def test_model_status_never_invents_metrics(client, admin):
    s = client.get("/api/model/status", headers=admin).json()
    hre = s["human_review_evaluation"]
    if hre["status"] == "pending":
        assert "Evaluation pending" in hre["message"]
    clf = next(v for v in s["versions"] if v["component"] == "sif_classifier" and v["is_active"])
    if clf["metrics"]:
        assert "SYNTHETIC" in clf["evaluation_basis"] and "NOT an estimate of real-world performance" in clf["evaluation_basis"]
    assert s["engine"]["external_llm"] is False


def test_dashboard_structure(client, admin):
    d = client.get("/api/dashboard?days=90", headers=admin).json()
    for k in ("total_reports", "sif_potential_reports", "recurring_patterns", "review_queue", "high_priority_signals", "lsr_coverage"):
        assert k in d["kpis"]
    assert sum(x["count"] for x in d["sif_distribution"]) == d["kpis"]["total_reports"]["value"]
    assert sum(w["total"] for w in d["reports_over_time"]) <= d["kpis"]["total_reports"]["value"] + 1
    assert d["site_ranking"]["items"]


def test_patterns_and_similar(client, admin):
    p = client.get("/api/patterns", headers=admin).json()
    assert p["items"]
    one = client.get(f"/api/patterns/{p['items'][0]['id']}", headers=admin).json()
    assert len(one["reports"]) == one["occurrences"]
    sim = client.get("/api/reports/SYN-DEMO-001/similar", headers=admin).json()
    assert sim["items"] and all("similarity" in x for x in sim["items"])


def test_retrain_uses_feedback(client, admin):
    r = client.post("/api/model/train", headers=admin)
    assert r.status_code == 200
    s = client.get("/api/model/status", headers=admin).json()
    assert s["feedback"]["not_yet_used_for_training"] == 0


def test_officer_can_review(client):
    h = login(client, "officer", "Officer@2026")
    item = client.get("/api/review?page_size=1", headers=h).json()["items"][0]
    r = client.post(f"/api/review/{item['id']}/decision", json={"action": "INSUFFICIENT", "reason": "Reporter to be contacted"}, headers=h)
    assert r.status_code == 200
