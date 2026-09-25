"""Synthetic demo dataset generator.

ALL DATA IS SYNTHETIC. Site names are used as demo placeholders only; nothing here is
OIL production data. Report IDs are prefixed "SYN-".

Each scenario template carries a *reference label* assigned by scenario design (what an
HSE assessor would conclude from the full scenario), NOT produced by the engine. These
labels allow an honest held-out evaluation of the engine and classifier on synthetic data.
Some phrasings deliberately use wording outside the engine's vocabulary, and some reports
are deliberately vague, so the engine will not agree with every reference label.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

SITES = [
    {"code": "DGB-S", "name": "Digboi", "region": "Upper Assam (synthetic)", "site_type": "Field + refinery interface", "exposure_hours": 520_000},
    {"code": "DLJ-S", "name": "Duliajan", "region": "Upper Assam (synthetic)", "site_type": "Field headquarters", "exposure_hours": 640_000},
    {"code": "NHK-S", "name": "Naharkatiya", "region": "Upper Assam (synthetic)", "site_type": "Production field", "exposure_hours": 380_000},
    {"code": "MRN-S", "name": "Moran", "region": "Upper Assam (synthetic)", "site_type": "Production field", "exposure_hours": 300_000},
    {"code": "BKT-S", "name": "Bokakhat", "region": "Central Assam (synthetic)", "site_type": "Exploration block", "exposure_hours": 170_000},
    {"code": "HPJ-S", "name": "Hapjan", "region": "Upper Assam (synthetic)", "site_type": "Gas gathering", "exposure_hours": 240_000},
    {"code": "TGK-S", "name": "Tengakhat", "region": "Upper Assam (synthetic)", "site_type": "Drilling block", "exposure_hours": 210_000},
]

LOCATIONS = {
    "DGB-S": ["GGS-2 Digboi", "Tank Farm East", "Main Workshop", "Well Pad DGB-114", "Loading Gantry"],
    "DLJ-S": ["OCS-4 Duliajan", "Central Workshop", "Compressor Station C-2", "Well Pad DLJ-207", "Effluent Treatment Plant", "Drilling Rig SR-7"],
    "NHK-S": ["GGS-1 Naharkatiya", "Crude Pump House", "Well Pad NHK-41", "Pipeline ROW km 14"],
    "MRN-S": ["OCS-1 Moran", "Well Pad MRN-22", "Power House", "Warehouse Yard"],
    "BKT-S": ["Drilling Rig SR-3", "Base Camp Bokakhat", "Well Pad BKT-3"],
    "HPJ-S": ["Gas Collecting Station Hapjan", "Compressor Station C-5", "Pipeline ROW km 32"],
    "TGK-S": ["Drilling Rig SR-5", "Well Pad TGK-9", "Mud Plant"],
}

ROLES = {
    "pump maintenance": ["Fitter", "Mechanical Technician", "Helper"],
    "hot work": ["Welder", "Fitter", "Fire Watch"],
    "lifting": ["Rigger", "Crane Operator", "Banksman", "Roustabout"],
    "confined-space entry": ["Tank Cleaner", "Fitter", "Helper"],
    "vehicle movement": ["Driver", "Tanker Driver", "Pedestrian Operator"],
    "drilling": ["Floorman", "Derrickman", "Driller", "Roustabout"],
    "electrical maintenance": ["Electrician", "Electrical Technician"],
    "pipeline work": ["Pipeline Fitter", "Welder", "Helper"],
    "work at height": ["Scaffolder", "Painter", "Insulator"],
    "loading/unloading": ["Tanker Driver", "Loading Operator", "Helper"],
    "well intervention": ["Wireline Operator", "CTU Operator", "Production Engineer"],
    "inspection": ["Production Operator", "Safety Officer", "Inspector"],
    "maintenance": ["Technician", "Helper", "Fitter"],
    "excavation": ["Excavator Operator", "Helper", "Civil Supervisor"],
}
CONTRACTORS = ["Contractor-A (synthetic)", "Contractor-B (synthetic)", "Contractor-C (synthetic)", "Contractor-D (synthetic)"]
WEATHER = ["Clear", "Clear", "Clear", "Rain", "Heavy Rain", "Fog", "High Wind", "Hot"]
PREFIXES = ["", "", "", "At {loc}, ", "During {shift} shift, ", "While working at {loc}, "]
SUFFIXES = ["", "", "", " Supervisor informed.", " Area made safe and corrective action raised.", " Discussed with the crew.", " Reported by the area operator.", " Matter reported to HSE."]


@dataclass
class Scenario:
    key: str
    activity: str
    report_types: tuple[str, ...]
    equipment: tuple[str, ...]
    texts: tuple[str, ...]
    ref_scl: str
    ref_lsr: str | None
    weight: float = 1.0
    sites: dict[str, float] = field(default_factory=dict)
    time_profile: str = "uniform"  # uniform | rising | falling
    injury: tuple[str, ...] = ("None",)


SCENARIOS: list[Scenario] = [
    # ---------------------------------------------------------------- energy isolation (recurring precursor)
    Scenario("iso_not_verified", "pump maintenance", ("Near Miss", "Unsafe Act"), ("Crude transfer pump", "Booster pump", "Injection pump"),
             ("During {activity}, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped.",
              "Fitter started removing the pump casing bolts but the suction and discharge isolation had not been verified. Trapped pressure was found when the drain was cracked.",
              "LOTO was not applied on the {equip} before seal replacement began. Residual pressure was noticed and work was halted.",
              "Maintenance crew opened the {equip} flange assuming it was isolated; isolation was not verified and pressure was still present in the line."),
             "EXPOSURE", "ENERGY_ISOLATION", 3.2, {"DGB-S": 2.5, "NHK-S": 2.0, "DLJ-S": 1.0}),
    Scenario("iso_release", "pump maintenance", ("Near Miss",), ("Crude transfer pump", "Mud pump"),
             ("While opening the {equip} discharge flange, residual pressure was released and crude oil sprayed towards the fitter. Isolation had not been verified. No injury.",
              "Pressure released from the pump casing when the cover was loosened because the line was not depressurised. The fitter stepped back and was not hurt."),
             "PSIF", "ENERGY_ISOLATION", 1.4, {"DGB-S": 2.0, "NHK-S": 1.5}),
    Scenario("iso_ok", "pump maintenance", ("Unsafe Condition", "Near Miss"), ("Booster pump", "Transfer pump"),
             ("Before {activity}, LOTO was applied and verified, and the line was depressurised. No residual pressure was found and work proceeded safely.",
              "Isolation was verified by the area operator and the {equip} was drained before the seal change."),
             "SUCCESS", "ENERGY_ISOLATION", 1.2),
    Scenario("elec_loto_missing", "electrical maintenance", ("Unsafe Act", "Near Miss"), ("415 V MCC panel", "Distribution panel", "Motor terminal box"),
             ("Electrician opened the {equip} without lockout tagout. The busbar was still energised.",
              "Work started on the {equip} while the circuit was live; LOTO was not applied and no voltage test was done.",
              "Electrical technician found the breaker of the {equip} was not locked out while cable termination was in progress."),
             "EXPOSURE", "ENERGY_ISOLATION", 1.6, {"DLJ-S": 1.5, "MRN-S": 1.5}),
    Scenario("elec_flash", "electrical maintenance", ("Incident",), ("415 V MCC panel",),
             ("An arc flash occurred when the electrician racked out a breaker in the {equip}. Arc-rated PPE was not worn. He received first aid for minor burns.",),
             "PSIF", "ENERGY_ISOLATION", 0.5, injury=("First Aid",)),
    # ---------------------------------------------------------------- hot work (rising trend at Duliajan)
    Scenario("hot_no_gas_test", "hot work", ("Unsafe Act", "Near Miss"), ("Welding set", "Grinder", "Gas cutting set"),
             ("During hot work, gas testing was not completed before welding began. Work was stopped when the issue was identified.",
              "Welding started near the separator without a gas test. The fire watch stopped the job.",
              "Grinding was carried out close to the crude tank manifold; gas testing had not been done and no fire blanket was in place.",
              "Gas cutting started on the flowline before the LEL check was carried out. Job suspended by the supervisor."),
             "EXPOSURE", "HOT_WORK", 3.0, {"DLJ-S": 3.5, "DGB-S": 1.0, "HPJ-S": 1.0}, "rising"),
    Scenario("hot_flash_fire", "hot work", ("Near Miss", "Incident"), ("Welding set",),
             ("Sparks from welding ignited hydrocarbon vapour near the drain; a small flash fire occurred. Gas testing had not been carried out. No one was injured.",
              "A flash fire occurred during grinding at the manifold. The area had not been gas tested. Fire was extinguished and nobody was hurt."),
             "PSIF", "HOT_WORK", 1.0, {"DLJ-S": 2.0}, "rising"),
    Scenario("hot_ok", "hot work", ("Unsafe Condition",), ("Welding set",),
             ("Hot work permit was valid, gas testing was completed and continuous gas monitoring was in place before welding on the header.",
              "Fire watch present, gas test done and fire blanket in place for the welding job."),
             "SUCCESS", "HOT_WORK", 1.0),
    Scenario("hot_permit_expired", "hot work", ("Unsafe Act",), ("Welding set", "Grinder"),
             ("Welding was continuing on the pipe rack after the hot work permit had expired. Work stopped for permit renewal.",
              "Crew carried out grinding without a valid permit to work near the gas line."),
             "EXPOSURE", "WORK_AUTHORIZATION", 1.0, {"HPJ-S": 1.5}),
    # ---------------------------------------------------------------- lifting / line of fire
    Scenario("lift_exclusion", "lifting", ("Unsafe Act", "Near Miss"), ("Mobile crane", "Hydra crane", "Pedestal crane"),
             ("During lifting operations, a worker entered the exclusion zone while a suspended load was moving.",
              "Rigger walked under the suspended load during the {equip} lift to guide it by hand; no tag line was used.",
              "Helper stood in the swing radius of the {equip} while the casing bundle was lifted. Barricade was not in place.",
              "Worker crossed the barricaded drop zone during the lift of a pump skid. Banksman stopped the lift."),
             "EXPOSURE", "SAFE_MECHANICAL_LIFTING", 2.6, {"DLJ-S": 1.5, "TGK-S": 1.5, "BKT-S": 1.5}),
    Scenario("lift_dropped", "lifting", ("Near Miss",), ("Hydra crane", "Mobile crane"),
             ("A sling parted during the lift and the load dropped two metres from the rigger. No exclusion zone had been set up. No injury.",
              "The load swung and struck the scaffold near a helper when the tag line was not used. Nobody was hurt."),
             "PSIF", "SAFE_MECHANICAL_LIFTING", 1.1, {"TGK-S": 2.0, "BKT-S": 1.5}),
    Scenario("lift_ok", "lifting", ("Unsafe Condition",), ("Mobile crane",),
             ("Lift plan was in place, exclusion zone barricaded and banksman present during the {equip} lift of the heat exchanger bundle.",
              "Tag lines were used and the barricade was maintained during the lift; the lift was completed safely."),
             "SUCCESS", "SAFE_MECHANICAL_LIFTING", 1.0),
    Scenario("lift_uncertified", "lifting", ("Unsafe Condition",), ("Chain block", "Hydra crane"),
             ("Uncertified slings were found in use at the rig for lifting operations; load chart not available in the crane cab.",),
             "EXPOSURE", "SAFE_MECHANICAL_LIFTING", 0.7),
    # ---------------------------------------------------------------- confined space
    Scenario("cs_no_monitoring", "confined-space entry", ("Unsafe Act", "Near Miss"), ("Crude storage tank", "Separator vessel", "Effluent sump"),
             ("Worker entered a confined space without atmospheric monitoring.",
              "Tank cleaner entered the {equip} without a gas test and without a standby person at the manhole.",
              "Entry into the {equip} was made before the confined space permit was issued; oxygen level was not checked."),
             "EXPOSURE", "CONFINED_SPACE", 1.8, {"DGB-S": 1.5, "MRN-S": 1.2}),
    Scenario("cs_h2s", "confined-space entry", ("Near Miss",), ("Effluent sump", "Separator vessel"),
             ("Personal H2S alarm activated inside the {equip}. Worker was not wearing breathing apparatus and exited immediately. No injury.",),
             "PSIF", "CONFINED_SPACE", 0.6),
    Scenario("cs_ok", "confined-space entry", ("Unsafe Condition",), ("Crude storage tank",),
             ("Confined space entry into the {equip} was done with continuous gas monitoring, forced ventilation and an attendant at the manhole.",),
             "SUCCESS", "CONFINED_SPACE", 0.7),
    # ---------------------------------------------------------------- driving / vehicles
    Scenario("veh_pedestrian", "vehicle movement", ("Unsafe Condition", "Near Miss"), ("Tanker", "Pick-up vehicle", "Trailer"),
             ("Vehicle movement occurred while a pedestrian was working nearby.",
              "A tanker was reversing at the gantry without a banksman while operators were walking behind it.",
              "Trailer reversed into the yard while a helper was working near the rear wheels; reverse alarm was not working."),
             "EXPOSURE", "DRIVING", 1.8, {"DGB-S": 1.5, "MRN-S": 1.5}),
    Scenario("veh_speeding", "vehicle movement", ("Unsafe Act",), ("Pick-up vehicle", "Bus"),
             ("Driver was speeding at 70 km/h on the field road against a 40 km/h speed limit, and was not wearing a seat belt.",
              "The {equip} driver was using a mobile phone while driving inside the plant."),
             "EXPOSURE", "DRIVING", 1.3),
    Scenario("veh_collision", "vehicle movement", ("Incident",), ("Pick-up vehicle",),
             ("The {equip} collided with a stationary trailer at low speed. The driver was wearing a seat belt and was unhurt.",),
             "CAPACITY", "DRIVING", 0.5),
    Scenario("veh_struck", "vehicle movement", ("Incident",), ("Forklift",),
             ("A reversing forklift struck a helper in the warehouse yard. He was hospitalised with a fractured leg. There was no pedestrian segregation.",),
             "HSIF", "DRIVING", 0.25, injury=("Serious Injury",)),
    # ---------------------------------------------------------------- height
    Scenario("height_no_tie", "work at height", ("Unsafe Act",), ("Scaffold", "Tank roof", "Pipe rack"),
             ("Scaffolder working at 5 m on the {equip} was not tied off; harness was worn but the lanyard was not attached.",
              "Painter on the tank roof was working near the unprotected edge without a harness.",
              "Insulator climbed onto the pipe rack at 6 m without fall protection."),
             "EXPOSURE", "WORKING_AT_HEIGHT", 1.8, {"DGB-S": 1.2, "DLJ-S": 1.2}),
    Scenario("height_arrested", "work at height", ("Near Miss",), ("Scaffold",),
             ("Scaffolder slipped at 6 m and the fall arrest system arrested the fall. Harness was tied off to an anchor point. No injury.",),
             "CAPACITY", "WORKING_AT_HEIGHT", 0.6),
    Scenario("height_ladder_fall", "work at height", ("Incident",), ("Ladder",),
             ("Technician fell from a 4 m ladder that was not secured and was hospitalised with a fracture.",),
             "HSIF", "WORKING_AT_HEIGHT", 0.25, injury=("Serious Injury",)),
    Scenario("height_guardrail", "work at height", ("Unsafe Condition",), ("Scaffold", "Elevated platform"),
             ("Guardrail missing on the {equip} at 4 m elevation near the ladder access.",
              "Handrail on the elevated platform was damaged and the toe board was missing."),
             "EXPOSURE", "WORKING_AT_HEIGHT", 1.2),
    # ---------------------------------------------------------------- bypassing safety controls
    Scenario("bypass_interlock", "maintenance", ("Unsafe Act",), ("Gas compressor", "Heater treater"),
             ("The high-pressure trip on the {equip} was bypassed to keep it running without authorisation.",
              "Operator found the ESD interlock on the {equip} jumpered out; no override approval was recorded."),
             "EXPOSURE", "BYPASSING_SAFETY_CONTROLS", 1.2, {"HPJ-S": 2.0, "DLJ-S": 1.0}),
    Scenario("guard_removed", "maintenance", ("Unsafe Condition",), ("Transfer pump", "Gas compressor"),
             ("Coupling guard on the {equip} had been removed and the pump was running with the rotating shaft exposed.",
              "Belt guard missing on the {equip}; rotating parts accessible from the walkway."),
             "EXPOSURE", "BYPASSING_SAFETY_CONTROLS", 1.2),
    # ---------------------------------------------------------------- drilling / well intervention
    Scenario("drill_dropped", "drilling", ("Near Miss",), ("Top drive", "Derrick"),
             ("A spanner fell from the monkey board and landed a metre from the floorman. Tools were not tethered. No injury.",
              "A bolt dropped from the derrick onto the rig floor near the driller during tripping. Nobody was hurt."),
             "PSIF", "LINE_OF_FIRE", 1.3, {"TGK-S": 2.0, "BKT-S": 2.0, "DLJ-S": 1.0}),
    Scenario("drill_rotary", "drilling", ("Unsafe Act",), ("Rotary table", "Top drive"),
             ("Floorman stepped close to the rotating rotary table to remove a slip without stopping the rotation.",
              "Roustabout's hand came near a pinch point while making up drill pipe; the tong was not secured."),
             "EXPOSURE", "LINE_OF_FIRE", 1.0, {"TGK-S": 1.5, "BKT-S": 1.5}),
    Scenario("drill_fracture", "drilling", ("Incident",), ("Elevator",),
             ("During tripping, a joint of drill pipe dropped from the elevator and struck the floorman's leg. He was hospitalised with a fracture.",),
             "HSIF", "LINE_OF_FIRE", 0.25, {"TGK-S": 2.0}, injury=("Serious Injury",)),
    Scenario("well_kick", "well intervention", ("Near Miss", "Incident"), ("BOP", "Wellhead"),
             ("During workover a kick was observed and the well was shut in. The BOP function test had not been done before the job.",
              "Influx noticed during coiled tubing operations; the stripper rubber was worn and had not been replaced. Well was shut in and nobody was hurt."),
             "PSIF", "PROCESS_SAFETY_NA", 0.7, {"TGK-S": 1.5, "MRN-S": 1.0}),
    Scenario("wireline_pressure", "well intervention", ("Unsafe Act",), ("Wellhead", "Lubricator"),
             ("Wireline crew started rigging down the lubricator before bleeding off wellhead pressure.",),
             "EXPOSURE", "ENERGY_ISOLATION", 0.7),
    # ---------------------------------------------------------------- pipelines / process safety
    Scenario("pipe_leak", "pipeline work", ("Incident", "Near Miss"), ("Flowline", "Trunk pipeline"),
             ("Crude oil leak from a corroded section of the {equip} at the ROW. Area cordoned and line depressurised. No ignition occurred.",
              "Gas release from the {equip} flange gasket; loss of containment isolated by the operator. No injury."),
             "CAPACITY", "PROCESS_SAFETY_NA", 1.0, {"NHK-S": 1.5, "HPJ-S": 1.5}),
    Scenario("pipe_hot_tap", "pipeline work", ("Unsafe Act",), ("Trunk pipeline",),
             ("Hot tapping on the live pipeline was started without a valid permit and without a job safety analysis.",),
             "EXPOSURE", "WORK_AUTHORIZATION", 0.5),
    Scenario("excavation_shoring", "excavation", ("Unsafe Condition",), ("Excavator",),
             ("Trench 2 m deep near the flowline had no shoring and workers were inside it.",
              "Excavation near the live pipeline was being done without a permit; trench walls were unsupported."),
             "EXPOSURE", "WORK_AUTHORIZATION", 0.8, {"NHK-S": 1.5, "HPJ-S": 1.2}),
    # ---------------------------------------------------------------- loading / unloading
    Scenario("load_overfill", "loading/unloading", ("Near Miss",), ("Tank lorry", "Loading arm"),
             ("During loading at the gantry, the tank lorry overflowed and condensate spilled on the ground. The high-level alarm was not working. No ignition.",),
             "PSIF", "PROCESS_SAFETY_NA", 0.6, {"DGB-S": 2.0}),
    Scenario("load_earthing", "loading/unloading", ("Unsafe Act",), ("Tank lorry",),
             ("Tank lorry loading was started without connecting the earthing clamp.",),
             "EXPOSURE", "PROCESS_SAFETY_NA", 0.5, {"DGB-S": 2.0}),
    # ---------------------------------------------------------------- low severity / housekeeping
    Scenario("housekeeping", "inspection", ("Unsafe Condition",), ("Walkway", "Workshop floor"),
             ("Housekeeping poor near the workshop, clutter on the walkway.",
              "Oil-soaked rags and debris on the floor of the {loc} workshop.",
              "Hoses left lying across the walkway creating a trip hazard."),
             "LOW_SEVERITY", None, 2.6),
    Scenario("signage", "inspection", ("Unsafe Condition",), ("Notice board", "First aid box"),
             ("Faded signage at the entrance of the pump house.",
              "First aid box in the control room found with expired items.",
              "Missing signage for the assembly point near the warehouse."),
             "LOW_SEVERITY", None, 1.8),
    Scenario("minor_cut", "maintenance", ("Incident",), ("Hand tool",),
             ("Helper received a minor cut on the finger while handling a damaged hand tool. First aid given.",
              "Technician got a minor bruise while carrying a toolbox. First aid treatment only."),
             "LOW_SEVERITY", None, 1.2, injury=("First Aid",)),
    Scenario("ppe_minor", "inspection", ("Unsafe Act",), ("PPE",),
             ("Worker in the office store was not wearing safety shoes.",
              "Helper was not wearing gloves while sweeping the workshop."),
             "LOW_SEVERITY", None, 1.0),
    Scenario("lsif_slip", "inspection", ("Incident",), ("Walkway",),
             ("Operator slipped on an oily walkway and fell on the same level. He was hospitalised with a fractured wrist.",),
             "LSIF", None, 0.3, injury=("Lost Time Injury",)),
    # ---------------------------------------------------------------- vague / insufficient information
    Scenario("vague_1", "maintenance", ("Unsafe Condition", "Unsafe Act"), ("Pump", "Valve"),
             ("Unsafe condition noticed near the pump house. Informed supervisor.",
              "Worker not following procedure at site.",
              "Contractor crew working without supervision near the well pad.",
              "Unsafe practice observed during the job, discussed with the crew."),
             "UNDETERMINED", None, 1.6),
    Scenario("vague_2", "maintenance", ("Near Miss", "Incident"), ("Valve", "Flange"),
             ("Leak observed at the flange of the {equip}.",
              "Something fell near the crew during the job.",
              "Valve handle broke during operation."),
             "UNDETERMINED", None, 1.0),
    # ---------------------------------------------------------------- off-vocabulary phrasings (realistic disagreement)
    Scenario("offvocab_pressure", "pump maintenance", ("Unsafe Act",), ("Transfer pump", "Booster pump"),
             ("Fitter started loosening the bonnet bolts on the {equip} while the casing was still full and the suction valve was only partly shut.",
              "Mechanic cracked open the drain on the pressurised {equip} without bleeding it first."),
             "EXPOSURE", "ENERGY_ISOLATION", 0.9),
    Scenario("offvocab_lift", "lifting", ("Unsafe Act",), ("Hydra crane",),
             ("Helper was guiding the swinging pipe bundle with his hands directly beneath the boom.",),
             "EXPOSURE", "SAFE_MECHANICAL_LIFTING", 0.6),
    Scenario("offvocab_cs", "confined-space entry", ("Unsafe Act",), ("Mud tank",),
             ("A helper climbed down into the mud tank to retrieve a fallen tool; no one checked the air inside first.",),
             "EXPOSURE", "CONFINED_SPACE", 0.5),
]

DEMO_CASES: list[dict[str, Any]] = [
    {"report_id": "SYN-DEMO-001", "report_type": "Near Miss", "site": "DGB-S", "location": "GGS-2 Digboi", "activity": "Pump maintenance", "equipment": "Crude transfer pump P-102",
     "description": "During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped.",
     "worker_role": "Fitter", "contractor": "Contractor-A (synthetic)", "injury_severity": "None", "shift": "Day", "weather": "Clear", "ref": ("EXPOSURE", "ENERGY_ISOLATION"), "days_ago": 4},
    {"report_id": "SYN-DEMO-002", "report_type": "Unsafe Act", "site": "DLJ-S", "location": "OCS-4 Duliajan", "activity": "Hot work", "equipment": "Welding set",
     "description": "During hot work, gas testing was not completed before welding began. Work was stopped when the issue was identified.",
     "worker_role": "Welder", "contractor": "Contractor-B (synthetic)", "injury_severity": "None", "shift": "Day", "weather": "Hot", "ref": ("EXPOSURE", "HOT_WORK"), "days_ago": 6},
    {"report_id": "SYN-DEMO-003", "report_type": "Unsafe Act", "site": "TGK-S", "location": "Drilling Rig SR-5", "activity": "Lifting", "equipment": "Mobile crane",
     "description": "During lifting operations, a worker entered the exclusion zone while a suspended load was moving.",
     "worker_role": "Rigger", "contractor": None, "injury_severity": "None", "shift": "Day", "weather": "High Wind", "ref": ("EXPOSURE", "SAFE_MECHANICAL_LIFTING"), "days_ago": 9},
    {"report_id": "SYN-DEMO-004", "report_type": "Unsafe Act", "site": "MRN-S", "location": "OCS-1 Moran", "activity": "Confined-space entry", "equipment": "Crude storage tank",
     "description": "Worker entered a confined space without atmospheric monitoring.",
     "worker_role": "Tank Cleaner", "contractor": "Contractor-C (synthetic)", "injury_severity": "None", "shift": "Day", "weather": "Clear", "ref": ("EXPOSURE", "CONFINED_SPACE"), "days_ago": 12},
    {"report_id": "SYN-DEMO-005", "report_type": "Unsafe Condition", "site": "DGB-S", "location": "Loading Gantry", "activity": "Vehicle movement", "equipment": "Tanker",
     "description": "Vehicle movement occurred while a pedestrian was working nearby.",
     "worker_role": "Loading Operator", "contractor": None, "injury_severity": "None", "shift": "Night", "weather": "Rain", "ref": ("EXPOSURE", "DRIVING"), "days_ago": 2},
]


# Synthetic site profiles so the ranking has something real to separate. Multiplies the
# weight of SIF-precursor scenarios (and divides low-severity ones) at each site.
SITE_PRECURSOR_PROFILE = {"DGB-S": 1.35, "BKT-S": 1.5, "TGK-S": 1.3, "NHK-S": 1.0, "DLJ-S": 0.9, "HPJ-S": 0.75, "MRN-S": 0.65}
PRECURSOR_CLASSES = ("PSIF", "EXPOSURE", "HSIF")


def _pick_weighted(rng: random.Random, items: list[Any], weights: list[float]) -> Any:
    return rng.choices(items, weights=weights, k=1)[0]


def _days_ago(rng: random.Random, profile: str, span: int) -> int:
    u = rng.random()
    if profile == "rising":
        return int(span * (1 - u ** 0.45))  # mass concentrated in recent weeks
    if profile == "falling":
        return int(span * u ** 0.6)
    return int(span * u)


def generate_reports(n: int = 280, seed: int = 26165, today: date | None = None, span_days: int = 365) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    today = today or date.today()
    weights = [s.weight for s in SCENARIOS]
    out: list[dict[str, Any]] = []
    for i in range(n):
        sc: Scenario = _pick_weighted(rng, SCENARIOS, weights)
        prof = [SITE_PRECURSOR_PROFILE[s["code"]] if sc.ref_scl in PRECURSOR_CLASSES else 1 / SITE_PRECURSOR_PROFILE[s["code"]] for s in SITES]
        site_w = [sc.sites.get(s["code"], 1.0) * (s["exposure_hours"] / 300_000) * p for s, p in zip(SITES, prof)]
        site = _pick_weighted(rng, SITES, site_w)
        loc = rng.choice(LOCATIONS[site["code"]])
        equip = rng.choice(sc.equipment)
        shift = rng.choices(["Day", "Night"], weights=[0.72, 0.28])[0]
        body = rng.choice(sc.texts).format(activity=sc.activity, equip=equip, loc=loc, shift=shift.lower())
        prefix = rng.choice(PREFIXES).format(loc=loc, shift=shift.lower())
        if prefix and body[0].isupper() and not body.startswith(("LOTO", "BOP", "H2S")):
            body = body[0].lower() + body[1:]
        desc = (prefix + body + rng.choice(SUFFIXES)).strip()
        desc = desc[0].upper() + desc[1:]
        rtype = rng.choice(sc.report_types)
        injury = rng.choice(sc.injury)
        contractor = rng.choice(CONTRACTORS) if rng.random() < 0.45 else None
        activity_label = sc.activity[0].upper() + sc.activity[1:]
        ref_sif = None if sc.ref_scl == "UNDETERMINED" else sc.ref_scl in ("PSIF", "EXPOSURE")
        out.append({
            "report_id": f"SYN-{today.year}-{i + 1:04d}",
            "report_type": rtype,
            "date": today - timedelta(days=_days_ago(rng, sc.time_profile, span_days)),
            "site": site["code"],
            "location": loc,
            "activity": activity_label,
            "equipment": equip,
            "description": desc,
            "worker_role": rng.choice(ROLES.get(sc.activity, ["Technician"])),
            "contractor": contractor,
            "injury_severity": injury,
            "shift": shift,
            "weather": rng.choice(WEATHER),
            "data_source": "synthetic_demo",
            "reference_scl_class": sc.ref_scl,
            "reference_sif_potential": ref_sif,
            "reference_lsr": sc.ref_lsr,
            "scenario": sc.key,
        })
    for d in DEMO_CASES:
        ref_scl, ref_lsr = d["ref"]
        rec = {k: v for k, v in d.items() if k not in ("ref", "days_ago")}
        rec.update({"date": today - timedelta(days=d["days_ago"]), "data_source": "synthetic_demo", "reference_scl_class": ref_scl, "reference_sif_potential": ref_scl in ("PSIF", "EXPOSURE"), "reference_lsr": ref_lsr, "scenario": "demo"})
        out.append(rec)
    out.sort(key=lambda r: r["date"])
    return out
