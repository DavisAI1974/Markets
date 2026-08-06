"""blind_legality.py - can this play actually FIRE on a blind slice? (A-53.)

Specialist E, S114, on a play asserting its own blind-legality while its numerator is masked:
"It'd be cheap to sweep every play's `requires` against the served blind field set and flag the
mismatches mechanically - that's a script, not a judgment call."

WHY IT PAYS. Specialist D spent real effort standing down four plays that could NEVER have fired
in blind - `direction.flow_nowcast`, `daytype.eia_print_impulse_arbiter`,
`structure.void_precedes_impact_collapse`, `flow.flowless_reprice_is_not_absorption` - and wrote a
paragraph for each. A flag lets it dispose of them in one line. That is the cheap half.

THE EXPENSIVE HALF IS THE CONTRADICTION CHECK, and it is what E actually found:

    magnitude.terminal_impact_coefficient_carry
    requires: "prior session phase-3 price change and signed flow (tape_conditions) -
               ALL PRE-CUTOFF, so this is BLIND-LEGAL, not refine-only"

The play ASSERTS blind-legality in prose. Phase price change is a price-derived quantity and is
not served on a blind slice. A play that declares itself legal and is not is worse than one that
is silently unavailable, because the declaration is what a specialist trusts. E's contrast:
`flow_conviction_sign_gate` labels itself refine-only and is honest.

WHAT THIS DOES NOT DO. `requires` is 63 free-prose strings, 21 lists and 6 nulls, with only three
recognised tokens (`open_time_only` 15, `needs_intraday_reveal` 9, `needs_day_N-1_tape` 4). Prose
that matches no token is reported UNCLASSIFIED, never guessed - a wrong BLIND_OK would send a
specialist to an instrument that is not there, which is the exact failure being fixed.

    python blind_legality.py sweep --gid g22
    python blind_legality.py selftest
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
RN = os.path.join(HERE, "renders", "ng_refine_s95")

# tokens whose meaning is settled on this desk
OK_TOKENS = ("open_time_only", "needs_day_n-1_tape", "open-conditions", "never-masked",
             "pre-cutoff", "decision-time-legit")
NO_TOKENS = ("needs_intraday_reveal", "refine-only", "refine only")

# quantities a BLIND slice does not carry, because the price curve is the one deliberate mask (D2)
PRICE_DERIVED = ("phase price change", "phase_price_change", "price change", "close-off-extreme",
                 "curve_2h", "cum-from-anchor", "cum_from_anchor", "last_hour_dir",
                 "intraday close", "realized close", "day's own run size", "the day's own run")


def load_brain():
    with open(BRAIN, encoding="utf-8") as f:
        return json.load(f)


def masked_blocks(gid):
    """The blocks a blind slice freezes - read from the slice itself, never hardcoded."""
    import glob
    fs = sorted(glob.glob(os.path.join(RN, "%s_causal_slices" % gid, "state_*.json")))
    if not fs:
        return []
    with open(fs[0], encoding="utf-8") as f:
        d = json.load(f)
    day = [k for k in d if k.isdigit()]
    if not day:
        return []
    blk = d[day[0]]
    return sorted(b for b, v in blk.items() if isinstance(v, dict) and v.get("masked_one_shot"))


def classify(play):
    """-> (verdict, why). Verdicts: BLIND_OK | BLIND_UNAVAILABLE | CONTRADICTION | UNCLASSIFIED."""
    r = play.get("requires")
    toks = [r] if isinstance(r, str) else list(r or [])
    if not toks:
        return "UNCLASSIFIED", "no `requires` recorded"
    text = " ; ".join(str(t) for t in toks).lower()

    asserts_ok = any(t in text for t in OK_TOKENS)
    asserts_no = any(t in text for t in NO_TOKENS)
    price_hits = [p for p in PRICE_DERIVED if p in text]

    # the contradiction check: claims legality AND names a price-derived quantity
    if asserts_ok and price_hits:
        return ("CONTRADICTION",
                "asserts blind-legality (%s) while naming price-derived quantity/ies %s, which a "
                "blind slice does not carry. A play that declares itself legal and is not is worse "
                "than one silently unavailable - the declaration is what a specialist trusts."
                % (", ".join(t for t in OK_TOKENS if t in text), ", ".join(price_hits)))
    if asserts_no:
        return "BLIND_UNAVAILABLE", "declares %s" % ", ".join(t for t in NO_TOKENS if t in text)
    if price_hits:
        return ("BLIND_UNAVAILABLE",
                "needs price-derived quantity/ies %s" % ", ".join(price_hits))
    if asserts_ok:
        return "BLIND_OK", "declares %s" % ", ".join(t for t in OK_TOKENS if t in text)
    return "UNCLASSIFIED", "requires text matches no recognised token - NOT guessed"


def sweep(brain=None, verbose=True):
    brain = brain or load_brain()
    out = {}
    for p in brain["plays"]:
        v, why = classify(p)
        out[p["id"]] = {"verdict": v, "why": why}
    if verbose:
        import collections
        c = collections.Counter(v["verdict"] for v in out.values())
        print("BLIND LEGALITY SWEEP - %d plays" % len(out))
        for k in ("BLIND_OK", "BLIND_UNAVAILABLE", "CONTRADICTION", "UNCLASSIFIED"):
            print("   %-18s %3d" % (k, c.get(k, 0)))
        for k in ("CONTRADICTION", "BLIND_UNAVAILABLE"):
            names = [i for i, r in out.items() if r["verdict"] == k]
            if names:
                print("\n%s:" % k)
                for n in names:
                    print("   %-52s %s" % (n, out[n]["why"][:88]))
    return out


def cmd_selftest():
    fails = []

    def check(name, cond, detail=""):
        print("  %-58s %s%s" % (name, "PASS" if cond else "FAIL", ("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    print("blind_legality selftest")
    res = sweep(verbose=False)
    check("every play gets a verdict", len(res) == len(load_brain()["plays"]))

    # E's finding must be reproduced mechanically, or the sweep is not doing its job
    tic = res.get("magnitude.terminal_impact_coefficient_carry")
    print("     guard output: %s -> %s" % ("terminal_impact_coefficient_carry",
                                           tic["verdict"] if tic else "<missing>"))
    check("E's play is caught as a CONTRADICTION",
          tic and tic["verdict"] == "CONTRADICTION", tic["why"][:70] if tic else "")

    fn = res.get("direction.flow_nowcast")
    check("a needs_intraday_reveal play is BLIND_UNAVAILABLE",
          fn and fn["verdict"] == "BLIND_UNAVAILABLE", fn["verdict"] if fn else "")

    # NEGATIVE: unrecognised prose must NOT be silently called legal
    fake = {"id": "x", "requires": "some prose nobody has tokenised"}
    v, why = classify(fake)
    print("     guard output: unrecognised prose -> %s (%s)" % (v, why[:52]))
    check("NEGATIVE unrecognised prose is UNCLASSIFIED, never BLIND_OK", v == "UNCLASSIFIED")

    v2, _ = classify({"id": "y", "requires": None})
    check("NEGATIVE a missing `requires` is UNCLASSIFIED", v2 == "UNCLASSIFIED")

    v3, w3 = classify({"id": "z", "requires": "open_time_only, from curve_2h final-2h sign"})
    print("     guard output: fake self-declared-legal play -> %s" % v3)
    check("NEGATIVE a synthetic contradiction is caught", v3 == "CONTRADICTION")

    print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % fails))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sweep"); s.add_argument("--gid", default="")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.gid:
        print("masked blocks on a %s blind slice: %s\n" % (a.gid, masked_blocks(a.gid)))
    sweep()
    return 0


if __name__ == "__main__":
    sys.exit(main())
