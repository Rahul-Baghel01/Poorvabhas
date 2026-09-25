"""Structured safety vocabulary.

Each entry maps many surface forms (regex, case-insensitive, matched on the ORIGINAL
text so evidence offsets stay valid) to one canonical concept. Abbreviations and
synonyms (LOTO / lock out / lockout ...) resolve to the same canonical term.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Term:
    canonical: str
    patterns: tuple[str, ...]
    confidence: float = 0.9
    attrs: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- abbreviations
ABBREVIATIONS: dict[str, str] = {
    "LOTO": "lockout tagout",
    "PTW": "permit to work",
    "PPE": "personal protective equipment",
    "JSA": "job safety analysis",
    "JHA": "job hazard analysis",
    "BOP": "blowout preventer",
    "SIMOPS": "simultaneous operations",
    "H2S": "hydrogen sulphide",
    "LEL": "lower explosive limit",
    "TBT": "toolbox talk",
    "SWL": "safe working load",
    "ESD": "emergency shutdown",
    "PSV": "pressure safety valve",
    "MCC": "motor control centre",
    "SCBA": "self contained breathing apparatus",
    "MOC": "management of change",
    "HV": "high voltage",
    "LV": "low voltage",
    "GGS": "group gathering station",
    "OCS": "oil collecting station",
    "CTU": "coiled tubing unit",
}

# --------------------------------------------------------------------------- energy sources
# attrs.high: whether the energy is "high energy" in the SCL sense (capable of SIF).
ENERGY: tuple[Term, ...] = (
    Term("residual pressure", (r"residual pressure", r"trapped pressure", r"stored pressure", r"pressure (?:was )?(?:still )?(?:present|trapped)"), 0.94, {"high": True, "family": "pressure"}),
    Term("pressure", (r"high[- ]pressure", r"line pressure", r"pressuri[sz]ed", r"under pressure", r"pressure build[- ]?up", r"\bpressure\b", r"\bpsi\b", r"\bbar\b(?!ricad)"), 0.85, {"high": True, "family": "pressure"}),
    Term("stored energy", (r"stored energy", r"spring tension", r"compressed spring", r"tensioned (?:line|cable|sling)"), 0.88, {"high": True, "family": "mechanical"}),
    Term("well pressure", (r"well ?control", r"\bkick\b", r"\binflux\b", r"wellhead pressure", r"\bBOP\b", r"blow ?out(?! preventer)", r"blowout preventer"), 0.9, {"high": True, "family": "pressure"}),
    Term("electrical", (r"\blive (?:cable|conductor|panel|line|circuit|terminal|busbar|wire)s?", r"(?<!de-)(?<!de)energi[sz]ed", r"high voltage", r"\bHV\b", r"\b\d{2,3} ?kV\b", r"\b(?:415|440|11000|6600|3300) ?V\b", r"arc flash", r"electric(?:al)? shock", r"exposed (?:wire|conductor|terminal)s?", r"electrocut\w*", r"switchgear", r"\bMCC\b", r"\bbusbar"), 0.9, {"high": True, "family": "electrical"}),
    Term("suspended load", (r"suspended load", r"load (?:was )?(?:swinging|swung|suspended|being lifted)", r"overhead load", r"under (?:a|the) (?:suspended |raised )?load", r"(?:suspended )?load (?:was )?(?:moving|in motion)", r"lifted load", r"(?:bundle|load|skid|spool|pipes?|casing|exchanger) (?:was |were |being )+(?:lifted|hoisted|raised)", r"(?:crane|hydra) lift of", r"lift of (?:the |a )?(?:[\w-]+ ){0,3}(?:bundle|skid|spool|load|casing|exchanger|pump)"), 0.93, {"high": True, "family": "gravity"}),
    Term("dropped object", (r"dropped objects?", r"falling objects?", r"object (?:fell|dropped)", r"(?:spanner|wrench|tool|bolt|pipe|hammer) (?:fell|dropped|slipped)"), 0.88, {"high": True, "family": "gravity"}),
    Term("height", (r"at height", r"\belevated\b", r"\bscaffold(?:ing|s)?\b", r"\bladder\b", r"\broof\b", r"unprotected edge", r"open edge", r"fall from", r"monkey ?board", r"\bderrick\b", r"\b\d+(?:\.\d+)? ?(?:m|metres|meters|ft|feet) (?:high|above|elevation|up)", r"\bat (?:a height of )?\d+(?:\.\d+)? ?(?:m|metres|meters|ft|feet)\b", r"elevated platform", r"\bmezzanine\b", r"pipe ?rack", r"tank roof"), 0.86, {"high": True, "family": "gravity"}),
    Term("mobile equipment", (r"\bvehicles?\b", r"\btrucks?\b", r"\btankers?\b", r"\bforklifts?\b", r"\breversing\b", r"mobile equipment", r"\bdumper\b", r"\bpick-?up\b", r"\bbus\b", r"\btrailer\b", r"\bspeeding\b", r"\b\d{2,3} ?km/?h\b", r"\bexcavator\b", r"\bJCB\b", r"\bhydra\b"), 0.85, {"high": True, "family": "kinetic"}),
    Term("rotating equipment", (r"\brotating\b", r"\brotation\b", r"rotary table", r"top drive", r"moving parts", r"unguarded (?:shaft|coupling|belt|pulley)", r"\bcoupling\b", r"\bdrawworks\b", r"\bconveyor\b", r"\bspinning\b", r"\bcathead\b"), 0.86, {"high": True, "family": "mechanical"}),
    Term("pinch point", (r"pinch points?", r"caught between", r"crush(?:ed|ing)? (?:between|hazard)"), 0.85, {"high": True, "family": "mechanical"}),
    Term("hydrocarbon / flammable", (r"\bhydrocarbons?\b", r"\bflammable\b", r"gas (?:release|leak)", r"crude (?:oil )?(?:leak|spill|release)", r"condensate", r"\bLPG\b", r"natural gas", r"\bvapou?rs?\b", r"explosive atmosphere", r"\bLEL\b", r"lower explosive limit"), 0.88, {"high": True, "family": "chemical"}),
    Term("ignition source", (r"\bwelding\b", r"\bgrinding\b", r"gas cutting", r"cutting torch", r"\bsparks?\b", r"open flame", r"naked flame", r"ignition source", r"hot work"), 0.8, {"high": True, "family": "thermal"}),
    Term("fire / explosion", (r"\bfire\b(?! (?:extinguisher|blanket|watch|barrier|drill|alarm|hydrant|hose|fighting))", r"flash fire", r"\bexplosion\b", r"\bexploded\b", r"\bignited\b", r"caught fire"), 0.9, {"high": True, "family": "thermal"}),
    Term("toxic atmosphere", (r"\bH2S\b", r"hydrogen sulph?f?ide", r"\btoxic\b", r"oxygen[- ]deficien\w*", r"atmospheric hazard", r"asphyxia\w*", r"\binert gas\b", r"nitrogen purge"), 0.9, {"high": True, "family": "chemical"}),
    Term("confined space atmosphere", (r"confined spaces?", r"vessel entry", r"tank entry", r"inside the (?:tank|vessel|drum|separator|pit)"), 0.78, {"high": True, "family": "chemical", "implied": True}),
    Term("thermal", (r"hot surface", r"\bsteam\b", r"\bmolten\b", r"high temperature", r"\bscald\w*", r"hot oil"), 0.84, {"high": True, "family": "thermal"}),
    Term("chemical", (r"\bchemicals?\b", r"\bcorrosive\b", r"\bacid\b", r"\bcaustic\b", r"\bmethanol\b"), 0.75, {"high": True, "family": "chemical"}),
    Term("excavation", (r"\btrench\b", r"\bexcavation\b", r"cave-?in", r"wall collapse"), 0.85, {"high": True, "family": "gravity"}),
)

# Low-energy hazards: evidence that the hazard is NOT high energy.
LOW_ENERGY: tuple[Term, ...] = (
    Term("housekeeping", (r"housekeeping", r"\bclutter\w*", r"untidy", r"debris on (?:the )?(?:floor|walkway)"), 0.8),
    Term("slip / trip same level", (r"\bslip(?:ped|pery)?\b", r"\btrip(?:ped|ping)? (?:hazard|over)", r"uneven (?:floor|surface|ground)"), 0.7),
    Term("signage / documentation", (r"missing sign\w*", r"faded sign\w*", r"\bsignage\b", r"expired first[- ]aid", r"first[- ]aid (?:box|kit)", r"notice board", r"logbook"), 0.8),
    Term("ergonomic / minor", (r"ergonomic\w*", r"manual handling of (?:light|small)", r"paper cut", r"minor (?:cut|bruise|abrasion|scratch)", r"carrying (?:a|the) (?:toolbox|box|bag|carton)", r"\bdust\b", r"poor lighting in (?:the )?office", r"office"), 0.7),
    Term("hand tool condition", (r"(?:damaged|worn) hand tools?", r"mushroomed (?:chisel|head)", r"loose handle"), 0.7),
)

# --------------------------------------------------------------------------- barriers / controls
# attrs.direct: a direct control targets the high-energy source and remains effective
# even with unintentional human error (SCL definition). Admin controls are not direct.
BARRIERS: tuple[Term, ...] = (
    Term("energy isolation", (r"lock[- ]?out(?:[/ -]?(?:and[/ -]?)?tag[- ]?out)?", r"locked[- ]out", r"tagged[- ]out", r"bleed(?:ing)?(?: (?:it )?(?:off|down))?(?: (?:the )?(?:wellhead |line |casing )?pressure)?", r"bled (?:off|down)", r"\bLOTO\b", r"tag[- ]?out", r"\bisolation\b", r"\bisolated\b", r"\bisolate\b", r"de-?energi[sz]\w+", r"double block and bleed", r"positive isolation", r"blind(?:ed)? flange", r"spaded", r"\bblinded\b", r"depressuri[sz]\w+", r"line (?:was )?(?:drained|vented)"), 0.92, {"direct": True, "lsr": "ENERGY_ISOLATION"}),
    Term("gas testing", (r"gas test\w*", r"gas monitor\w*", r"atmospheric (?:monitoring|testing|test|check)", r"gas detector", r"gas meter", r"\b4-gas\b", r"(?:LEL|H2S|oxygen) (?:check|reading|monitoring|test)", r"gas free certificate", r"personal gas monitor"), 0.92, {"direct": True, "lsr": "HOT_WORK"}),
    Term("exclusion zone", (r"exclusion zones?", r"barricad\w*", r"cordon(?:ed)?(?: off)?", r"restricted area", r"drop zone", r"no[- ]go zone", r"red zone"), 0.9, {"direct": True, "lsr": "LINE_OF_FIRE"}),
    Term("fall protection", (r"\bharness\w*", r"\blanyard\w*", r"fall arrest\w*", r"\bguard ?rails?\b", r"\bhand ?rails?\b", r"\btoe ?boards?\b", r"tie[d]?[- ]off", r"tied off", r"anchor points?", r"safety net", r"life ?line"), 0.9, {"direct": True, "lsr": "WORKING_AT_HEIGHT"}),
    Term("machine guarding", (r"machine guards?", r"guarding", r"\bguards?\b(?! ?rail)", r"safety cover", r"coupling guard", r"belt guard"), 0.88, {"direct": True, "lsr": "BYPASSING_SAFETY_CONTROLS"}),
    Term("dropped-object prevention", (r"\btether\w*", r"tool lanyards?", r"dropped[- ]objects? (?:prevention|survey|net)", r"secondary retention"), 0.86, {"direct": True, "lsr": "LINE_OF_FIRE"}),
    Term("well control barrier", (r"BOP (?:function |pressure )?test\w*", r"well control equipment", r"stripper rubber", r"kill line", r"barrier test\w*", r"(?:BOP|annular) (?:was|were) (?:closed|functioned)"), 0.88, {"direct": True, "lsr": None}),
    Term("safety interlock / trip", (r"\binterlocks?\b", r"trip system", r"(?:high|low)[- ](?:pressure|level|temperature) trip", r"\btrips?\b(?! hazard| over| and)", r"\bESD\b", r"emergency shut ?down", r"pressure safety valve", r"\bPSV\b", r"relief valve", r"safety instrumented", r"shutdown system", r"gas detection system", r"fire detection", r"override\w*", r"crown[- ]?o[- ]?matic", r"anti-two[- ]block", r"load moment indicator", r"\bLMI\b"), 0.88, {"direct": True, "lsr": "BYPASSING_SAFETY_CONTROLS"}),
    Term("ventilation", (r"forced ventilation", r"\bventilat\w+", r"air mover", r"blower"), 0.8, {"direct": True, "lsr": "CONFINED_SPACE"}),
    Term("pedestrian separation", (r"pedestrian (?:walkway|segregation|separation)", r"segregat\w+", r"traffic management", r"walkway"), 0.82, {"direct": True, "lsr": "DRIVING"}),
    Term("seat belt", (r"seat ?belts?",), 0.88, {"direct": True, "lsr": "DRIVING"}),
    Term("lifting controls", (r"tag ?lines?", r"lift(?:ing)? plan", r"load chart", r"\bSWL\b", r"safe working load", r"rigging (?:inspection|check)", r"certified slings?", r"outriggers?"), 0.84, {"direct": True, "lsr": "SAFE_MECHANICAL_LIFTING"}),
    Term("earthing / bonding", (r"earthing(?: clamp| cable| connection)?", r"\bbonding\b", r"static (?:earth|ground)\w*"), 0.86, {"direct": True, "lsr": None}),
    Term("excavation support", (r"\bshoring\b", r"trench (?:box|support)", r"\bbenching\b", r"sloped walls?"), 0.86, {"direct": True, "lsr": None}),
    Term("fire barrier", (r"fire blankets?", r"spark (?:containment|guard|shield)", r"fire barrier", r"welding screen", r"fire[- ]resistant cover"), 0.84, {"direct": True, "lsr": "HOT_WORK"}),
    # --- administrative / non-direct controls
    Term("permit to work", (r"permit to work", r"\bPTW\b", r"work permit", r"hot work permit", r"confined space permit", r"\bpermits?\b", r"\bauthori[sz]ation\b", r"\bauthori[sz]ed\b", r"\bunauthori[sz]ed\b"), 0.9, {"direct": False, "lsr": "WORK_AUTHORIZATION"}),
    Term("spotter / banksman", (r"\bspotters?\b", r"\bbanksman\b", r"\bflagman\b", r"\bsignal ?man\b", r"\bsignaller\b", r"\bsignalperson\b"), 0.88, {"direct": False, "lsr": "SAFE_MECHANICAL_LIFTING"}),
    Term("standby / attendant", (r"standby (?:person|man)", r"\battendant\b", r"hole watch", r"fire watch\w*", r"rescue (?:plan|team)"), 0.86, {"direct": False, "lsr": "CONFINED_SPACE"}),
    Term("PPE", (r"\bPPE\b", r"personal protective equipment", r"\bgloves\b", r"\bgoggles\b", r"face ?shield", r"\brespirator\b", r"breathing apparatus", r"\bSCBA\b", r"hard ?hat", r"\bhelmet\b", r"safety (?:shoes|boots|glasses)", r"\bFR ?coverall\w*", r"ear (?:plugs|muffs)"), 0.8, {"direct": False, "lsr": None}),
    Term("job safety analysis", (r"\bJSA\b", r"\bJHA\b", r"job safety analysis", r"risk assessment", r"toolbox talk", r"\bTBT\b", r"pre-?job (?:briefing|meeting)", r"method statement", r"\bprocedure\b", r"\bSOP\b"), 0.75, {"direct": False, "lsr": None}),
    Term("fire extinguisher", (r"fire extinguishers?", r"fire hose", r"hydrant"), 0.8, {"direct": False, "lsr": None}),
    Term("warning device", (r"reverse (?:alarm|horn)", r"reversing (?:alarm|horn)", r"\balarm\b", r"beacon", r"warning (?:sign|light)"), 0.75, {"direct": False, "lsr": None}),
    Term("speed limit", (r"speed limit", r"journey management", r"journey plan"), 0.82, {"direct": False, "lsr": "DRIVING"}),
)

# --------------------------------------------------------------------------- barrier state cues
# Failure/absence cues immediately BEFORE a barrier term.
BARRIER_FAIL_PREFIX = (
    r"without(?: (?:a|an|the|any|valid|proper|adequate))*",
    r"\bno(?: (?:valid|proper|adequate|functioning|working))?",
    r"missing",
    r"lack of(?: (?:a|an|the))?",
    r"absence of(?: (?:a|an|the))?",
    r"not wearing(?: (?:a|an|the|his|her|their))?",
    r"(?:failed|forgot) to (?:use|apply|verify|wear|obtain|isolate|carry out|complete|conduct|install|put on|set up)(?: (?:a|an|the))?",
    r"did not (?:use|apply|verify|wear|obtain|have|carry out|complete|conduct|set up|install)(?: (?:a|an|the))?",
    r"(?:bypass(?:ed|ing)?|defeat(?:ed|ing)?|disabl(?:ed|ing)|overrid(?:den|ing)|remov(?:ed|ing)|jump(?:ed|ering)|inhibit(?:ed|ing))(?: (?:a|an|the))?",
    r"(?:improper|inadequate|incomplete|expired|unverified|ineffective|damaged|broken|defective|faulty|uncertified)",
    r"\bbefore",
    r"(?:was|were|is|are|had|has)(?: been)? not",
    r"(?:entered|entering|inside|within|into|breach(?:ed|ing)?|crossed|stood in|standing in|walked into)(?: (?:a|an|the))?",
)
# Failure/absence cues AFTER a barrier term (same clause).
BARRIER_FAIL_SUFFIX = (
    r"(?:(?:was|were|had|has|is|are)(?: (?:been|also))? )?not (?:been )?(?:verified|completed|done|carried out|performed|applied|in place|used|worn|obtained|available|installed|tested|conducted|checked|present|attached|tied(?: off)?|functioning|working|followed|issued|signed|established|isolated|set up|positioned|deployed|maintained)",
    r"(?:was|were|had|has|is|are)(?: (?:been|also))? not\b",
    r"(?:wasn't|weren't|hadn't|isn't|aren't)",
    r"(?:had been |was |were )?(?:bypassed|defeated|overridden|disabled|removed|jumpered|inhibited|isolated out)",
    r"(?:had |has )?expired",
    r"(?:was |were )?(?:missing|absent|breached|damaged|broken|defective|inadequate|incomplete|ineffective|faulty|out of service|unattended|left open)",
    r"(?:was |were )?(?:skipped|ignored|not followed)",
    r"(?:failed|malfunctioned)",
)
# Presence/effectiveness cues.
BARRIER_OK_PREFIX = (
    r"(?:valid|verified|approved|correct(?:ly)?|proper(?:ly)?|effective|functional|functioning|certified|continuous|installed|intact|adequate)",
    r"(?:wearing|using|with (?:a |an |the )?(?:valid |proper |correct )?|under (?:a |an |the )?(?:valid )?)",
)
BARRIER_OK_SUFFIX = (
    r"(?:was|were|had been|has been|is|are) (?:verified|confirmed|applied|completed|in place|installed|carried out|obtained|worn|used|tested|conducted|attached|tied off|maintained|established|functional|intact|effective|issued|valid|activated|done|checked|set up)",
    r"\bin place\b",
    r"(?:barricaded|cordoned off|present|provided|available|secured|established)\b",
    r"(?:functioned|activated|operated|worked|held|prevented|arrested|stopped|contained|tripped)",
)

# --------------------------------------------------------------------------- high-energy event (release / contact)
EVENT_YES = (
    r"\breleas(?:ed|e of)\b", r"\bsprayed\b", r"\bburst\b", r"\bruptur\w+", r"\bblew (?:out|off)\b", r"\bstruck\b", r"\bhit (?:the|a|his|her)\b",
    r"\bfell\b", r"\bdropped\b", r"\bcollaps\w+", r"caught fire", r"\bignited\b", r"flash fire", r"\bexplo(?:sion|ded)\b", r"\bleak(?:ed|ing|age)?\b",
    r"loss of containment", r"\bswung\b", r"tipped over", r"\boverturn\w*", r"rolled over", r"\bcollided\b", r"\bcollision\b", r"\bcontact with (?:a |the )?live",
    r"received (?:an? )?(?:electric(?:al)? )?shock", r"arc flash occurred", r"\bkick\b", r"\binflux\b", r"\buncontrolled\b", r"\bparted\b", r"\bsnapped\b",
    r"\bwhipped\b", r"gas alarm (?:activated|triggered|sounded)", r"H2S alarm (?:activated|triggered|sounded)", r"\bsprung\b", r"\bdislodged\b",
    r"narrowly missed", r"arrested (?:the|his|her|their) fall", r"fall was arrested", r"slipped(?= (?:and|from|off))", r"missed (?:the |a )?(?:worker|him|her|operator|crew)", r"struck by", r"came into contact", r"pinned\b", r"\bslipped (?:from|off)\b",
)
EVENT_NO = (
    r"(?:task|work|job|activity|operation|lift) was (?:stopped|halted|suspended)", r"stop(?:ped)? (?:the )?work", r"\bstopped before\b", r"identified before",
    r"prior to (?:start|commencement|opening)", r"no (?:release|leak|spill|fire|ignition|contact)", r"nothing (?:fell|was released)",
    r"(?:was|were) observed", r"\bobserved\b", r"\bnoticed\b", r"\bfound\b", r"\bspotted\b", r"during (?:inspection|audit|walkdown|patrol)",
)
EVENT_NEGATION = r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bnothing\b|did not|didn't|was prevented|avoid(?:ed)?)"

# --------------------------------------------------------------------------- injury
INJURY_YES = (
    r"\bfatal\w*", r"\bdied\b", r"\bdeath\b", r"\bamputat\w+", r"\bfractur\w+", r"\bhospitali[sz]\w+", r"\bunconscious\w*",
    r"severe burns?", r"(?:second|third)[- ]degree burns?", r"crush injur\w+", r"loss of consciousness", r"life[- ]threatening", r"internal injur\w+",
    r"broken (?:leg|arm|pelvis|ribs?|back|neck)", r"head injury", r"spinal injury",
)
INJURY_NO = (
    r"no (?:one|person|worker|personnel)? ?(?:was )?(?:hurt|injured|harmed)", r"(?:was|were) not (?:hurt|injured|harmed)", r"nobody was (?:hurt|injured|harmed)", r"no injur\w+", r"without injur\w+", r"\bunhurt\b", r"\bunharmed\b",
    r"no (?:harm|casualt\w+)", r"escaped (?:unhurt|without)", r"minor (?:cut|bruise|abrasion|injury|scratch)", r"first[- ]aid (?:only|treatment|case)",
)
INJURY_SEVERITY_FIELD = {
    "none": ("NO", 0.95),
    "no injury": ("NO", 0.95),
    "first aid": ("NO", 0.9),
    "medical treatment": ("NO", 0.8),
    "restricted work": ("NO", 0.72),
    "lost time": ("INSUFFICIENT", 0.5),
    "lost time injury": ("INSUFFICIENT", 0.5),
    "serious injury": ("YES", 0.95),
    "serious": ("YES", 0.9),
    "fatality": ("YES", 0.99),
    "fatal": ("YES", 0.99),
}

# --------------------------------------------------------------------------- activities
ACTIVITIES: tuple[Term, ...] = (
    Term("pump maintenance", (r"pump (?:maintenance|overhaul|repair|servicing|seal replacement)", r"(?:maintenance|overhaul|repair|servicing) (?:of|on) (?:the |a )?(?:\w+ )?pump", r"pump maintenance"), 0.92),
    Term("hot work", (r"hot work", r"\bwelding\b", r"\bgrinding\b", r"gas cutting", r"cutting torch", r"\bbrazing\b"), 0.9),
    Term("lifting", (r"lifting operations?", r"\blifting\b", r"\bcrane\b", r"\bhoist\w*", r"\brigging\b(?! down| up)", r"\blift\b", r"\bhydra\b", r"chain block"), 0.88),
    Term("confined-space entry", (r"confined[- ]space(?: entry)?", r"vessel entry", r"tank entry", r"entered the (?:tank|vessel|drum|separator|pit|sump)"), 0.92),
    Term("vehicle movement", (r"vehicle movement", r"\bdriving\b", r"\breversing\b", r"(?:truck|tanker|vehicle|bus|trailer) (?:was )?(?:moving|reversing|travelling|manoeuvring|maneuvering)", r"convoy", r"road transport"), 0.88),
    Term("drilling", (r"\bdrilling\b", r"\btripping\b", r"rig floor", r"pipe handling", r"make[- ]up of (?:drill )?pipe", r"\bspudding\b", r"drill floor"), 0.88),
    Term("electrical maintenance", (r"electrical (?:maintenance|work|isolation|repair|testing)", r"\bswitchgear\b", r"\bpanel (?:maintenance|work)", r"\bMCC\b", r"cable (?:termination|jointing)", r"motor (?:rewinding|terminal)"), 0.88),
    Term("pipeline work", (r"pipeline", r"\bpigging\b", r"flange (?:work|replacement|joint)", r"hot tap\w*", r"line (?:repair|replacement|cutting)"), 0.86),
    Term("work at height", (r"work(?:ing)? at height", r"\bscaffold(?:ing|s)?\b", r"\bladder\b", r"elevated (?:work|platform)", r"tank roof", r"monkey ?board", r"pipe ?rack"), 0.86),
    Term("loading/unloading", (r"\bloading\b", r"\bunloading\b", r"offloading", r"tank lorry", r"bay (?:loading|filling)", r"transfer of (?:crude|product|chemicals?)"), 0.84),
    Term("well intervention", (r"well intervention", r"\bworkover\b", r"\bwireline\b", r"coiled tubing", r"well servicing", r"\bslickline\b", r"\bCTU\b", r"well testing"), 0.88),
    Term("excavation", (r"\bexcavation\b", r"\btrench\w*", r"\bdigging\b"), 0.86),
    Term("inspection", (r"\binspection\b", r"\bpatrol\b", r"walk ?down", r"\baudit\b", r"site visit"), 0.75),
    Term("maintenance", (r"\bmaintenance\b", r"\bservicing\b", r"\brepair\b", r"\boverhaul\b"), 0.7),
)

# --------------------------------------------------------------------------- behaviours / context
HUMAN_BEHAVIOR: tuple[Term, ...] = (
    Term("entered danger zone", (r"(?:entered|walked into|stepped into|stood (?:in|under)|standing (?:in|under|beneath)|positioned (?:himself|herself|themselves)? ?(?:in|under))(?: the| a)? (?:exclusion zone|line of fire|drop zone|swing (?:radius|path)|red zone|danger zone|suspended load)", r"under (?:a|the) (?:suspended|raised) load", r"in the line of fire", r"stepped close to the (?:rotating|moving)", r"hands? (?:came|was|were) (?:near|close to|inside)", r"reached into", r"directly (?:beneath|under) the (?:boom|load)", r"workers were inside (?:it|the trench)"), 0.9),
    Term("bypassed control", (r"\bbypass\w*", r"\bdefeat\w*", r"\boverrid\w*", r"\bjumper\w*", r"\binhibit\w*", r"disabled the"), 0.88),
    Term("did not follow procedure", (r"did not follow", r"not following", r"deviat\w+ from (?:the )?procedure", r"short[- ]?cut", r"without (?:informing|authori[sz]ation|approval)", r"skipped"), 0.85),
    Term("failed to verify", (r"not verified", r"did not verify", r"without verif\w+", r"failed to (?:verify|check|confirm)", r"assumed"), 0.85),
    Term("rushing / time pressure", (r"\brush\w*", r"time pressure", r"\bhurr\w+", r"to save time"), 0.8),
    Term("distraction", (r"mobile phone", r"distract\w*", r"not paying attention"), 0.8),
    Term("pedestrian exposure", (r"\bpedestrians?\b", r"walking (?:behind|near|beside)", r"working (?:nearby|near|close to)", r"on foot"), 0.85),
    Term("stopped work (intervention)", (r"(?:task|work|job|activity|operation|lift) was (?:stopped|halted|suspended)", r"stop[- ]work", r"stopped the (?:job|work|task)"), 0.9),
)

ENVIRONMENT: tuple[Term, ...] = (
    Term("night / low light", (r"\bnight\b", r"poor (?:lighting|visibility)", r"\bdark\w*", r"low light"), 0.85),
    Term("adverse weather", (r"\brain\w*", r"high wind\w*", r"strong wind\w*", r"\bstorm\w*", r"\bfog\w*", r"monsoon", r"lightning", r"flood\w*", r"\bheat\b", r"slippery"), 0.8),
    Term("simultaneous operations", (r"\bSIMOPS\b", r"simultaneous operations?", r"another crew", r"parallel (?:job|work|activit\w+)"), 0.85),
    Term("congested area", (r"congest\w+", r"restricted access", r"cramped", r"tight space"), 0.8),
    Term("live plant", (r"live plant", r"operating (?:plant|unit)", r"process (?:was )?(?:running|online|live)", r"\bonline\b"), 0.8),
)

EQUIPMENT_PATTERNS: tuple[Term, ...] = (
    Term("pump", (r"(?:centrifugal |reciprocating |transfer |booster |mud |crude |injection )?pumps?",), 0.85),
    Term("crane", (r"(?:mobile |overhead |crawler |pedestal )?cranes?", r"\bhydra\b"), 0.88),
    Term("valve", (r"(?:gate |ball |check |isolation |control |relief )?valves?",), 0.8),
    Term("pipeline / flowline", (r"pipelines?", r"flow ?lines?", r"trunk line"), 0.8),
    Term("pressure vessel", (r"separator", r"pressure vessel", r"\bheater treater\b", r"knock[- ]out drum", r"\bdrum\b"), 0.8),
    Term("storage tank", (r"(?:storage |crude |slop )?tanks?(?! lorry)",), 0.75),
    Term("vehicle", (r"\bvehicles?\b", r"\btrucks?\b", r"\btankers?\b", r"tank lorry", r"\bforklifts?\b", r"\bbus\b", r"\btrailer\b"), 0.85),
    Term("electrical panel", (r"(?:electrical |distribution |control )?panels?", r"switchgear", r"\bMCC\b", r"transformer", r"\bbusbar"), 0.82),
    Term("wellhead / BOP", (r"wellhead", r"christmas tree", r"\bBOP\b", r"blowout preventer"), 0.88),
    Term("compressor", (r"compressors?",), 0.85),
    Term("scaffold / ladder", (r"\bscaffold(?:ing|s)?\b", r"\bladders?\b"), 0.82),
    Term("welding set", (r"welding (?:set|machine|generator)", r"gas cylinders?", r"oxy[- ]?acetylene"), 0.82),
    Term("drilling rig", (r"\brig\b", r"top drive", r"rotary table", r"drawworks", r"\bderrick\b"), 0.85),
)

# Hazard derivation: (hazard name, energy families or canonicals that trigger it)
HAZARD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("uncontrolled release of pressure", ("residual pressure", "pressure", "well pressure", "stored energy")),
    ("struck by suspended / falling load", ("suspended load", "dropped object")),
    ("fall from height", ("height",)),
    ("struck by mobile equipment", ("mobile equipment",)),
    ("electrocution / arc flash", ("electrical",)),
    ("fire / explosion", ("hydrocarbon / flammable", "ignition source", "fire / explosion")),
    ("toxic or oxygen-deficient atmosphere", ("toxic atmosphere", "confined space atmosphere")),
    ("caught in / between", ("rotating equipment", "pinch point")),
    ("burns / thermal contact", ("thermal",)),
    ("chemical exposure", ("chemical",)),
    ("engulfment / trench collapse", ("excavation",)),
)

REPORT_TYPES = ("Unsafe Act", "Unsafe Condition", "Near Miss", "Incident")
INJURY_SEVERITIES = ("None", "First Aid", "Medical Treatment", "Restricted Work", "Lost Time Injury", "Serious Injury", "Fatality")
