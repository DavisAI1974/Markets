#!/usr/bin/env python3
"""
brain_schema.py - give the brain a schema: typed, queryable, LOSSLESS. (S111, Greg's call)

WHY. knowledge/ng_brain.json grew one merge at a time and every session invented its own field
names. Measured at s105.0: 82 plays carrying ~90 DISTINCT field names, most appearing exactly once
(`s101_6_0223_fade_vs_ratify`, `s102_1_unowned_premium_full_fade`, `mis_scaled_not_refuted_tails_
only_s110`). Even the core fields fragmented - `forward_evidence` 77 times, plus `forward_evidence_
g20`, `forward_evidence_g21_leg_vs_day`, `g15_forward_evidence` and `g16_forward_evidence` as four
separate keys holding the same kind of thing. Consequence: NOTHING can be asked of the brain as a
whole. Every audit this session had to be a bespoke regex.

The S110 turnaround memo flagged half of this ("Brain status taxonomy drift (FIX, S): 68 plays carry
ten different free-text statuses including one 40-word sentence"), it never became a DECISIONS line,
and nothing enforced it - so the count is now TWELVE statuses across 82 plays, including that exact
40-word sentence. This file is the enforcement that was missing.

THE GOVERNING RULE, and it is the whole point:
    EVERY FIELD MUST BE QUERYABLE ACROSS ALL PLAYS. A session that needs to record something new
    puts it in a TYPED SLOT with a session tag inside it - never in a new field name.

LOSSLESS BY CONSTRUCTION. Nothing is deleted, ever - the desk's standing policy (Greg, S111) is that
a refutation is SCOPED to the cell and instrument it was measured on, never converted into "dead",
and that applies to prose as much as to plays. Every ad-hoc key is preserved verbatim under
`legacy_notes`. `migrate --write` refuses to run unless the round-trip check proves every leaf value
in the old brain is still reachable in the new one.

WHAT IS DELIBERATELY *NOT* AUTOMATED. `conditions[]` is populated ONLY from a hand-curated map.
Parsing prose triggers into structured conditions by regex is exactly the fuzzy-matching error this
program keeps being bitten by (hole #8 recomputed coherently off the wrong contract; hole #9 read a
plausible 0.0). Unmapped plays get `conditions: []` and `conditions_state: "unparsed"` - an explicit
open task, never a guess.

USAGE
    python brain_schema.py validate                 # check the CURRENT brain against the schema
    python brain_schema.py migrate                  # DRY RUN - prints the diff, writes nothing
    python brain_schema.py migrate --write          # backup, migrate, verify round-trip
    python brain_schema.py report                   # what the schema can now answer
"""

import argparse
import copy
import json
import os
import shutil
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")

SCHEMA_VERSION = "brain-schema-1"

# --------------------------------------------------------------------------------------
# THE SCHEMA
# --------------------------------------------------------------------------------------
STATUS_ENUM = ["HYPOTHESIS", "PROPOSED", "PROVISIONAL", "STABLE", "RETIRED",
               "REFUTED", "WIRED_UNPROVEN", "DESCRIPTOR", "DEGENERATE"]
# DEGENERATE added S114, on Greg's call, and it closes the session's sharpest correction.
#
# THE DEFECT, MEASURED: 15 of the 22 plays whose OWN evidence flags them - health.can_change_state
# opening with "NO", or a falsifier recording that it is already discharged or cannot be run - were
# still statused PROVISIONAL. A LIVE STATUS ON DEAD EVIDENCE IS AN INVITATION TO FIRE THE PLAY.
# The refutation was written down, honestly, in every case; it just sat BELOW the `call`, under a
# status that said the play was in good standing. Greg: "we should have a big correction... when
# the agents ignore the things that was our biggest win. Not good."
#
# The falsifier fields were the g24 run's most-praised content - specialists repeatedly said they
# were what stopped a bad emission ("if you cut the view, cut calls before falsifiers"). That makes
# a play that CARRIES a discharged falsifier and still reads PROVISIONAL the worst case of all: it
# spends the credibility the falsifiers earned.
#
# TWO DIFFERENT DEATHS, kept distinct because D37 keeps the observation and the story apart:
#   REFUTED    - the play's OWN falsifier came back negative. The claim is wrong.
#   DEGENERATE - the trigger cannot change state on the served data (the D23 disease): it fires
#                always, or never, or on a bar sited outside its own distribution. The claim may
#                still be TRUE; it carries no information as written, which is a different fault
#                and wants a different repair (re-site the bar, not discard the mechanism).
# Neither may read as a live gate. `check_status_honesty` below enforces it.
# DESCRIPTOR added on Greg's call, S111. It is a real and distinct category, not sloppiness:
# structure.squeeze_unwind's own `call` field reads "DESCRIPTOR grade - regime context, not a
# scored play", and the day-class doctrine calls day-class "the OVERARCHING descriptor". Filing it
# as HYPOTHESIS would assert it is an untested rule when it deliberately is not a rule at all, and
# would put pressure on future regime-context entries to dress up as plays.

# NOVEL_N1 added S111 (Greg): "some things won't have past instances because it was the first time
# we saw them but that doesn't make them bad." An argued mechanism observed once, honestly
# labelled, is NOT the same object as a claim with no argument - and D24 already says a finding is
# never disregarded for lacking past evidence. Anything genuinely new has no precedent by
# construction; the tropical channel is the clean case.
# NOT_A_PLAY added S112, on the same reasoning that added DESCRIPTOR to STATUS_ENUM: it is a real
# category, not sloppiness. Some entries are not conditional rules at all and a support class does
# not apply to them - forcing one is a category error that makes the entry look weakly-evidenced
# when it was never making a claim. The 82-play audit assigned it to exactly three, and each is
# independently corroborated by its own status field: structure.squeeze_unwind (status DESCRIPTOR,
# and its own `call` reads "DESCRIPTOR grade - regime context, not a scored play"),
# supply.lng_export_throughput_vessel_line (status WIRED_UNPROVEN - an INSTRUMENT merged to make a
# live channel readable, with zero consumers), and weekend.seam_delta_requires_level_difference
# (status PROPOSED). The S111 partial had filed the vessel line as ASSERTED, which read as a weak
# claim rather than as what it is.

# ==========================================================================================
# S114 CORRECTION RECORD — WHAT THE SCHEMA LEARNED FROM THE G24 RUN
# Greg: "Build on the instances that we got right in the schema and note the stuff we got wrong."
# Kept HERE, in the enforcing file, because that is the whole lesson below: a finding recorded
# somewhere nothing reads is a finding that expires.
# ==========================================================================================
#
# ---------------------------------------------------------------------------------------
# WHAT WE GOT RIGHT — the patterns to BUILD ON, each with the evidence that it worked
# ---------------------------------------------------------------------------------------
# 1. THE FALSIFIER FIELD IS THE MOST VALUABLE THING IN A PLAY, MEASURED BY ITS READERS.
#    Every g24 specialist said so unprompted and one put it as an instruction: "if you cut the
#    view, cut CALLS before FALSIFIERS." D-0723 named the falsifiers as what stopped it taking a
#    -450..-780 band. KEEP THEM VERBOSE. When trimming a view, trim anywhere else first.
#
# 2. CONTRADICTING INSTANCES EARN THEIR KEEP. E-0722: "a view that kept only the SUPPORTS
#    instances would have made me worse." The most useful single row it found was a play's own
#    falsifier text describing the exact configuration its day stood in, and recording that it had
#    already failed there twice. Never prune an instance for being unflattering.
#
# 3. EQUAL FOOTING (S112, Greg) WORKS — ONE instances[] list, one `action`, do beside dont. A
#    decline is evidence exactly as much as a fire. This is why ACTION_ENUM exists above.
#
# 4. A PLAY'S OWN WORDS ARE A TRUSTWORTHY CLASSIFIER; PROSE ANYWHERE IN THE PARAGRAPH IS NOT.
#    The nine DEGENERATE demotions of S114 were made on health.can_change_state OPENING with the
#    word NO - the play's own verdict, stated first. The same sweep keyed on the substring
#    "degenerate" ANYWHERE flagged 43 of 90 and was WRONG, catching plays that merely discuss
#    degeneracy while concluding they are sound. Read the opening verdict; never grep the body.
#
# 5. DECLARING AN ABSENCE BEATS REMOVING IT. Every guard added this session replaces a silent gap
#    with a NAMED one - the retro-instance `observation` action, the LEGACY-state note, the
#    unmeasured-vs-zero split in freeze_risk. A specialist can reason about a declared absence and
#    cannot reason about a missing one.
#
# ---------------------------------------------------------------------------------------
# WHAT WE GOT WRONG — the failure modes this file now gates
# ---------------------------------------------------------------------------------------
# A. A ONE-TIME CLEANUP THAT DOES NOT BECOME A GATE IS A CLEANUP THAT EXPIRES.
#    S112 stamped do/dont across 624 instances and found 43 declines reading as fires. It was
#    never made a schema rule - so every play merged since silently dropped the field, and by
#    S114 thirty-eight instances carried NO action at all. The identical defect, by the identical
#    door, two sessions later. `check_instance_actions` is the gate that should have existed then.
#
# B. A LIVE STATUS ON DEAD EVIDENCE IS AN INVITATION TO FIRE THE PLAY.
#    15 of the 22 plays flagged by their own health/falsifier still read PROVISIONAL. In EVERY
#    case the refutation was written down honestly - it just sat BELOW the `call`, under a status
#    saying the play was in good standing. This is the worst form of the fault because it spends
#    the credibility the falsifiers earned (see RIGHT #1). `check_status_honesty` gates it.
#
# C. A FIELD THAT IS A FLOAT ON MOST PLAYS AND A SENTENCE ON A FEW BREAKS EVERY CONSUMER.
#    8 of 90 plays carried PROSE in `confidence`. Anything that sorts or thresholds on it
#    mis-handled them silently. Fixed by moving prose to `confidence_note` and NULLING the value -
#    an invented number would have been worse than the prose. `check_field_types` gates it, and
#    it also rejects bool, which is an int subclass and would have sorted as the highest
#    confidence in the brain.
#
# D. A PLAY CAN ASSERT AN INPUT IT DOES NOT HAVE, AND THE ASSERTION IS WHAT GETS TRUSTED.
#    `magnitude.terminal_impact_coefficient_carry` advertised "ALL PRE-CUTOFF, so BLIND-LEGAL"
#    while its quantity needs a price the blind is never served. Four specialists caught it; its
#    own author was one. BEING PRE-CUTOFF IN TIME IS NOT THE SAME AS BEING SERVED. The A-46
#    evaluability pass now resolves every state_path against the actual slice - and immediately
#    found two more paths that resolve to nothing, one of them PROSE, on the play that should have
#    carried the whole block.
#
# E. A TEST WHOSE PREMISE CAN EXPIRE WILL EXPIRE. spawn's A-50 selftest asserted "g24 has no
#    outcome anywhere" - true when written, false within the same session once g24 was walked and
#    written up. Every group eventually becomes a walked group. Assert the GATE's behaviour on a
#    synthetic input, never a named live entity's current state.
#
# F. THE FIX ITSELF NEEDS THE SAME SCEPTICISM AS THE DEFECT. Three guards written this session
#    were wrong on their first cut and were caught only by negative-testing them: the
#    "degenerate"-substring sweep (RIGHT #4), a nested relive that mutated a SHARED list and
#    served one day's answer to all ten, and a percentile that sited a 1-hour stub inside a
#    distribution of 23-hour sessions. NC-3 is not paperwork - it caught all three.
# ==========================================================================================

SUPPORT_ENUM = ["MECHANISM_VERIFIED", "NOVEL_N1", "OUTCOME_CREDITED", "ASSERTED",
                "NOT_A_PLAY", "UNCLEAR", "UNAUDITED"]
D24_ENUM = ["found", "searched_none", "not_searched"]

# ACTION_ENUM added S114 (Greg: "I want to make sure we picked up that don't-do for the schema").
#
# EQUAL FOOTING IS A GREG RULE FROM S112: one `instances[]` list, one `action` field, `do` vs
# `dont` - because a DECLINE is evidence exactly as much as a fire is, and burying declines in a
# separate list (or omitting them) makes a play look better than its record. Stamping the brain
# then found 43 DECLINES ALREADY READING AS FIRES.
#
# THE REGRESSION, MEASURED S114: that stamping was a one-time pass and was NEVER MADE A SCHEMA
# RULE - `action` appeared in no enum and no gate. So it held for the instances that existed in
# S112 and every play merged since silently dropped it: 38 of 661 instances carried NO action at
# all, every one of them in a recently-merged weather play. An instance with no action reads as a
# fire by default, which is the S112 defect returning by the same door.
#
# THE LESSON, and it is the one this whole file exists for: a one-time cleanup that does not
# become a gate is a cleanup that expires. `check_instance_actions` below is the gate.
ACTION_ENUM = ["do", "dont", "observation"]
# `observation` added S114, and it is deliberately NARROW so it cannot become an escape hatch from
# the do/dont discipline it sits beside.
#
#   do          - the play FIRED on that day and this is what followed.
#   dont        - the play DECLINED on that day. Equal footing: a decline is evidence exactly as
#                 much as a fire, and burying declines is how 43 of them read as fires pre-S112.
#   observation - a CORPUS or CENSUS measurement supporting or refuting the claim, on a day the
#                 play was NOT RUN AS A GATE AT ALL (it neither fired nor declined - typically
#                 because it did not exist yet). These are D24 retro-instances.
#
# WHY IT IS NOT A LOOPHOLE: `observation` asserts NO live record, and `fire_record` below counts
# do/dont ONLY. A play whose instances are entirely observations therefore shows n=0 fires and
# n=0 declines - visibly untested - which is the honest reading and the opposite of what a
# mislabelled `do` would have claimed for it. All 38 unstamped instances found at S114 were of
# this kind: every one belongs to a play merged that same session that has never run.

# core fields that survive as themselves
CORE = ["id", "target", "one_line", "trigger", "read", "call", "mechanism",
        "requires", "scope", "caveats", "confidence"]

# every known status string -> (enum, note_prefix). Anything not here STOPS the migration
# and is reported for Greg, per the SOP rule that a gap stops the line rather than being guessed.
STATUS_MAP = {
    "PROVISIONAL": ("PROVISIONAL", None),
    "STABLE": ("STABLE", None),
    "HYPOTHESIS": ("HYPOTHESIS", None),
    "PROPOSED": ("PROPOSED", None),
    "PROPOSAL": ("PROPOSED", "was: PROPOSAL"),
    "PROVISIONAL_WEAKENED": ("PROVISIONAL", "weakened - see status_note"),
    "DESCRIPTOR": ("DESCRIPTOR", None),
}
STATUS_PREFIX = [
    ("REFUTED", "REFUTED"),
    ("WIRED_UNPROVEN", "WIRED_UNPROVEN"),
    ("PROPOSED", "PROPOSED"),
    ("PROVISIONAL", "PROVISIONAL"),
]

# the two dialects for the same quantity (turnaround memo 1.3, never fixed)
MAGNITUDE_ALIASES = ["guessed_net_usd", "expected_magnitude_usd", "guess_day_move_usd"]

# hand-curated condition map, carried over from condition_audit.py's REGISTRY. Asserted by hand
# on purpose; see the docstring.
CONDITION_MAP = {
    "structure.accumulation_arm_turn": [
        dict(quantity="big_print_b_share", state_path="tape_conditions.big_print_b_share",
             reference="absolute", comparator=">=", threshold=0.55, units="share"),
        dict(quantity="big_print_b_share", state_path="tape_conditions.big_print_b_share",
             reference="absolute", comparator=">=", threshold=0.62, units="share"),
        dict(quantity="gw_hdd", state_path="weather.gw_hdd",
             reference="absolute", comparator=">=", threshold=16.4, units="gw_hdd"),
    ],
    "magnitude.shoulder_weather_band_void": [
        dict(quantity="forecast_gw_hdd", state_path="weather_forecast.forecast_gw_hdd",
             reference="absolute", comparator="<=", threshold=13.5, units="gw_hdd"),
        dict(quantity="forecast_gw_hdd", state_path="weather_forecast.forecast_gw_hdd",
             reference="absolute", comparator=">=", threshold=16.0, units="gw_hdd"),
    ],
    "magnitude.s1void_injection_chain_bleed": [
        dict(quantity="session_b_share", state_path="tape_conditions.session_b_share",
             reference="absolute", comparator="<", threshold=0.50, units="share"),
    ],
    "monday.overnight_headfake_into_catchup": [
        dict(quantity="session_b_share", state_path="tape_conditions.session_b_share",
             reference="absolute", comparator="<", threshold=0.50, units="share"),
    ],
    "tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell": [
        dict(quantity="session_signed_flow", state_path="tape_conditions.session_signed_flow",
             reference="absolute", comparator=">", threshold=t, units="lots")
        for t in (1000, 1500, 2000, 3000)
    ],
    "magnitude.terminal_impact_coefficient_carry": [
        dict(quantity="ph3_signed_flow_abs", state_path="tape_conditions.phase_signed_flow[2]",
             reference="absolute", comparator=">=", threshold=500, units="lots"),
    ],
    "weekend.seam_sign_from_stability_ladder": [
        dict(quantity="mm_net_pctile_3y", state_path="cot.managed_money_net_pctile_3y",
             reference="percentile_3y", comparator="<=", threshold=5.0, units="pctile"),
    ],
    "boundary.weekend_gap_wide_band_emission": [
        dict(quantity="mm_net_pctile_3y", state_path="cot.managed_money_net_pctile_3y",
             reference="percentile_3y", comparator="<=", threshold=5.0, units="pctile"),
    ],
}


def blank_play_extras():
    """the typed slots every play gains, empty until the audit populates them."""
    return OrderedDict([
        ("status_note", ""),
        ("status_original", ""),      # the raw pre-migration string, verbatim, always
        ("falsifier", ""),
        ("support", "UNAUDITED"),
        ("conditions", []),
        ("conditions_state", "unparsed"),
        ("instances", []),
        ("corpus", OrderedDict([("d24_state", "not_searched"), ("searched_on", None),
                                ("searched_scope", ""), ("n_found", 0)])),
        ("forward", []),
        ("provenance", OrderedDict([("merged_session", None), ("brain_version", None),
                                    ("from_proposal", None), ("proposed_by", None)])),
        ("health", OrderedDict([("degenerate_block_share", None), ("can_change_state", None),
                                ("last_checked", None)])),
        ("legacy_notes", OrderedDict()),
    ])


# --------------------------------------------------------------------------------------
def normalize_status(raw):
    """-> (enum, note, ok). ok=False means STOP and ask, never guess."""
    if raw is None:
        return "HYPOTHESIS", "status was absent in s105.0", True
    s = str(raw).strip()
    if s in STATUS_MAP:
        e, n = STATUS_MAP[s]
        return e, (n or ""), True
    for prefix, enum in STATUS_PREFIX:
        if s.upper().startswith(prefix):
            return enum, s, True      # whole original string preserved as the note
    return None, s, False


def leaves(o, acc):
    """every scalar leaf, for the round-trip proof."""
    if isinstance(o, dict):
        for k, v in o.items():
            acc.append(str(k))
            leaves(v, acc)
    elif isinstance(o, list):
        for v in o:
            leaves(v, acc)
    else:
        acc.append(str(o))
    return acc


def migrate_play(p, unmapped):
    out = OrderedDict()
    src = copy.deepcopy(p)

    for k in CORE:
        if k in src:
            out[k] = src.pop(k)

    raw_status = src.pop("status", None)
    enum, note, ok = normalize_status(raw_status)
    if not ok:
        unmapped.append((p.get("id"), note))
        enum = "HYPOTHESIS"
    out["status"] = enum

    extras = blank_play_extras()
    extras["status_note"] = note
    for k, v in extras.items():
        out.setdefault(k, v)
    # the raw string, verbatim and unparaphrased - this is what makes the round-trip provable
    out["status_original"] = "" if raw_status is None else str(raw_status)

    # Fields that map onto typed slots are COPIED, not moved: the original key and value stay in
    # legacy_notes as well. Duplication there is the price of a provable round trip, and cheap.
    if "falsifier" in src:
        out["falsifier"] = src["falsifier"]
    if "merged" in src:
        out["provenance"]["merged_session"] = src["merged"]
    if "proposed_by" in src:
        out["provenance"]["proposed_by"] = src["proposed_by"]

    # every *_forward_evidence dialect ALSO collapses into the typed forward[] slot, tagged
    for k in [k for k in list(src) if "forward_evidence" in k or k == "forward_test"]:
        out["forward"].append(OrderedDict([("tag", k), ("text", src[k])]))

    if p.get("id") in CONDITION_MAP:
        out["conditions"] = CONDITION_MAP[p["id"]]
        out["conditions_state"] = "mapped_by_hand"

    # EVERYTHING ELSE is preserved verbatim - nothing is deleted, ever
    for k in list(src):
        out["legacy_notes"][k] = src.pop(k)

    return out


def run_migrate(write):
    brain = json.load(open(BRAIN, encoding="utf-8"), object_pairs_hook=OrderedDict)
    old_plays = brain["plays"]
    unmapped = []
    new_plays = [migrate_play(p, unmapped) for p in old_plays]

    print("=" * 84)
    print("BRAIN SCHEMA MIGRATION  (%s)   brain %s   %d plays"
          % ("WRITE" if write else "DRY RUN", brain.get("meta", {}).get("version"), len(old_plays)))
    print("=" * 84)

    before = Counter()
    for p in old_plays:
        for k in p:
            before[k] += 1
    after = Counter()
    for p in new_plays:
        for k in p:
            after[k] += 1
    print("distinct field names   BEFORE %3d   AFTER %3d" % (len(before), len(after)))
    print("statuses               BEFORE %3d   AFTER %3d"
          % (len({str(p.get('status')) for p in old_plays}),
             len({p['status'] for p in new_plays})))
    print("\nstatus distribution after:")
    for k, v in Counter(p["status"] for p in new_plays).most_common():
        print("   %-16s %3d" % (k, v))
    print("\nplays with conditions mapped: %d of %d (rest are `unparsed`, an open task not a guess)"
          % (sum(1 for p in new_plays if p["conditions"]), len(new_plays)))
    print("plays with a falsifier      : %d of %d"
          % (sum(1 for p in new_plays if p["falsifier"]), len(new_plays)))
    print("legacy keys preserved       : %d across all plays"
          % sum(len(p["legacy_notes"]) for p in new_plays))

    if unmapped:
        print("\n" + "!" * 84)
        print("STOP - %d status value(s) not in the map. Per the SOP a gap stops the line;" % len(unmapped))
        print("these are reported for Greg rather than guessed:")
        for pid, raw in unmapped:
            print("   %-52s %s" % (pid, raw[:90]))
        print("!" * 84)

    # ---- the round-trip proof: nothing lost -------------------------------------------
    old_leaves = Counter(leaves(old_plays, []))
    new_leaves = Counter(leaves(new_plays, []))
    lost = {k: c for k, c in old_leaves.items() if new_leaves[k] < c}
    print("\nROUND-TRIP: %d distinct leaf values before, %d after; LOST: %d"
          % (len(old_leaves), len(new_leaves), len(lost)))
    if lost:
        print("   MIGRATION IS LOSSY - refusing to write. First 10 missing values:")
        for k in list(lost)[:10]:
            print("      %s" % k[:100])
        return 1
    print("   lossless confirmed - every leaf value in the old brain is reachable in the new one")

    if not write:
        print("\nDRY RUN - nothing written. Re-run with --write to apply.")
        return 0
    if unmapped:
        print("\nrefusing to write while status values are unmapped.")
        return 1

    ver = brain.get("meta", {}).get("version", "unknown")
    bak = os.path.join(HERE, "knowledge", "ng_brain_%s_preschema_backup.json" % ver)
    shutil.copy2(BRAIN, bak)
    brain["plays"] = new_plays
    brain.setdefault("meta", OrderedDict())["schema"] = SCHEMA_VERSION
    with open(BRAIN, "w", encoding="utf-8") as fh:
        json.dump(brain, fh, indent=1, ensure_ascii=False)
    print("\nbackup  -> %s" % os.path.basename(bak))
    print("written -> knowledge/ng_brain.json  (meta.schema = %s)" % SCHEMA_VERSION)
    return 0


# --------------------------------------------------------------------------------------
# THE NON-PLAY SECTIONS  (S111, Greg: "then do the same treatment for the other docs")
#
# Surveyed at s105.0:
#   reasoning_method     18 keys, all strings, ZERO session-tagged  -> already clean, left alone
#   mechanisms           6 items, uniform {id,text}                 -> already clean, left alone
#   ruled_out_by_target  2 keys, small                              -> already clean, left alone
#   doctrine_tier3       21 keys / 93k chars, NINE session-tagged    -> the disease. treated.
#   open_frontier        33 items: 27 strings + 6 dicts in one list  -> untyped. treated.
#   fingerprints         4 keys, one session-tagged                  -> treated.
#
# THE SAME GOVERNING RULE AS THE PLAYS: the session belongs in a FIELD, never in the key name.
# `s101_3_protocol` becomes key `protocol` with session `s101.3` - so "what did S101.3 decide"
# and "show me every protocol entry" both become queries instead of greps.
# --------------------------------------------------------------------------------------
SESSION_RE = __import__("re").compile(r"(?:^|_)(s\d{2,3}[_.]?\d?|g\d{1,2})(?:_|$)", __import__("re").I)


def split_session_key(key):
    """-> (topic, session|None). Session moves to a field; the raw key is preserved regardless."""
    m = SESSION_RE.search(key)
    if not m:
        return key, None
    tok = m.group(1)
    topic = (key[:m.start()] + "_" + key[m.end():]).strip("_") or key
    sess = tok.lower().replace("_", ".") if tok.lower().startswith("s") else tok.lower()
    return topic, sess


def migrate_sections(brain):
    """returns (new_sections_dict, notes[]) - lossless: original keys always preserved."""
    notes = []

    # ---- doctrine_tier3 -> typed entry list ------------------------------------------
    dt = brain.get("doctrine_tier3")
    if isinstance(dt, dict):
        entries = []
        for k, v in dt.items():
            topic, sess = split_session_key(k)
            entries.append(OrderedDict([
                ("topic", topic),
                ("session", sess),
                ("original_key", k),          # verbatim, so the round trip is provable
                ("kind", "doctrine"),
                ("body", v),
            ]))
            if sess:
                notes.append("doctrine_tier3: %s -> topic=%s session=%s" % (k, topic, sess))
        brain["doctrine"] = entries
        # the superseded SECTION NAME is itself preserved as a value, so the round trip holds
        brain["doctrine_legacy"] = OrderedDict([
            ("superseded_section", "doctrine_tier3"),
            ("note", "superseded by `doctrine` (S111 schema). Every entry, including its "
                     "original key, is present in `doctrine` with the session as a field."),
        ])
        del brain["doctrine_tier3"]

    # ---- open_frontier -> one uniform shape -------------------------------------------
    of = brain.get("open_frontier")
    if isinstance(of, list):
        items = []
        for i, it in enumerate(of):
            if isinstance(it, dict):
                e = OrderedDict([("kind", "structured"), ("session", None)])
                e.update(it)
                items.append(e)
            else:
                txt = str(it)
                head = txt.split(" - ")[0].split(":")[0][:70]
                _, sess = split_session_key(head.replace(" ", "_"))
                items.append(OrderedDict([("kind", "note"), ("session", sess),
                                          ("headline", head), ("text", txt)]))
        brain["open_frontier"] = items
        notes.append("open_frontier: normalized %d items (%d were bare strings) to one shape"
                     % (len(items), sum(1 for x in of if not isinstance(x, dict))))

    # ---- fingerprints: session out of the key ------------------------------------------
    fp = brain.get("fingerprints")
    if isinstance(fp, dict):
        moved = {}
        for k in list(fp):
            topic, sess = split_session_key(k)
            if sess:
                moved[k] = OrderedDict([("topic", topic), ("session", sess),
                                        ("original_key", k), ("body", fp.pop(k))])
        if moved:
            fp["session_additions"] = list(moved.values())
            notes.append("fingerprints: %d session-tagged key(s) moved into session_additions"
                         % len(moved))
    return brain, notes


def run_sections(write):
    raw = json.load(open(BRAIN, encoding="utf-8"), object_pairs_hook=OrderedDict)
    before_leaves = Counter(leaves(copy.deepcopy(raw), []))
    new, notes = migrate_sections(copy.deepcopy(raw))
    after_leaves = Counter(leaves(copy.deepcopy(new), []))

    print("=" * 84)
    print("NON-PLAY SECTION MIGRATION  (%s)" % ("WRITE" if write else "DRY RUN"))
    print("=" * 84)
    for n in notes:
        print("  " + n)
    if not notes:
        print("  nothing to do - sections already conform")

    dt = new.get("doctrine", [])
    print("\ndoctrine entries: %d  (%d carry a session field)"
          % (len(dt), sum(1 for e in dt if e.get("session"))))
    of = new.get("open_frontier", [])
    print("open_frontier   : %d items, kinds %s"
          % (len(of), dict(Counter(x.get("kind") for x in of if isinstance(x, dict)))))

    lost = {k: c for k, c in before_leaves.items() if after_leaves[k] < c}
    print("\nROUND-TRIP: %d distinct leaves before, %d after; LOST: %d"
          % (len(before_leaves), len(after_leaves), len(lost)))
    if lost:
        print("   LOSSY - refusing to write. Missing:")
        for k in list(lost)[:10]:
            print("      %s" % k[:100])
        return 1
    print("   lossless confirmed")

    if not write:
        print("\nDRY RUN - nothing written.")
        return 0
    ver = new.get("meta", {}).get("version", "unknown")
    bak = os.path.join(HERE, "knowledge", "ng_brain_%s_presections_backup.json" % ver)
    shutil.copy2(BRAIN, bak)
    with open(BRAIN, "w", encoding="utf-8") as fh:
        json.dump(new, fh, indent=1, ensure_ascii=False)
    print("\nbackup  -> %s\nwritten -> knowledge/ng_brain.json" % os.path.basename(bak))
    return 0


def check_sections(brain):
    """THE SECTION-INDEX GATE (S114).

    ONE BRAIN DOC (Greg): behaviour doctrine does not get its own file. But a section does NOT have
    to fit the play schema - 'Same doc but doesn't have to fit the schema.' So this gate checks
    DECLARATION, never shape: every top-level section must be named in `meta.sections` with what it
    IS and who READS it, and every declared section must exist. Nothing here constrains a section's
    internal form.

    Why it exists: before S114 `meta.purpose` listed the sections in PROSE and the prose was stale -
    it omitted `doctrine` and `doctrine_legacy` outright. A section could be added and no agent
    would ever be told it was there.
    """
    idx = (brain.get("meta") or {}).get("sections") or {}
    declared = {k for k in idx if not k.startswith("_")}
    present = {k for k in brain if k != "meta"}
    undeclared = sorted(present - declared)
    missing = sorted(declared - present)
    incomplete = sorted(k for k in declared if not (idx[k] or {}).get("is")
                        or not (idx[k] or {}).get("read_by"))
    # `roles` is what brain_view.py actually SERVES on. A section declared without it would be
    # silently invisible to every role - the same silent-absence shape as holes #7/#8. A section
    # served to nobody is legal (doctrine_legacy) but must SAY so via withheld_why.
    no_roles = sorted(k for k in declared if "roles" not in (idx[k] or {}))
    dead_unexplained = sorted(k for k in declared
                              if not ((idx[k] or {}).get("roles") or [])
                              and "roles" in (idx[k] or {})
                              and not (idx[k] or {}).get("withheld_why"))
    print("\nSECTION INDEX (meta.sections): %d declared, %d present" % (len(declared), len(present)))
    for k in sorted(present):
        e = idx.get(k) or {}
        print("   %-22s %-9s %-13s %s"
              % (k, "required" if e.get("required") else "optional",
                 ",".join(e.get("roles") or []) or "-served to none-",
                 (e.get("read_by") or "-")[:40]))
    fails = []
    if undeclared:
        fails.append("UNDECLARED section(s) - present in the brain, absent from meta.sections: %s"
                     % ", ".join(undeclared))
    if missing:
        fails.append("DECLARED but ABSENT section(s): %s" % ", ".join(missing))
    if incomplete:
        fails.append("declared without `is` and `read_by`: %s" % ", ".join(incomplete))
    if no_roles:
        fails.append("declared without `roles` - brain_view would serve it to nobody, silently: %s"
                     % ", ".join(no_roles))
    if dead_unexplained:
        fails.append("served to NO role and no `withheld_why` saying why: %s"
                     % ", ".join(dead_unexplained))
    return fails


# Fields whose TYPE is load-bearing because something downstream sorts, thresholds or
# arithmetics on them. A field that is a float on most plays and a SENTENCE on a few is the
# defect this catches: every consumer that compares it either crashes or silently mis-ranks.
TYPED_FIELDS = {
    # (field, allowed python types, why)
    "confidence": ((int, float, type(None)),
                   "numeric or null. S114: 8 of 90 plays carried a PROSE sentence here while 59 "
                   "carried a float - found by a g24 specialist ('anything that sorts or thresholds "
                   "on confidence will mis-handle it'). Prose belongs in `confidence_note`. A null "
                   "is legal and honest; an INVENTED number would be worse than the prose was."),
}



def check_instance_actions(plays):
    """Every instance must declare `do` or `dont`. A missing action is not neutral - it reads as a
    FIRE, which is how 43 declines were mis-counted before S112 stamped them."""
    bad, missing = [], []
    for p in plays:
        for k, i in enumerate(p.get("instances") or []):
            a = i.get("action")
            if a is None:
                missing.append("%s[%d]" % (p["id"], k))
            elif a not in ACTION_ENUM:
                bad.append("%s[%d] action=%r" % (p["id"], k, a))
    # SURFACE THE SPLIT. A play with instances but ZERO do/dont has no live record at all,
    # however many observations it carries - say so rather than letting the instance COUNT imply
    # a track record.
    for p in plays:
        insts = p.get("instances") or []
        if not insts:
            continue
        live = [i for i in insts if i.get("action") in ("do", "dont")]
        if insts and not live:
            p.setdefault("fire_record", {})
            p["fire_record"] = {"do": 0, "dont": 0, "observation": len(insts),
                                "note": "NO LIVE RECORD. Every instance is a corpus observation - "
                                        "this play has never fired or declined on a scored day."}
        else:
            p["fire_record"] = {
                "do": sum(1 for i in insts if i.get("action") == "do"),
                "dont": sum(1 for i in insts if i.get("action") == "dont"),
                "observation": sum(1 for i in insts if i.get("action") == "observation")}
    out = []
    if missing:
        out.append("instances with NO `action` (%d): %s%s - a missing action reads as a FIRE, which "
                   "is exactly how 43 declines were mis-counted before S112. Stamp do/dont."
                   % (len(missing), ", ".join(missing[:6]),
                      " ..." if len(missing) > 6 else ""))
    if bad:
        out.append("instances with an action outside %s (%d): %s"
                   % (ACTION_ENUM, len(bad), ", ".join(bad[:6])))
    return out


LIVE_STATUSES = ("PROVISIONAL", "STABLE")


def check_status_honesty(plays):
    """A play may not read LIVE while its own evidence says it is dead. (S114, Greg.)

    MEASURED: 15 of the 22 plays whose own health/falsifier flags them were still PROVISIONAL. The
    refutation was written down honestly in every case - it just sat BELOW the `call`, under a
    status saying the play was in good standing.

    THIS REPORTS, IT DOES NOT AUTO-DEMOTE, except where the play's OWN opening verdict is the word
    NO. Inferring death from prose anywhere in a paragraph is the fuzzy-matching error this file
    warns about at the top - it produced a 43-of-90 false-positive sweep on the first attempt, which
    would have talked specialists out of working plays.
    """
    import re as _re
    fails = []
    for p in plays:
        if p.get("status") not in LIVE_STATUSES:
            continue
        h = ((p.get("health") or {}).get("can_change_state") or "")
        h = h if isinstance(h, str) else ""
        opens_no = _re.match(r"no\b|not applicable\b|none\b", h.lower().lstrip(" -*\"'"))
        if opens_no:
            fails.append("%s is %s but its OWN health.can_change_state opens \"%s\" - a live status "
                         "on a trigger that cannot change state. Use DEGENERATE (the claim may still "
                         "be true; it carries no information as written)."
                         % (p["id"], p["status"], h[:60]))
    return fails

def check_field_types(plays):
    """Type gate for the fields something downstream computes on. Declaration-only elsewhere -
    this deliberately constrains a handful of fields, not the schema at large."""
    fails = []
    for field, (types, why) in TYPED_FIELDS.items():
        # bool is a SUBCLASS of int in python, so a stray `confidence: true` would pass an
        # isinstance(int) check and then sort as 1.0 - the highest confidence in the brain.
        # Found by negative-testing this gate rather than by it firing in anger.
        offenders = [p["id"] for p in plays
                     if field in p and (isinstance(p.get(field), bool)
                                        or not isinstance(p.get(field), types))]
        if offenders:
            fails.append("%s must be %s (%s) - %d offender(s): %s"
                         % (field, "/".join(t.__name__ for t in types), why,
                            len(offenders), ", ".join(offenders[:5])))
    return fails


def run_validate():
    brain = json.load(open(BRAIN, encoding="utf-8"))
    plays = brain["plays"]
    schema = brain.get("meta", {}).get("schema")
    print("brain %s | schema %s | %d plays"
          % (brain.get("meta", {}).get("version"), schema or "NONE (pre-migration)", len(plays)))
    section_fails = check_sections(brain)
    type_fails = check_field_types(plays)
    action_fails = check_instance_actions(plays)
    honesty_fails = check_status_honesty(plays)
    bad = Counter()
    for p in plays:
        if p.get("status") not in STATUS_ENUM:
            bad["status not in enum"] += 1
        if not p.get("falsifier"):
            bad["no falsifier"] += 1
        if p.get("support", "UNAUDITED") == "UNAUDITED":
            bad["support unaudited"] += 1
        if p.get("conditions_state") == "unparsed":
            bad["conditions unparsed"] += 1
        if (p.get("corpus") or {}).get("d24_state") == "not_searched":
            bad["corpus not searched"] += 1
    print("\nopen items (these are the work list, not errors):")
    for k, v in bad.most_common():
        print("   %-24s %3d of %d" % (k, v, len(plays)))
    if section_fails or type_fails or action_fails or honesty_fails:
        if section_fails:
            print("\nHARD FAIL - section index:")
            for f in section_fails:
                print("   %s" % f)
        if type_fails:
            print("\nHARD FAIL - field types:")
            for f in type_fails:
                print("   %s" % f)
        if action_fails:
            print("\nHARD FAIL - instance do/dont (equal footing, S112 Greg rule):")
            for f in action_fails:
                print("   %s" % f)
        if honesty_fails:
            print("\nHARD FAIL - status honesty (S114): a live status on dead evidence")
            for f in honesty_fails:
                print("   %s" % f)
        return 1
    return 0


def run_report():
    brain = json.load(open(BRAIN, encoding="utf-8"))
    print("QUESTIONS THE SCHEMA MAKES ANSWERABLE (each was a bespoke script this session):")
    for q in ["which plays carry an absolute bar, and on which served field",
              "which conditions cannot change state inside a block",
              "which plays rest on an outcome rather than a mechanism",
              "which plays have never been corpus-searched, and when was each last searched",
              "which plays have no falsifier",
              "which plays fired in group N and what they delivered",
              "which session merged this play, from whose proposal"]:
        print("   - %s" % q)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["validate", "migrate", "sections", "report"])
    ap.add_argument("--write", action="store_true", help="apply the migration (default is dry run)")
    a = ap.parse_args()
    if a.cmd == "migrate":
        return run_migrate(a.write)
    if a.cmd == "sections":
        return run_sections(a.write)
    if a.cmd == "validate":
        return run_validate()
    return run_report()


if __name__ == "__main__":
    sys.exit(main())
