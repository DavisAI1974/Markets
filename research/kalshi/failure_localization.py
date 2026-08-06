"""failure_localization.py - WHERE does the repair belong? (S114)

SOURCE: "Model or Harness? An Interaction-Centric Taxonomy for Localizing Agent Failures", Raj,
Gupta, Mahmoud, Dumitru, Yi, Sabharwal, He (Scale AI), arXiv:2607.28802v1, 30 Jul 2026. Component
definitions, the 41 modes, the fault-side notation, the root-cause tracing rule and the judge
protocol below are FROM THE PAPER, not reconstructed.

THE PROBLEM IT SOLVES, in the paper's words: "the same visible failure may call for model
post-training, harness engineering, environment redesign, or benchmark repair depending on where it
originated." Outcome-level labels do not say which.

WE HAD ALREADY WRITTEN THE PROBLEM DOWN AND NEVER SYSTEMATISED IT. S107, verbatim: "Keep
ATTRIBUTION straight in post-mortems so a merge does not bank a data fix as evidence for a play."
The cost is measured: S108 RETRACTED a play whose day-net was right and whose mechanism was false,
because a non-model result had been banked as model-side evidence. A wrong repair is worse than
none - it also manufactures confidence.

WHAT THE DEFECT REGISTRY HAD, AND WHAT IT LACKED. `defect_timeline.DEFECTS` carries a repair CLASS
(RETRO_REPAIRED / FORWARD_ONLY / OPEN) - that is repair TIMING. It says nothing about repair
LOCATION. Both are needed and they are independent.

-------------------------------------------------------------------------------------------------
THREE CORRECTIONS THE FULL PAPER FORCED ON MY FIRST ATTEMPT (recorded, not tidied away - the first
version was built from the ABSTRACT ONLY, which does not enumerate the modes, and it was wrong in
ways that changed verdicts):

  1. THERE IS NO "HARNESS" COMPONENT. I invented one. "Harness" is a FAMILY of edges
     (model-context, model-memory, model-tool, model-model), not an endpoint. Calling something a
     harness fault said nothing about which interface to repair.
  2. EVERY EDGE HAS THE MODEL ON ONE SIDE. All 41 modes are model-X. I had written edges like
     "tools <-> environment" and "harness <-> environment", which do not exist in the schema. The
     consequence is large for us and is stated honestly below under SCOPE.
  3. CONTEXT AND MEMORY ARE DIFFERENT COMPONENTS AND I HAD ONLY MEMORY. Context is what the model
     can see in THIS interaction; memory is what outlives it. For this plant that is exactly the
     causal slice / served state (context) versus the brain, ledgers and handoffs (memory) - and
     several of our failures live on the context edge, which I could not previously express.

  Also: the paper's actor is the OWNER ("gives the agent its task AND defines what counts as
  success"), not a generic "user"; the GRADER is explicitly "usually not visible to the agent"; and
  the ENVIRONMENT splits into LOCAL and EXTERNAL.
-------------------------------------------------------------------------------------------------

SCOPE - CORRECTED S114 ON GREG'S QUESTION ("this paper is supposed to cover agent behavior right?").
It does, and my first pass excluded nine defect groups as "pipeline bugs with no model in the loop".
That was WRONG: every one of them ended up in a SERVED STATE that a specialist read, so the model
interacted with each and the interaction failed. Under the paper's own root-cause rule the label
goes on the interaction where the earliest unrecovered failure occurred, and what failed there is
the CONTEXT. That the repair happens to live in a builder is what "fault: context" TELLS you - it
is not grounds for exclusion. Nothing is out of scope now, and the correction INVERTS the headline:
context 16, model 8, owner 2, tool 2.

OTHER USES THIS SCHEMA SUPPORTS (Greg, S114: "I'm sure we can modify it for other things too").
The unit of analysis is an INTERACTION and a RESPONSIBLE END, which is not specific to failures.
Registered rather than built, so the idea is not lost:
  - THE POST-MORTEM STATION. Classify every finding BEFORE it becomes brain evidence. This is the
    one that pays first: S108 retracted a play whose day-net was right and whose mechanism was
    false, because a non-model result was banked as model-side evidence. Edge + fault side at the
    point of merge would have refused it.
  - THE STATE AUDITOR (D17) already hunts silently-wrong inputs; its findings ARE model-context
    faults and could be emitted pre-labelled, which makes the fix-phase adjudication (STEP 2) a
    routing decision instead of a judgment call.
  - SUCCESSES, NOT ONLY FAILURES. The same edge/side labelling applied to the winners census says
    WHERE a win came from - C-0714's k3 chain is a model-side success, while a day carried by a
    clean served block is a context-side one. We currently credit both to the forecaster.
  - THE DECLINE AUDIT (384 declines, 115 DATA_ABSENT). A decline for missing data is a
    model-context event, not a play weakness; the tiers are already in the data and unlabelled.
  - THE PAPER DOCK. When the venue enters, THIRD PARTY stops being empty and the edges it opens
    (Indirect Prompt Injection, Contextual Sycophancy) are the ones we have no instrument for.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---- the paper's components, verbatim definitions, mapped to this plant --------------------
COMPONENTS = {
    "model":       ("The policy that processes observations and produces outputs or actions.",
                    "a specialist (A-E), the state auditor, the coordinator when it reasons"),
    "owner":       ("The human or upstream system that gives the agent its task and defines what "
                    "counts as success.",
                    "Greg; and the RUN DIRECTIVE / spawn prompt, which is the upstream system"),
    "grader":      ("The mechanism used to evaluate whether the agent completed the task "
                    "successfully; it is usually not visible to the agent.",
                    "blind_score_nonpooled, the actuals, the 20:00-to-20:00 scoring clock (D26), "
                    "the benchmarks - and note the paper's clause: NOT VISIBLE TO THE AGENT. Ours "
                    "is not visible either, by design (D2)"),
    "third_party": ("An actor encountered during execution that does not act on behalf of the owner.",
                    "NONE TODAY - we have no external actors in a run. Stated so the absence is "
                    "declared rather than assumed; it changes when the dock trades against a venue"),
    "context":     ("The information available to the model during the current interaction, "
                    "including instructions, conversation history, observations, and summaries.",
                    "the per-day CAUSAL SLICE, the served decision state, the emitted spawn prompt, "
                    "the calendar block, a consumed handoff or bridge"),
    "memory":      ("A persistent store that outlives the active context, within or across sessions.",
                    "knowledge/ng_brain.json, the ledgers, DECISIONS.md, OPEN_ITEMS.json, the "
                    "committed posteriors"),
    "tool":        ("The bidirectional interface through which the model exchanges requests, "
                    "messages, actions, observations, and responses.",
                    "the scripts a specialist or the line invokes"),
    "local_env":   ("The local execution setting.", "the container, data/, the git tree"),
    "external_env":("Remote services and APIs.", "S3, Databento, EIA, the exchange feeds"),
}

# ---- the 41 modes, by family and edge (paper Table 1 / Section 3) --------------------------
MODES = {
 "user": {
   "model-owner": [("Over-initiative","model"),("Under-initiative","model"),("Satisficing","model"),
                   ("Instruction-Following Failure","model"),("Reasoning Failure","model"),
                   ("Unauthorized Irreversible Action","model"),("Sycophancy","model"),
                   ("Domain Knowledge Deficit","model"),("Value Misalignment","model"),
                   ("Instruction-Grader Mismatch","owner")],
   "model-grader": [("Specification Gaming","model"),("Evaluation Awareness","model")],
   "model-third_party": [("Indirect Prompt Injection","model"),("Contextual Sycophancy","model")],
 },
 "harness": {
   "model-context": [("State Tracking Failure","model"),("Goal Drift","model"),
                     ("Context Rationale Erosion","harness or model")],
   "model-memory": [("Missed Write","model"),("State Staleness","model"),("Overgeneralization","model"),
                    ("Memory Rationale Erosion","model"),("Pollution","model"),("Redundancy","model"),
                    ("Missed Read","model"),("Memory Following Failure","model")],
   "model-tool": [("Incorrect Tool Selection","model"),("Tool Hallucination","model"),
                  ("Tool Feedback Neglect","model"),("Tool Recovery Failure","model"),
                  ("Malformed Arguments","model"),("Suboptimal Arguments","model"),
                  ("Mistranslation","tool")],
   "model-model_peer": [("Delegation Failure","model"),("Communication Failure","model")],
   "model-model_subagent": [("Delegation Failure","model"),("Communication Failure","model")],
 },
 "environment": {
   "model-external_env": [("Service Failure","environment"),("Stale State Delivery","environment"),
                          ("Recovery Failure","model")],
   "model-local_env": [("Observation Failure","model"),("Recovery Failure","environment")],
 },
}

ROOT_CAUSE_RULE = (
 "Paper, Section 4, verbatim: 'Starting from the observed system-level failure, the preceding events "
 "are traced backward to identify the EARLIEST failure from which execution does not recover. Later "
 "errors are treated as CONSEQUENCES, and the taxonomy label is assigned to the interaction in which "
 "the earliest unrecovered failure occurred.' THIS IS THE PART WE MOST NEED: our post-mortems have "
 "habitually labelled the LAST visible error. The S104 cascade is the instance - 10 of 14 bad Mondays "
 "root to a mis-read Friday, so the Monday label was a consequence every time.")

JUDGE_PROTOCOL = (
 "Three sequential turns: (1) EVIDENCE RECONSTRUCTION - retrieve and organise the source material "
 "chronologically and NEUTRALLY; (2) FAILURE CLASSIFICATION - against frozen taxonomy definitions, "
 "identify the earliest unrecovered failure and assign edge + fault side + mode; (3) REFLECTION AND "
 "DISAMBIGUATION - check the proposed label against predefined disambiguation rules, confirm or "
 "revise. Validated across four frontier models against human labels on 40 worked examples; best "
 "category-level (edge + fault side) agreement Cohen's kappa 0.76. NOTE THE SHAPE: neutral "
 "reconstruction BEFORE classification is the same pre-influence ordering the S114 decision-order "
 "proposal puts at step 3, arrived at independently in a different literature.")

# ---- OUR failures, classified. Hand-assigned per the paper's own method (its reproducibility
# check is independent JUDGES reaching kappa 0.76, i.e. a checkable judgment, never a parse).
# Regex-guessing an edge from text is the fuzzy-matching error that produced holes #8 and #9.
CLASSIFIED = {
 # ---- model-context: what the specialist was shown, and what it did with it ----
 "0629 wind read": ("model-context", "model", "Missed Read",
   "wind_mwh was SERVED in every slice and read by nobody; gw_cdd rose exactly as forecast and burn "
   "FELL 4.2 Bcf/d on a 62% wind rise. The context carried it; the model did not consult it. "
   "Model-side - and this is the classification that says the repair is doctrine, not a feed."),
 "0601 wind read": ("model-context", "model", "Missed Read",
   "0629's twin, found S114: served wind +1,071k MWh, gas -1,271k, blind +350 into a -990 day."),
 "hole #11 forward reads": ("model-context", "context", "Stale State Delivery",
   "The state served a day's tape under the NEXT day's key, so all three specialists could read past "
   "their own decision point. ALL THREE DECLARED IT - the models behaved correctly and the context "
   "was malformed. Repair was build_causal_slices, i.e. the context builder. Not a model fault."),
 "h-frozen_countdowns": ("model-context", "context", "Stale State Delivery",
   "The one-shot mask froze distance-from-today fields, so every staleness reading inside a masked "
   "block counted from the wrong day."),
 "h-squeeze_live / _calendar_twins": ("model-context", "context", "Stale State Delivery",
   "A field named _live holding a constant. Twice - the second time inside the fields added to cure "
   "the first."),
 # ---- model-owner: the directive, and what counts as success ----
 "NC-1 false calendar premise": ("model-owner", "owner", "Instruction-Following Failure (owner-side premise)",
   "The run directive asserted 'first post-roll session'; flow_calendar said otherwise. C-0715 "
   "checked and corrected the record rather than reasoning on it. THE MODEL WAS RIGHT AND THE "
   "DIRECTIVE WAS WRONG - owner-side, and no amount of specialist tuning would have fixed it."),
 "B-0713 override": ("model-owner", "model", "Sycophancy",
   "Its own instrument pointed down (D-1 aggregate -1,225 SELL) and it went up on a handed-down "
   "verdict table - 'not by my override'. Deferring to an upstream assertion against its own "
   "evidence is the paper's Sycophancy, model-side. The block's worst wrong-direction day."),
 "0709 scenario-weighting": ("model-owner", "model", "Satisficing",
   "Weighted loose/in-band/tight and emitted -250 against a -2,050 actual: a defensible middle "
   "instead of a derived number."),
 # ---- model-grader: the mismatch class ----
 "D26 scoring clock": ("model-owner", "owner", "Instruction-Grader Mismatch",
   "The specialists were told 17:00-to-17:00; the grader scores 20:00-to-20:00. THE PAPER PUTS THIS "
   "MODE ON THE OWNER SIDE, which is the right verdict: the agent followed its instruction and the "
   "instruction did not match what success was measured as. Measured: 0 on 8/8 Fridays, and on 0715 "
   "it was 230 of that day's 360 error."),
 # ---- model-memory ----
 "burn-gate tally 0-of-3": ("model-memory", "model", "Overgeneralization",
   "A tally assembled from independent per-day slices was written as a general fact; the truth was "
   "1-of-4. Per-day causal isolation (D3) means no peer can correct it mid-run, so the remedy is "
   "coordinator recomputation, already merged S110."),
 "S108 retracted play": ("model-memory", "model", "Pollution",
   "A right day-net carried a FALSE MECHANISM into the brain, and the mechanism is what gets "
   "extrapolated. Persisting a wrong reason into the store that outlives the session is exactly "
   "Pollution."),
 # ---- process failures: the line acting on itself ----
 "NC-4 blind coordinator": ("model-tool", "tool", "Mistranslation",
   "The coordinator asked for 'the specialist files' and the tool returned REFINE posteriors under "
   "the canonical blind names, which it then wrote over the immutable blind record (4/10 sum|err| "
   "5,965 -> 10/10 500). The interface's answer did not mean what the caller meant. Tool-side."),
 "h-tape_offinstrument": ("model-tool", "tool", "Mistranslation",
   "The harness asked for 'whichever store has more trades'; after a roll that is the DEFERRED "
   "contract. The tool answered its question honestly and the answer was the wrong instrument - "
   "signed flow SIGN-FLIPPED on the blind's only never-masked flow channel."),
 "NC-3 untested guard": ("model-tool", "model", "Tool Feedback Neglect",
   "I reported a guard 'negative-tested both directions' when its firing branch had never executed. "
   "The tool never produced the output that would have shown it; I did not require it to."),
 "NC-2 scratchpad harness": ("model-memory", "model", "Missed Write",
   "The next session was pointed at a harness that did not persist - the durable write never "
   "happened."),
}

# CORRECTED S114, ON GREG'S QUESTION "this paper is supposed to cover agent behavior right?".
# It does - and that is precisely why my first OUT_OF_SCOPE list was WRONG. I had excluded nine
# defect groups as "pipeline bugs with no model in the loop", importing a software-bug-vs-agent-
# failure distinction THE PAPER DOES NOT MAKE. Every one of those defects ended up in a SERVED
# STATE that a specialist read: a b_share computed on the wrong denominator, an empty weather block,
# a vol_regime dead since G16. The model interacted with each of them and the interaction failed.
# Under the paper's own root-cause rule the label goes on the interaction where the earliest
# unrecovered failure occurred - and the CONTEXT is what failed there. That the repair happens to
# live in a builder is what "fault: context" TELLS you; it is not grounds for exclusion.
#
# The correction matters because it inverts the headline: reclassified, the plant's failures are
# overwhelmingly CONTEXT-side, not model-side.
CONTEXT_SIDE_RECLASSIFIED = {
 "h-bshare_denom": "every *_b_share divided by TOTAL volume while the tape carries a third side value",
 "h-session_bshare_encoding": "served share a flat 0.0 on 20 readings across two groups",
 "h-big_print_series": "the count-based value served under the size-weighted name",
 "h-vol_regime": "the magnitude-conditioning block dead since G16 on a hard-coded SPAN_END",
 "h-weather_path": "weather empty on EVERY staged group",
 "h-lne_strike_scale": "LNE strikes served at 1/10 of $/MMBtu",
 "h-volregime_window_undeclared": "two windows served as one quantity with no basis field",
 "h-nws_tail": "the last day of a pull served wrong while reporting coverage 1.0",
 "h-storage": "storage / stor_surprise served empty",
 "h-l1book": "signed-flow + l1_book served empty",
 "h-options_surface": "options_surface served empty",
 "h-mbo_book_absent": "book layer stood down group-wide",
 "a10-fingerprint_book": "eleven book features hard-constant since 2026-01-18",
}
for _k, _v in CONTEXT_SIDE_RECLASSIFIED.items():
    CLASSIFIED[_k] = ("model-context", "context", "Stale State Delivery", _v +
        " - served to a specialist and read as if sound. Fault: CONTEXT; the repair lives in the "
        "builder, which is what the fault side names.")

OUT_OF_SCOPE = {
 "none": "Nothing is excluded. The earlier exclusion list was an error - see the note above.",
}

UNRESOLVED = {
 "A-40 the emission ceiling": {
  "measured": "Largest |guess| in 60 modern days is 950 (one over-call); the SECOND largest is 550, "
              "so 59 of 60 emitted <= 550 while 30 of 60 days delivered |actual| > 550, to 2100. "
              "Capture degrades with move size: 7% on 0528, 12% on 0709.",
  "candidate_A": "model-owner - fault MODEL - Satisficing. The specialist settles for a defensible "
                 "middle instead of deriving. Repair: doctrine, the decision order, play text.",
  "candidate_B": "model-owner - fault OWNER - Instruction-Grader Mismatch. The output contract "
                 "REQUIRES a numeric magnitude and the coordinator hard-fails without one, so a "
                 "specialist with no read must invent one; NO CALL is unemittable (C-0715 wrote it "
                 "and could not). Repair: contract + coordinator (A-2).",
  "why_it_matters": "Same edge, opposite fault sides, disjoint repairs - one of them is wasted "
                    "effort. This is the paper's thesis landing on our most expensive open defect.",
  "how_to_separate": "By experiment, not argument. Step 3 already exists as "
                     "magnitude.emission_ceiling_check (s105.3). Serve the decision order WITHOUT "
                     "changing the contract and re-measure: if emissions break 550 where drivers "
                     "support it, the fault was model-side and doctrine fixed it; if they do not, "
                     "the contract binds and the fault is owner-side.",
 },
}


def report():
    print("=" * 98)
    print("FAILURE LOCALIZATION - interaction edge + fault side (arXiv:2607.28802)")
    print("=" * 98)
    print(f"\nROOT-CAUSE RULE\n  {ROOT_CAUSE_RULE}\n")
    n = sum(len(v) for fam in MODES.values() for v in fam.values())
    print(f"taxonomy loaded: {n} modes across "
          f"{sum(len(f) for f in MODES.values())} edges in {len(MODES)} families\n")
    print(f"{'our failure':32} {'edge':22} {'fault':8} mode")
    print("-" * 98)
    by = {}
    for k, (edge, side, mode, _why) in sorted(CLASSIFIED.items(), key=lambda x: (x[1][0], x[1][1])):
        print(f"{k:32} {edge:22} {side:8} {mode}")
        by.setdefault(side, []).append(k)
    print("\nFAULT SIDE - where the repair belongs (members named):")
    for side in sorted(by, key=lambda s: -len(by[s])):
        print(f"  {side:9} {len(by[side]):2}  {', '.join(sorted(by[side]))}")
    print(f"\nOUT OF SCOPE ({len(OUT_OF_SCOPE)} defect groups) - pipeline bugs with no model in the")
    print("loop. Forcing them onto a model-X edge would be the mislabelling this tool exists to stop.")
    for k, v in OUT_OF_SCOPE.items():
        print(f"  {k:52} {v}")
    for name, u in UNRESOLVED.items():
        print(f"\nUNRESOLVED - {name}")
        for f in ("measured", "candidate_A", "candidate_B", "why_it_matters", "how_to_separate"):
            print(f"  {f:15}: {u[f]}")
    print(f"\nJUDGE PROTOCOL\n  {JUDGE_PROTOCOL}")
    return 0


if __name__ == "__main__":
    sys.exit(report())
