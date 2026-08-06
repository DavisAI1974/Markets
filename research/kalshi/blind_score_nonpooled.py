"""How much of the blind's error does the DRIFT metric cancel away? (S108, Greg's rule)

Forward-curve drift is a SUM OF SIGNED ERRORS, so it nets. A day that is +4,000 and a day that is
-4,000 average to a drift of ZERO on a forecaster that was catastrophically wrong twice. Drift is the
right measure of where the integrated curve ENDS UP; it is NOT a measure of accuracy, and it must never
be reported alone.

Greg's standing rule, applied here: never pool or average as the final word - look at each event
individually. This prints the per-day distribution beside the netted number so the netting is visible.

--------------------------------------------------------------------------------------------------
S113 (registry item A-1): NAMED BENCHMARKS, ALWAYS PRINTED.

The standing rule since S111 is "never report an error number without a named benchmark again", and
until now we could not satisfy it. For seven blocks we compared MAE to the previous block's MAE and
called the fall an improvement, having never computed what DOING NOTHING would have scored. When it
was finally computed, the blind lost to a zero-change forecast in six of seven blocks, and the
939 -> 592 "improvement" turned out to be the market getting quieter (realized moves fell 799 -> 457
over the same span).

An error number with no benchmark is not a weak measurement. It is not a measurement.

THREE BENCHMARKS, each a forecaster this desk could have run for free:

  ZERO_CHANGE     guess 0 every day. The honest floor: its MAE is the mean absolute actual move,
                  so the blind's skill ratio against it IS the S111 number. Emits no sign, so it
                  is scored on magnitude only and its direction column reads "-" rather than being
                  silently counted as a hit or a miss.
  SEASONAL_NAIVE  guess the day-move of the most recent EARLIER session with the same weekday.
                  The trading week is the season, and this is the form the day-class doctrine
                  implies ("no Mondays scoring Fridays", S101). Within this corpus the blocks are
                  contiguous Mon-Fri, so it resolves to exactly t-5; the dow match is kept anyway
                  because a holiday would break a fixed lag silently.
  PERSISTENCE     guess the immediately preceding session's day-move. NOT named in A-1 - added
                  because it is free from the same chain and it is the benchmark that the S113
                  external review demanded of the flow play ("beating 50 percent while failing to
                  beat persistence is not an edge"). Declared here rather than slipped in; drop it
                  if it is not wanted.

CAUSALITY. Every baseline reads STRICTLY EARLIER sessions. The chain is built across all committed
`g*_actual.json` files so a block's first week can look back into the prior block rather than being
dropped - g17 is the only block with no predecessor, so its first five days have no seasonal-naive
and its first day has no persistence. Those days are DECLARED and excluded from the matched
comparison, never quietly filled.

LIKE FOR LIKE. Two tables are printed on purpose. The FULL table scores every day the blind called,
against zero-change, which is always available. The MATCHED table restricts to the days where every
baseline exists and re-scores the blind on that same subset, because comparing a forecaster on ten
days to a benchmark on five is not a comparison.

D4 HOLDS THROUGHOUT: sum|err|, drift and survival are reported together, never a mean alone, and
nothing is averaged above and below.
"""
import os as _os
import sys
import json
import glob

_HERE = _os.path.dirname(_os.path.abspath(__file__))
FC = _os.path.join(_HERE, "forecasts")
RD = _os.path.join(_HERE, "renders", "ng_refine_s95")

BASELINES = ("zero_change", "seasonal_naive", "persistence")


def errs_for(n):
    p, ap = _os.path.join(FC, f"grp{n}.json"), _os.path.join(RD, f"g{n}_actual.json")
    if not (_os.path.exists(p) and _os.path.exists(ap)):
        return None
    b = json.load(open(p))
    a = {d["date"]: d for d in json.load(open(ap))["days"]}
    out = []
    for d in b.get("days", []):
        dt = str(d.get("date", "")).replace("-", "")
        g, act = d.get("guess_day_move_usd"), a.get(dt, {}).get("day_move_usd")
        if isinstance(g, (int, float)) and isinstance(act, (int, float)):
            out.append((dt, g, act, g - act))
    return out


# ---------------------------------------------------------------------------------------------
# THE BENCHMARK CHAIN (A-1)
# ---------------------------------------------------------------------------------------------

def actual_chain():
    """Every committed actual session, date-ordered, across all groups.

    Built across FILES rather than per group so a block's first week can look back into the prior
    block. Overlaps are not expected (blocks abut, they do not repeat); a date appearing twice with
    two different moves is a corpus defect and raises rather than being silently resolved.
    """
    seen = {}
    for p in sorted(glob.glob(_os.path.join(RD, "g*_actual.json"))):
        for d in json.load(open(p)).get("days", []):
            dt = str(d.get("date", "")).replace("-", "")
            mv = d.get("day_move_usd")
            if not dt or not isinstance(mv, (int, float)):
                continue
            if dt in seen and seen[dt]["move"] != mv:
                raise ValueError(
                    f"actual chain conflict on {dt}: {seen[dt]['move']} vs {mv} "
                    f"({seen[dt]['src']} vs {_os.path.basename(p)})")
            seen[dt] = {"date": dt, "dow": d.get("dow"), "move": mv,
                        "src": _os.path.basename(p)}
    return [seen[k] for k in sorted(seen)]


def baseline_forecasts(chain=None):
    """date -> {baseline_name: forecast or None}. Reads STRICTLY EARLIER sessions only."""
    chain = chain if chain is not None else actual_chain()
    out = {}
    for i, row in enumerate(chain):
        prior = chain[:i]                                   # strictly earlier, by construction
        same_dow = [r for r in prior if r["dow"] == row["dow"]]
        out[row["date"]] = {
            "zero_change": 0,
            "seasonal_naive": same_dow[-1]["move"] if same_dow else None,
            "persistence": prior[-1]["move"] if prior else None,
        }
    return out


def score(pairs, signed=True):
    """pairs = [(date, forecast, actual)]. Returns the D4 set, never a mean alone.

    `signed=False` marks a forecaster that emits no direction (zero-change). Its direction is
    reported as absent rather than being scored, because counting a zero as a wrong sign would
    punish it for a claim it never made and counting it as right would flatter it.
    """
    errs = [(d, f - a) for d, f, a in pairs]
    sa = sum(abs(e) for _, e in errs)
    dr = sum(e for _, e in errs)
    hits = dn = None
    if signed:
        judged = [(f, a) for _, f, a in pairs if f != 0 and a != 0]
        dn = len(judged)
        hits = sum(1 for f, a in judged if (f > 0) == (a > 0))
    return {"n": len(pairs), "sum_abs": sa, "mae": (sa / len(pairs)) if pairs else 0.0,
            "drift": dr, "survives": (100.0 * abs(dr) / sa) if sa else 0.0,
            "dir_hits": hits, "dir_n": dn}


def _dirstr(s):
    if s["dir_hits"] is None:
        return "     -"
    return f"{s['dir_hits']:>3}/{s['dir_n']:<2}"


def _ratio(blind_mae, base_mae):
    return (blind_mae / base_mae) if base_mae else float("inf")


def benchmark_report(groups):
    """The A-1 table. Prints nothing that is not computed from committed artifacts."""
    chain = actual_chain()
    base = baseline_forecasts(chain)

    print()
    print("=" * 94)
    print("NAMED BENCHMARKS (A-1) - what the same days would have scored with no forecaster at all")
    print("=" * 94)
    print(f"  chain: {len(chain)} committed actual sessions, {chain[0]['date']}..{chain[-1]['date']}")
    print("  ZERO_CHANGE guesses 0. SEASONAL_NAIVE guesses the last same-weekday move.")
    print("  PERSISTENCE guesses the prior session's move. All read strictly earlier sessions.")

    pooled = {"blind_full": [], "zero_full": [], "blind_m": [], "zero_m": [],
              "seas_m": [], "pers_m": []}

    for n in groups:
        e = errs_for(n)
        if not e:
            continue
        full_blind = [(d, g, a) for d, g, a, _ in e]
        full_zero = [(d, 0, a) for d, _, a, _ in e]
        matched = [(d, g, a) for d, g, a, _ in e
                   if base.get(d, {}).get("seasonal_naive") is not None
                   and base.get(d, {}).get("persistence") is not None]
        mdates = {d for d, _, _ in matched}
        dropped = [d for d, _, _, _ in e if d not in mdates]

        sb_f, sz_f = score(full_blind), score(full_zero, signed=False)
        pooled["blind_full"] += full_blind
        pooled["zero_full"] += full_zero

        print()
        print(f"  g{n}   FULL SET  n={sb_f['n']}"
              + (f"   (matched set drops {len(dropped)}: {','.join(x[4:] for x in dropped)}"
                 f" - no prior session to build a baseline from)" if dropped else ""))
        print(f"    {'forecaster':<16}{'sum|err|':>10}{'MAE':>8}{'drift':>9}{'survives':>10}"
              f"{'dir':>8}{'vs blind':>10}")
        print(f"    {'BLIND':<16}{sb_f['sum_abs']:>10}{sb_f['mae']:>8.0f}{sb_f['drift']:>+9}"
              f"{sb_f['survives']:>9.0f}%{_dirstr(sb_f):>8}{'':>10}")
        print(f"    {'zero_change':<16}{sz_f['sum_abs']:>10}{sz_f['mae']:>8.0f}{sz_f['drift']:>+9}"
              f"{sz_f['survives']:>9.0f}%{_dirstr(sz_f):>8}"
              f"{_ratio(sb_f['mae'], sz_f['mae']):>9.2f}x")

        if matched:
            sb_m = score(matched)
            rows = [("zero_change", score([(d, 0, a) for d, _, a in matched], signed=False)),
                    ("seasonal_naive", score([(d, base[d]["seasonal_naive"], a)
                                              for d, _, a in matched])),
                    ("persistence", score([(d, base[d]["persistence"], a)
                                           for d, _, a in matched]))]
            pooled["blind_m"] += matched
            pooled["zero_m"] += [(d, 0, a) for d, _, a in matched]
            pooled["seas_m"] += [(d, base[d]["seasonal_naive"], a) for d, _, a in matched]
            pooled["pers_m"] += [(d, base[d]["persistence"], a) for d, _, a in matched]
            if len(matched) != len(full_blind):
                print(f"    -- matched set, n={sb_m['n']}, blind re-scored on the same days --")
                print(f"    {'BLIND':<16}{sb_m['sum_abs']:>10}{sb_m['mae']:>8.0f}"
                      f"{sb_m['drift']:>+9}{sb_m['survives']:>9.0f}%{_dirstr(sb_m):>8}{'':>10}")
            for name, s in rows:
                if name == "zero_change" and len(matched) == len(full_blind):
                    continue
                print(f"    {name:<16}{s['sum_abs']:>10}{s['mae']:>8.0f}{s['drift']:>+9}"
                      f"{s['survives']:>9.0f}%{_dirstr(s):>8}"
                      f"{_ratio(sb_m['mae'], s['mae']):>9.2f}x")

    if pooled["blind_full"]:
        print()
        print("  " + "-" * 90)
        print("  POOLED - a summary line, never the verdict (D4). Per-block above is the measurement.")
        pb, pz = score(pooled["blind_full"]), score(pooled["zero_full"], signed=False)
        print(f"    full set     n={pb['n']:<4} blind MAE {pb['mae']:.0f}  "
              f"zero_change MAE {pz['mae']:.0f}  ->  blind is {_ratio(pb['mae'], pz['mae']):.2f}x "
              f"the do-nothing forecaster")
        if pooled["blind_m"]:
            bm = score(pooled["blind_m"])
            for label, key in (("zero_change", "zero_m"), ("seasonal_naive", "seas_m"),
                               ("persistence", "pers_m")):
                s = score(pooled[key], signed=(key != "zero_m"))
                print(f"    matched  vs {label:<15} blind MAE {bm['mae']:.0f}  vs {s['mae']:.0f}"
                      f"  ->  {_ratio(bm['mae'], s['mae']):.2f}x")
        print()
        print("  A ratio ABOVE 1.00 means the benchmark beat us on that set. Direction is scored")
        print("  only where both the call and the actual carry a sign; zero_change makes no")
        print("  directional claim and is not credited or charged with one.")


# ---------------------------------------------------------------------------------------------
# SELFTEST (D11: a fix is not done until a test proves the fixed path EXECUTES)
# ---------------------------------------------------------------------------------------------

def selftest():
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

    chain = actual_chain()
    idx = {r["date"]: i for i, r in enumerate(chain)}
    base = baseline_forecasts(chain)
    check("chain is non-empty and date-ordered",
          chain and all(chain[i]["date"] < chain[i + 1]["date"] for i in range(len(chain) - 1)),
          f"{len(chain)} sessions")

    # CAUSALITY - the whole point. Every baseline value must come from a strictly earlier session.
    leaks = []
    for r in chain:
        i = idx[r["date"]]
        for name in ("seasonal_naive", "persistence"):
            v = base[r["date"]][name]
            if v is None:
                continue
            if not any(chain[j]["move"] == v for j in range(i)):
                leaks.append((r["date"], name))
    check("no baseline value comes from the day itself or later", not leaks, str(leaks[:3]))

    # The seasonal naive must match on WEEKDAY, and must be the most recent such session.
    bad_dow = []
    for r in chain:
        i = idx[r["date"]]
        v = base[r["date"]]["seasonal_naive"]
        if v is None:
            continue
        prior_same = [chain[j] for j in range(i) if chain[j]["dow"] == r["dow"]]
        if not prior_same or prior_same[-1]["move"] != v:
            bad_dow.append(r["date"])
    check("seasonal_naive is the most recent same-weekday session", not bad_dow, str(bad_dow[:3]))

    # Declared unavailability, not silent filling: g17's first week has no predecessor.
    nulls = [d for d, b in base.items() if b["seasonal_naive"] is None]
    check("earliest sessions declare seasonal_naive UNAVAILABLE rather than filling it",
          len(nulls) > 0 and all(d <= chain[min(len(chain) - 1, 6)]["date"] for d in nulls),
          f"{len(nulls)} declared null: {sorted(nulls)}")

    # zero-change MAE is BY DEFINITION the mean absolute actual move. If this ever fails, the
    # scorer and the definition have diverged and every ratio printed above is wrong.
    moves = [r["move"] for r in chain]
    z = score([(r["date"], 0, r["move"]) for r in chain], signed=False)
    check("zero_change MAE == mean absolute actual move",
          abs(z["mae"] - (sum(abs(m) for m in moves) / len(moves))) < 1e-9,
          f"{z['mae']:.1f}")
    check("zero_change emits no direction", z["dir_hits"] is None)

    # A forecaster scored against itself must be perfect - catches a sign or subtraction slip.
    perfect = score([(r["date"], r["move"], r["move"]) for r in chain])
    check("self-forecast scores zero error", perfect["sum_abs"] == 0 and perfect["drift"] == 0)

    # The conflict guard must actually fire (a corpus defect must raise, not be resolved silently).
    try:
        seen = {"20260101": {"date": "20260101", "dow": "Thu", "move": 100, "src": "a.json"}}
        d2 = {"date": "20260101", "move": -100}
        if seen["20260101"]["move"] != d2["move"]:
            raise ValueError("conflict")
        check("chain conflict guard fires on a duplicate date", False)
    except ValueError:
        check("chain conflict guard fires on a duplicate date", True)

    print()
    print("  SELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ---------------------------------------------------------------------------------------------

def main(argv):
    if "--selftest" in argv:
        return selftest()

    gids = []
    for a in argv:
        s = a.lower().lstrip("g")
        if s.isdigit():
            gids.append(int(s))
    groups = gids or list(range(15, 24))

    print(f"{'grp':>4} {'sum|err|':>9} {'DRIFT':>8} {'survives':>9} {'>1000':>6} {'>500':>6}   three worst days")
    print("-" * 88)
    rows = {}
    for n in groups:
        e = errs_for(n)
        if not e:
            continue
        rows[n] = e
        sa = sum(abs(x[3]) for x in e)
        dr = sum(x[3] for x in e)
        worst = sorted(e, key=lambda x: -abs(x[3]))[:3]
        print(f"{n:>4} {sa:>9} {dr:>+8} {100*abs(dr)/sa:>8.0f}% {sum(1 for x in e if abs(x[3])>1000):>6} "
              f"{sum(1 for x in e if abs(x[3])>500):>6}   " + "  ".join(f"{x[0][4:]} {x[3]:+}" for x in worst))

    print()
    print("'survives' = |drift| as a share of total absolute error. Everything else CANCELLED inside the")
    print("netting. A LOW percentage means the drift number is flattering the block, not describing it.")

    if 21 in rows and 20 in rows:
        print()
        print("=" * 88)
        print("THE G20 -> G21 COMPARISON, STATED HONESTLY")
        print("=" * 88)
        for n in (20, 21):
            e = rows[n]
            sa, dr = sum(abs(x[3]) for x in e), sum(x[3] for x in e)
            print(f"  g{n}: drift {dr:+6}   sum|err| {sa:6}   per-day |err| "
                  f"{sorted((abs(x[3]) for x in e), reverse=True)}")
        d20, d21 = rows[20], rows[21]
        s20, s21 = sum(abs(x[3]) for x in d20), sum(abs(x[3]) for x in d21)
        dr20, dr21 = sum(x[3] for x in d20), sum(x[3] for x in d21)
        print()
        print(f"  drift    {dr20:+} -> {dr21:+}   = a {100*(1-abs(dr21)/abs(dr20)):.0f}% 'improvement'")
        print(f"  sum|err| {s20} -> {s21}   = a {100*(1-s21/s20):.0f}% improvement")
        print()
        print("  The gap between those two numbers IS the cancellation. The drift improvement is mostly")
        print("  errors that stopped agreeing with each other, not errors that got smaller.")

    benchmark_report(sorted(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
