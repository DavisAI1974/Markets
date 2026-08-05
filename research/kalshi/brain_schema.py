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
               "REFUTED", "WIRED_UNPROVEN", "DESCRIPTOR"]
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
SUPPORT_ENUM = ["MECHANISM_VERIFIED", "NOVEL_N1", "OUTCOME_CREDITED", "ASSERTED",
                "UNCLEAR", "UNAUDITED"]
D24_ENUM = ["found", "searched_none", "not_searched"]

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


def run_validate():
    brain = json.load(open(BRAIN, encoding="utf-8"))
    plays = brain["plays"]
    schema = brain.get("meta", {}).get("schema")
    print("brain %s | schema %s | %d plays"
          % (brain.get("meta", {}).get("version"), schema or "NONE (pre-migration)", len(plays)))
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
    ap.add_argument("cmd", choices=["validate", "migrate", "report"])
    ap.add_argument("--write", action="store_true", help="apply the migration (default is dry run)")
    a = ap.parse_args()
    if a.cmd == "migrate":
        return run_migrate(a.write)
    if a.cmd == "validate":
        return run_validate()
    return run_report()


if __name__ == "__main__":
    sys.exit(main())
