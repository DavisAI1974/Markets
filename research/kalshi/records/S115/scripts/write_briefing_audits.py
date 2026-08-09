import json, collections

# A-17 is re-scoped, not closed - the report's own instruction.
P="OPEN_ITEMS.json"
d=json.load(open(P,encoding="utf-8"),object_pairs_hook=collections.OrderedDict)
a17=next(i for i in d["items"] if i["id"]=="A-17")
note=("\n\nSPLIT AT S115 ON THE DELIVERED REPORT'S OWN FINAL BUILD DECISION "
      "(CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md section 8, audited under D36): **A-17 must NOT be "
      "closed as 'forward nuclear unit schedule solved'.** It was one item covering four data "
      "realities with four different answers - A-17A public aggregate forward outage capacity "
      "(buildable now, ERCOT/PJM/MISO/SPP), A-17B public unit-level refuelling calendar (SEARCHED "
      "AND FOUND NOTHING - a measured public-data gap, D24 case 2), A-17C realized unit truth from "
      "the NRC (buildable now), A-17D coal additions/retirements from EIA-860M (buildable now). "
      "**A-17 stays OPEN as the parent** so the thing Greg asked for twice keeps its own line; the "
      "four children carry the work. The operational rule the report is emphatic about: the public "
      "ISO products CANNOT identify which nuclear unit is scheduled out, so never infer a "
      "unit-level calendar from aggregate outage totals.")
if "SPLIT AT S115" not in a17.get("why",""):
    a17["why"] = a17["why"] + note
    a17["children"] = ["A-17A","A-17B","A-17C","A-17D"]
    print("A-17 re-scoped")
json.dump(d,open(P,"w",encoding="utf-8"),indent=1,ensure_ascii=False)

# ---- the audits ----
P2="store/briefing_audits.json"
b=json.load(open(P2,encoding="utf-8"),object_pairs_hook=collections.OrderedDict)
A=b["audited"]

def rec(name, n, result, items):
    A[name]=collections.OrderedDict([("session","S115"),("n_recommendations",n),
                                     ("result",result),("items",items),("verified_on","S115")])
    print("audited", name)

rec("G15_MBO_FIXES_FOR_CHATGPT.md", 10,
    "AUDITED ITEM BY ITEM at S115 close. SEVEN of ten are SETTLED and verifiable as such: item 1 "
    "(NG.n.0 is the wrong pre-roll leg for a roll-straddling group) was acted on at S104 - the year "
    "pull went per-contract-leg, 312 files on S3 - and S115 added a warning when the continuous roll "
    "defaults to `v`; items 3, 4, 5 (MBOMsg casing, action/side enums, source_mode) were integration "
    "snags applied in the same session they were written; items 2, 7, 8 (definition_date sidecar, the "
    "box role's S3 denial, dash-vs-bash under SSM) are ops facts now handled by the definition-schema "
    "pull and by creds.py's explicit-credential path. THREE HAD NO REGISTRY LINE AND NOW DO: item 9 "
    "-> A-73 (live MBO is not authorized on the $179 tier and the collector HOT-LOOPS on the error - "
    "a live-lane blocker carried unregistered for twelve sessions, and the only one of the three that "
    "needs Greg rather than a build); item 10 -> A-75 (continuous_rt.py renders a roll-straddling "
    "group on the post-roll leg for the whole block); item 6 -> A-76 (the odcore import footgun). The "
    "brain's doctrine entry that used to defer to this file was reframed as dated provenance at S115 "
    "under A-58, so nothing served now points a specialist at it.",
    ["A-73","A-75","A-76"])

rec("CHATGPT_BRIEF_S112.md", 6,
    "AUDITED at S115 close. This is an OUTBOUND task packet, not a delivered hand-off: its six "
    "numbered sections are TASKS WE ASSIGNED, and its eight house rules are our own standing rules "
    "restated for an outside reader (name the benchmark, falsification first, per cell never pooled, "
    "three evidence states, instance beside the claim, nothing local, no emojis, measurement vs "
    "vendor marketing). It therefore carries no recommendations of its own to register - the "
    "recommendations are in the REPLY, CHATGPT_S112_SIX_WORKSTREAMS.md, which is audited separately "
    "and is where the registry lines come from. Recorded explicitly rather than left pending, because "
    "'this document has nothing to register' is a disposition and 'nobody has looked' is not.",
    [])

rec("CHATGPT_S112_SIX_WORKSTREAMS.md", 6,
    "AUDITED TASK BY TASK at S115 close against the registry. FIVE of six were already covered: Task "
    "2 (ECMWF ENS + GEFS member retrieval) -> G-5, and it is DONE - the S114 renewables forcing is a "
    "31-member GEFS density, blind-wall audited 10 of 10 days; Task 3 (ISO forward load/wind/solar -> "
    "net load) -> G-4, with A-29 as the free already-paid proxy; Task 4 (the summer degree-day "
    "replacement - a heating-weighted index mis-specifies the summer channel) -> A-19 and A-21; Task "
    "5 (the 500 hPa weather-regime label as a low-dimensional RETRIEVAL key, explicitly not a price "
    "predictor) -> A-5 and G-28; Task 6 (LNG feedgas EBB adapters with explicit health states) -> "
    "G-7. **TASK 1 MAPPED ONTO NOTHING** - searching `Lee-Ready|order-flow direction nowcast` "
    "returned 0 of 181 items, with A-24e (integrity gate) and A-6 (dipole exhaustion) as the nearest "
    "and both a different question. Registered as A-72, carrying the report's honest split: the "
    "RESULT exists (monotone 0.68/0.84/0.94/0.93 by strength, 34 of 34 on three unseen days) while "
    "the original AUDIT PACKAGE does not, and it is a running-leg NOWCAST, never a from-flat "
    "forecast.",
    ["A-72"])

rec("CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md", 4,
    "AUDITED at S115 close. The report's four numbered conclusions became its own section-8 build "
    "decision, and that decision is the audit: **A-17 must not be closed as 'forward nuclear unit "
    "schedule solved'**, because it was one registry line over four different data realities. Split "
    "as the report instructs - A-17A public aggregate forward outage capacity (ERCOT NP3-233-CD, PJM "
    "frcstd_gen_outages, the MISO JSON endpoint, SPP's seven-day fuel-type CSV: buildable now), A-17B "
    "public unit-level refuelling calendar (SEARCHED AND FOUND NOTHING - no free public nationwide "
    "unit-level forward calendar exists; shadow document-watch lane only), A-17C realized unit truth "
    "from the NRC daily status (buildable now), A-17D coal additions/retirements from EIA-860M with a "
    "retained revision history (buildable now, and it is the forward instrument A-31's coal-ramp work "
    "has been missing). A-17 stays OPEN as the parent. The load-bearing negative, kept verbatim in "
    "A-17B: the public ISO products cannot identify WHICH nuclear unit is out, so a unit calendar must "
    "never be inferred from aggregate MW, from typical 18/24-month cycles, or from undated vendor "
    "commentary.",
    ["A-17A","A-17B","A-17C","A-17D"])

rec("TURNAROUND_MEMO_S110.md", 11,
    "AUDITED at S115 close, part by part. This is OUR OWN memo, and most of it was executed in the "
    "session that wrote it - which is why it sat pending: nothing looked wrong. PART 2 builds are all "
    "SHIPPED and verifiable in the tree: the batch record, the andon board + QC checklist "
    "(`plant_status.py`, `agents/QC_CHECKLIST.md`), the decision ledger (`DECISIONS.md`, now 52 "
    "append-only entries), `PLANT_MAP.md`. PART 3's go-plan: G0 CLOSED (signed REST auth proven on "
    "prod and demo), G1 CLOSED (the paper ledger with four risk caps, 11/11 selftest including "
    "negative tests proving each cap fires), G2 CLOSED (the daily paper loop), G4 CLOSED (the andon "
    "covers the loop), G5 STANDING (key rotation deferred to post-walk - unchanged), G6 DECIDED (the "
    "parallel track was blessed and run). **G3 - collector-as-a-service - was NOT built and had NO "
    "registry line**, twelve sessions after being planned at half a session of work; registered as "
    "A-74, and it matters now because paper trading needs a loop that survives a session ending. "
    "PART 1's disposition table and PART 0 are a state-of-the-business snapshot, correctly frozen as "
    "a record.",
    ["A-74"])

rec("NG_FORECASTER_PROBLEM_MEMO_S103.md", 4,
    "AUDITED at S115 close. Like CHATGPT_BRIEF_S112 this is an OUTBOUND diagnostic - its section 8 is "
    "literally 'Specific questions for you (ChatGPT)' - so it carries questions, not recommendations "
    "to register. Its four diagnoses were nonetheless all acted on and can be traced: (1) the "
    "magnitude error FLIPS SIGN block to block - still live and now measured much more sharply as "
    "SYSTEMATIC UNDER-EMISSION, 0.29x of realized on g24 against 0.55x and 0.68x on g22/g23, which is "
    "the dominant open finding of the whole walk; (2) the selector AVERAGES bimodal splits instead of "
    "selecting - merged as the brain play `selector.divergence_resolution` at s102.3; (3) the "
    "order-flow direction nowcast is under-weighted - the same instrument now registered as A-72 by "
    "the S112 workstreams audit, which is the two audits meeting from opposite ends; (4) blind 30-70% "
    "vs refine 90-100% every block - the gap the whole blind/refine architecture (D7) exists to "
    "measure. NOTHING NEW TO REGISTER, and that is the finding.",
    [])

rec("NG_FORECASTER_PROBLEM_MEMO_S103_ADDENDUM_FILES.md", 0,
    "AUDITED at S115 close. It is a FILE LIST - the addendum naming which artifacts accompany the "
    "S103 memo for an outside reader. No recommendations, nothing to register. Recorded as an "
    "explicit zero rather than left pending: a document with nothing in it still needs someone to "
    "have looked, and 'pending' cannot tell those two states apart.",
    [])

rec("GAS_SIGNAL_BRIEFING_S111.md", 13,
    "AUDITED at S115 close, by structure rather than by re-reading 344KB, and the reasoning is stated "
    "so it can be challenged. This is the RAW RESEARCH BODY whose distillation is "
    "GAS_SIGNAL_SYNTHESIS_S111.md - the pair was commissioned and delivered together, the synthesis "
    "IS the briefing's recommendation set, and the synthesis was audited at S112: 12 of its 13 "
    "recommendations had no registry item and became G-16..G-28, the 13th (the VRP denominator) was "
    "already inside G-10. So the briefing's recommendations are registered, through its synthesis, "
    "and G-16..G-28 are all present in the registry today. WHAT THIS AUDIT DOES NOT CLAIM: that every "
    "measurement in the 344KB body was extracted. The body is a corpus to mine, not a list to "
    "discharge, and mining it is a research task rather than a D36 obligation. Recorded that way "
    "deliberately - the alternative was leaving a permanent red line that nobody could ever clear, "
    "which is how a gate gets ignored.",
    ["G-16","G-17","G-18","G-19","G-20","G-21","G-22","G-23","G-24","G-25","G-26","G-27","G-28"])

json.dump(b,open(P2,"w",encoding="utf-8"),indent=1,ensure_ascii=False)
print("audits:", len(A))
