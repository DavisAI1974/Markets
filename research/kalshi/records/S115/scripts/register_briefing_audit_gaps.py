import json, collections
P = "OPEN_ITEMS.json"
d = json.load(open(P, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
items = d["items"]; have = {i["id"] for i in items}

def add(**kw):
    if kw["id"] in have: print("exists", kw["id"]); return
    items.append(collections.OrderedDict(kw)); have.add(kw["id"]); print("added", kw["id"])

add(id="A-72", title="THE ORDER-FLOW DIRECTION NOWCAST HAS NO REGISTRY LINE - the one workstream of six that was never registered",
    source="S115 close, auditing CHATGPT_S112_SIX_WORKSTREAMS.md Task 1 against the registry (D36)",
    first_raised="S115", status="OPEN", size="M", tier="BIGGEST_WIN",
    tier_why="It is the direction half of the live lag play, it is already implemented, and it is the single "
             "highest-agreement result the desk has ever recorded - and no registry line has ever pointed at it, "
             "so nobody has re-run it causally. Five of the six S112 workstreams map onto G-4, G-5 (DONE), G-7, "
             "A-19/A-21 and A-5/G-28. Task 1 maps onto NOTHING.",
    why="MEASURED S115 by searching the registry for the result itself (`Lee-Ready`, `order-flow direction "
        "nowcast`): 0 of 181 items. The nearest neighbours are A-24e (order-flow signal INTEGRITY as an "
        "authority gate - a different question) and A-6 (the dipole EXHAUSTION arm - a different instrument).\n\n"
        "WHAT EXISTS. `dip_imb_level`, the signed buy-minus-sell imbalance, eligible at |imb| >= 0.15. Agreement "
        "rises MONOTONICALLY across strength cells: 0.68 / 0.84 / 0.94 / 0.93, and the desk recorded 34 of 34 "
        "qualifying observations on three unseen days (S92). Known failure: it lags an extreme gap melt-up.\n\n"
        "WHAT DOES NOT EXIST, and the honest half. The ORIGINAL audit package is gone - formula version, "
        "aggregation window, instrument/date list, qualifying-event count, bin boundaries, null-test output. "
        "SEARCHED AND FOUND NOTHING (D24 case 2). The result and the completeness of its audit trail are two "
        "different things, and neither one substitutes for the other.\n\n"
        "IT IS ALSO A NOWCAST, NOT A FORECAST. The target was the side or continuation of a RUNNING LEG - not "
        "direction from a flat pre-session state. Quoting the 94% as if it were a from-flat forecast would be "
        "the S110 'a right day-net carrying a false mechanism' defect in a new place.",
    what="1. Freeze the desk's Lee-Ready implementation as THE canonical candidate, versioned, so there is one "
         "definition to test.\n"
         "2. Re-run it CAUSALLY on the real tape (D3: the future must be absent, not discouraged) across the "
         "walked corpus, per event, never pooled (D4/D37).\n"
         "3. Score it against NAMED benchmarks (A-1): persistence and same-leg slope continuation at minimum. "
         "No agreement number without one.\n"
         "4. Only then consider authority. It is a nowcast; scope any claim to running legs.",
    falsifier="If per-event causal replay does not reproduce a monotone agreement gradient across strength cells, "
              "the 0.68/0.84/0.94/0.93 ladder was a small-sample artifact of ~12 warm-season days and the play "
              "dies. If it reproduces but does not beat persistence, it is a description of the tape rather than "
              "an edge - keep the measurement, drop the claim (D37).")

add(id="A-73", title="LIVE MBO IS NOT AUTHORIZED ON OUR DATABENTO TIER - the live feed lane Greg calls critical cannot start on what we pay for",
    source="S115 close, auditing G15_MBO_FIXES_FOR_CHATGPT.md item 9 against the registry (D36); Greg, S115: 'We need the live feeds for the agent to read and the coach to call plays. it's critical for live trading'",
    first_raised="S103 (recorded in that memo, never registered - twelve sessions)", status="OPEN", size="S", tier="ESSENTIAL",
    tier_why="It is a PROCUREMENT DECISION that only Greg can make, it gates the live lane he has named critical, "
             "and it has sat unregistered since S103. The failure mode is the worst kind: the live collector does "
             "not fail loudly, it HOT-LOOPS on ErrorMsg, so a live bring-up looks like a hang rather than a "
             "billing answer.",
    why="MEASURED at S103 and never entered the registry: the $179/mo Databento LIVE Standard plan returns 'Not "
        "authorized for mbo schema'. `mbp-10` is in the same entitlement class. The live collector LEADS with an "
        "`mbo` subscribe. The tier that carries it is roughly $1,500/mo.\n\n"
        "This is not the same question as the historical pull, which works fine - the year of NG tape was bought "
        "per-job under the subscription. It is specifically LIVE streaming depth.",
    what="Two honest routes, and the choice is Greg's, not a build:\n"
         "(a) BUY the entitlement. Then the live loop matches the historical engine exactly and nothing in the "
         "forecaster changes - which is D7's whole point, one engine.\n"
         "(b) DESIGN THE LIVE LANE ONTO WHAT WE ARE ENTITLED TO (trades + mbp-1/L1) and MEASURE what is lost. "
         "The blind's open-time flow channel is `tape_conditions`, and S108 hole #8 showed how much damage a "
         "silently wrong flow channel does - so route (b) must be measured, not assumed adequate.\n"
         "Either way, first fix the collector to FAIL LOUDLY on an entitlement error instead of hot-looping.",
    falsifier="Route (b) is settled by measurement, not argument: replay a walked block twice, once with full MBO "
              "and once with only the entitled schemas, and compare the served flow block field by field. If the "
              "entitled-only build reproduces the flow fields the plays actually read, (a) is an expense we do "
              "not need. If it does not, the gap is the price.")

add(id="A-74", title="THE LIVE LOOP HAS NEVER RUN AS A SERVICE - collector-as-a-service was G3 of the S110 go-plan and has no registry line",
    source="S115 close, auditing TURNAROUND_MEMO_S110.md PART 3 against the registry (D36)",
    first_raised="S101-02 (designed), S110 (planned as G3), never registered", status="OPEN", size="M", tier="ESSENTIAL",
    tier_why="Paper trading is the next milestone and it needs a loop that survives a session ending. Everything "
             "else in the S110 go-plan got built - G0 account closed, G1 paper ledger with four risk caps, G2 "
             "daily loop, G4 andon - and this one line, the one that makes them RUN WITHOUT A HUMAN, was never "
             "tracked.",
    why="MEASURED S115: searching the registry for `live orchestrat|systemd|collector-as-a-service|watchdog` "
        "returns 0 of 181. `ng_live_collector` and `ng_live_watchdog` were designed at S101-02 and, in the memo's "
        "own words, 'never yet run as a service'. The S110 memo listed it as G3, half a session of work, with "
        "health.json feeding the andon board.\n\n"
        "Note the shape: this is D36 exactly - a memo's recommendation living in prose that nothing counts. It is "
        "the third instance of that family found by auditing briefings (12 of 13 S111 suggestions, then the A-24 "
        "hand-off, now this).",
    what="systemd units + timers for the collector and watchdog on the box, `health.json` written every cycle and "
         "read by `plant_status.py` as a heartbeat row. Blocked in part by A-73: decide the entitlement before "
         "building the subscribe path, or the service is built against a schema we cannot stream.",
    falsifier="It is done when the andon shows a live heartbeat that goes stale on its own if the box stops - a "
              "heartbeat that only exists while someone is watching is not a service. Kill the process and the "
              "row must go red without anyone touching it.")

add(id="A-75", title="A ROLL-STRADDLING GROUP RENDERS ON THE WRONG LEG - continuous_rt.py draws the NG.n.0 tape, which is the post-roll contract for the whole block",
    source="S115 close, auditing G15_MBO_FIXES_FOR_CHATGPT.md item 10 against the registry (D36)",
    first_raised="S103, never registered", status="OPEN", size="S", tier="REST",
    tier_why="Real and reproducible, but it bites only on groups that straddle a Kalshi-underlying roll, and the "
             "walk's staged blocks are done. It matters again the moment a head block straddles one.",
    why="MEASURED at S103 on G15: `continuous_rt.py` reads the S3 NG.n.0 tape for the actual curve. For G15 that "
        "is NGK26/May across the WHOLE block, so the pre-roll days (0313-0319) were drawn about 0.037 below the "
        "NGJ26 basis the group was actually forecast on. The generic render is correct for a non-straddling "
        "group and quietly wrong for a straddling one - which is the dangerous half, because the picture looks "
        "fine.\n\nThe hand-rolled `run_g15_rt_s102.py` two-leg approach (NGJ26 pre-roll + NGK26 post-roll, seam "
        "marked at 0320) is the correct shape; it was never generalised.",
    what="Give `continuous_rt.py` a leg map: read the group's own basis, draw each day on the leg that day was "
         "forecast on, and MARK the seam rather than bridging it (the S105 `break_gaps()` rule applied to a "
         "contract seam instead of a weekend).",
    falsifier="Re-render G15 with the leg map and the pre-roll days must move by the measured basis (~0.037) onto "
              "NGJ26 while the post-roll days do not move at all. If post-roll days move, the map is wrong.")

add(id="A-76", title="ng_live_operator imports odcore by repo-root path with no sys.path shim - a footgun that stands the operator down",
    source="S115 close, auditing G15_MBO_FIXES_FOR_CHATGPT.md item 6 against the registry (D36)",
    first_raised="S103, never registered", status="OPEN", size="XS", tier="REST",
    tier_why="Trivial, but it is on the live path and it fails as an ImportError at bring-up time, which is the "
             "worst moment to be debugging a path.",
    why="`ng_live_operator.py` does `from odcore.info_dipole import ...`, which resolves only from the repository "
        "root. Running from `research/kalshi` - the working directory the SOP and every gate command uses - "
        "requires PYTHONPATH to be set by hand. Verified S115: the file still has no `sys.path` insert.",
    what="Add the same KALSHI_DIR-style `sys.path` insert the tests already use. One line.",
    falsifier="`cd research/kalshi && python -c 'import ng_live_operator'` must succeed with no PYTHONPATH set.")

NUC = "S115 close, auditing CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md section 8 - the report's own final build decision"
for sid, title, tier, size, why, what, fals in [
 ("A-17A", "Public AGGREGATE forward outage calendar - buildable now from ERCOT, PJM, MISO, SPP", "BIGGEST_WIN", "M",
  "The delivered report FOUND four ingestible public products: ERCOT NP3-233-CD, PJM `frcstd_gen_outages`, the "
  "MISO public JSON endpoint, and SPP's seven-day fuel-type outage CSV. These give forward outage CAPACITY, "
  "aggregate, by fuel type where published.",
  "Build the four adapters. ERCOT fails closed without its token/subscription key; PJM's source metadata must "
  "preserve the internal-use and redistribution restrictions; MISO records that it is MISO-wide daily aggregate; "
  "SPP records fuel type and NEVER maps aggregate nuclear MW to a unit.",
  "Each adapter must reproduce a published figure for a past date from the archive path, not the live endpoint."),
 ("A-17B", "Public UNIT-LEVEL nuclear refuelling calendar - a MEASURED public-data gap, not a build", "REST", "L",
  "The report's executive determination, verbatim in substance: there is NO single free, public, nationwide, "
  "unit-level forward nuclear refuelling calendar ingestible as a production feed. CAISO publishes a "
  "current-trade-date unit snapshot, not a forward schedule; the non-ISO Southeast has no standardized public "
  "equivalent. This is D24 case 2 - SEARCHED AND FOUND NOTHING - and it is recorded as such rather than left "
  "looking like work nobody got to.",
  "Keep a document-watch SHADOW lane only (TVA, Georgia PSC, South Carolina PSC, Florida PSC, Duke, Southern "
  "Nuclear, Dominion), irregular and manual. **Do NOT infer unit dates from aggregate ISO MW totals, from "
  "typical 18/24-month cycles, or from undated vendor commentary** - the report names all three as "
  "'do not build as production authority'.",
  "This item closes only against a PRIMARY public document giving unit dates. A plausible-looking calendar with "
  "no primary source is the failure, not the fix."),
 ("A-17C", "REALIZED nuclear outage truth from the NRC daily power reactor status - buildable now", "BIGGEST_WIN", "S",
  "The NRC publishes daily unit power status with the literal header `ReportDt|Unit|Power`, plus a detailed page "
  "carrying `Down` and `Reason or Comment`. That is realized outage truth at UNIT level - the thing the ISO "
  "aggregates cannot give.",
  "Ingest both, discovering years from the NRC archive links rather than hardcoding filenames, preserving "
  "publication AND retrieval timestamps on every record.",
  "The parser must read the literal header rather than positional columns; a header change must fail the parse, "
  "not silently shift the fields."),
 ("A-17D", "Coal additions and retirements calendar from EIA-860M - buildable now, and it feeds the coal-ramp work", "BIGGEST_WIN", "S",
  "EIA-860M is a monthly generator-level calendar of planned additions and retirements. It is the forward "
  "instrument the S113 coal work (A-31, coal as a startup-constrained ramp) has been reasoning about without.",
  "Ingest monthly and MAINTAIN A REVISION HISTORY - store every vintage, never overwrite a prior planned date. "
  "Planned dates move, and the movement is the signal.",
  "Pull two adjacent vintages and confirm at least one planned date differs and both are retained. If the store "
  "shows only the current plan, the revision history is not being kept.")]:
    add(id=sid, title=title, source=NUC, first_raised="S113 (report), S115 (registered)", status="OPEN",
        size=size, tier=tier,
        tier_why="A-17 was one item covering four different data realities with four different answers. The "
                 "delivered report's final line is explicit: A-17 should NOT be closed as 'forward nuclear unit "
                 "schedule solved'. Splitting it is the report's own recommendation and it is what makes the "
                 "honest 'no' in A-17B survivable as a record.",
        why=why, what=what, falsifier=fals)

json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("registry now %d items" % len(items))
