"""gefs_ensemble.py - the GEFS ensemble through OUR gas-weighted degree days, to a DENSITY. (G-5.)

THE ASK (registry G-5, BIGGEST_WIN, open since S111): "ECMWF ENS + GEFS members through our own
GWDD weighting -> a DENSITY". Greg, S114: "We have to build g5 then before we run."

WHY A DENSITY AND NOT A NUMBER. Everything upstream of this serves ONE weather number per day
(`gw_hdd`, `gw_cdd`) and a specialist cannot tell a confident 12 GWDD from a coin-flip 12 GWDD.
The whole S111 finding that we cannot measure skill until the system can DECLINE needs a width to
decline on, and the options lane wants a distribution over trajectories rather than a p50. Thirty-one
members re-weighted through the same station weights give exactly that width, in the same units as
the number the plays already read.

THE ONE PROPERTY THAT MAKES IT COMPARABLE, and it is why this module imports rather than copies:
the members go through `nws_temp_feed.station_weights()` and `nws_temp_feed.degree_days()`
THEMSELVES. If the weighting were re-implemented here, the density and the realized value would be
on subtly different scales and every spread would be part real, part artifact. Identical by
construction, not by inspection.

RETRIEVAL. Bucket `noaa-gefs-pds`, UNSIGNED - no credentials, no cost. The `.idx` sidecar gives byte
offsets per message, so we HTTP-Range only the `TMP:2 m above ground` record (~440 KB) instead of
the whole file. The code shape came from CHATGPT_S112_SIX_WORKSTREAMS.md (Greg: "Chat gave you path
code in the paper"); the vintage rule, the weighting and the gas-day boundary are ours.

MEASURED S114 before building: the archive is NOT recent-days-only. 2026 retains 217 days
(20260101..20260805) and every G24 date is present. THE TRAP - a plain list_objects_v2 with
MaxKeys=1000 returns 20170101..20190927 and reads like a dead 2019 archive, because the listing is
alphabetical and truncates. Probe exact dates, never the listing.

THE VINTAGE RULE IS THE WHOLE BLIND-LEGALITY ARGUMENT. A gas session labelled day D opens at 20:00
ET on D-1. We use the **12Z cycle of D-1**, which publishes around 17Z (12:00 ET on D-1) - roughly
eight hours before the reopen, and a full cycle more conservative than the 18Z that would also
qualify. Every emitted record carries `cycle_utc` and `knowable_from` so the claim is auditable
rather than asserted, which is the S97 lesson about the COT publication gap.

STATION COORDINATES ARE SOURCED, NOT REMEMBERED - fetched from the IEM network metadata, the same
provider the realized feed reads, and cached with provenance. A hand-typed airport latitude is
exactly the class of fact that is wrong 1 time in 16 and never noticed.

    python gefs_ensemble.py probe --date 20260719
    python gefs_ensemble.py density --day 20260720 --members 5
    python gefs_ensemble.py selftest
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys
import tempfile
from zoneinfo import ZoneInfo

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nws_temp_feed as ntf  # noqa: E402  - the SAME weighting and degree-day math, imported

BASE = "https://noaa-gefs-pds.s3.amazonaws.com"
PRODUCT = "pgrb2sp25"                      # 0.25 deg surface set; carries TMP 2 m
NEEDLE = ":TMP:2 m above ground:"
COORDS_FILE = os.path.join(HERE, "store", "station_coords.json")
GAS_TZ = ntf.REF_TZ                        # America/Chicago - the same gas-day boundary
MEMBERS = ["gec00"] + ["gep%02d" % i for i in range(1, 31)]   # control + 30 perturbed


# ---------------------------------------------------------------------------------------------
# station coordinates - sourced from IEM, cached, provenance kept
# ---------------------------------------------------------------------------------------------
IEM_NETWORKS = ("NY_ASOS", "MA_ASOS", "PA_ASOS", "VA_ASOS", "IL_ASOS", "MI_ASOS", "MN_ASOS",
                "MO_ASOS", "TX_ASOS", "GA_ASOS", "CO_ASOS", "AZ_ASOS", "CA_ASOS", "WA_ASOS")


def fetch_coords(write=False):
    want = set(ntf.STATION_WEIGHTS_RAW)
    out = {}
    for netw in IEM_NETWORKS:
        try:
            r = requests.get("https://mesonet.agron.iastate.edu/geojson/network/%s.geojson" % netw,
                             timeout=60)
            for f in r.json().get("features", []):
                sid = f["id"]
                if sid in want and sid not in out:
                    lon, lat = f["geometry"]["coordinates"]
                    out[sid] = {"lat": round(lat, 4), "lon": round(lon, 4),
                                "name": f["properties"].get("sname"), "source_network": netw}
        except Exception:
            continue
    missing = sorted(want - set(out))
    if missing:
        raise SystemExit("gefs: could not resolve coordinates for %s - refusing to guess them, "
                         "because a hand-typed latitude is wrong once in sixteen and never "
                         "noticed" % missing)
    if write:
        os.makedirs(os.path.dirname(COORDS_FILE), exist_ok=True)
        with open(COORDS_FILE, "w", encoding="utf-8") as f:
            json.dump({"note": "Station coordinates for the gas-weighted degree-day stations, "
                               "fetched from the IEM network metadata - the SAME provider the "
                               "realized feed reads. Regenerate with "
                               "`gefs_ensemble.py coords --write`.",
                       "fetched_for_stations": sorted(want),
                       "stations": out}, f, indent=1, ensure_ascii=False)
    return out


def coords():
    if os.path.exists(COORDS_FILE):
        with open(COORDS_FILE, encoding="utf-8") as f:
            return json.load(f)["stations"]
    return fetch_coords(write=True)


# ---------------------------------------------------------------------------------------------
# the vintage rule
# ---------------------------------------------------------------------------------------------
def cycle_for(day, cycle_hour=12):
    """-> (cycle_date_YYYYMMDD, cycle_hh, knowable_from_iso) for a gas session labelled `day`.

    The session opens 20:00 ET on day-1, so the D-1 12Z cycle (published ~17Z = 12:00 ET on D-1) is
    available roughly eight hours before the decision point. Returned rather than assumed so the
    caller can record it; the emitted record carries it, so 'this was knowable' is auditable
    instead of asserted.
    """
    d = dt.datetime.strptime(day, "%Y%m%d").date()
    c = d - dt.timedelta(days=1)
    # publication latency for GEFS is ~4-5h; 5h is the conservative side
    known = dt.datetime.combine(c, dt.time(cycle_hour), tzinfo=dt.timezone.utc) + dt.timedelta(hours=5)
    return c.strftime("%Y%m%d"), "%02d" % cycle_hour, known.isoformat()


def target_fhrs(day, cycle_date, cycle_hour, step=3):
    """Forecast hours covering the CHICAGO gas day `day`, measured from the cycle.

    The realized index buckets hourly observations on the America/Chicago day, so the ensemble has
    to be sampled on that same boundary or the two are not the same quantity.
    """
    d = dt.datetime.strptime(day, "%Y%m%d").date()
    start_local = dt.datetime.combine(d, dt.time(0), tzinfo=GAS_TZ)
    end_local = start_local + dt.timedelta(days=1)
    c0 = dt.datetime.combine(dt.datetime.strptime(cycle_date, "%Y%m%d").date(),
                             dt.time(int(cycle_hour)), tzinfo=dt.timezone.utc)
    lo = int((start_local.astimezone(dt.timezone.utc) - c0).total_seconds() // 3600)
    hi = int((end_local.astimezone(dt.timezone.utc) - c0).total_seconds() // 3600)
    lo = lo - (lo % step)
    return list(range(max(lo, 0), hi + 1, step))


# ---------------------------------------------------------------------------------------------
# retrieval + decode
# ---------------------------------------------------------------------------------------------
def _key(cycle_date, cycle_hour, member, fhr):
    stem = "%s.t%sz.pgrb2s.0p25.f%03d" % (member, cycle_hour, fhr)
    return "gefs.%s/%s/atmos/%s/%s" % (cycle_date, cycle_hour, PRODUCT, stem)


def station_temps_f(cycle_date, cycle_hour, member, fhr, pts, session=None):
    """-> {station: temp_F} for one member at one forecast hour, or None if the message is absent.

    Absent is returned, never faked. A missing member at one hour must show up as a smaller
    ensemble with a declared count, not as a silently interpolated value - the whole point of the
    density is that its width is real.
    """
    import eccodes
    s = session or requests
    key = _key(cycle_date, cycle_hour, member, fhr)
    ir = s.get("%s/%s.idx" % (BASE, key), timeout=60)
    if ir.status_code != 200:
        return None
    rows = []
    for line in ir.text.strip().splitlines():
        p = line.split(":", 3)
        rows.append((int(p[1]), line))
    span = None
    for j, (start, line) in enumerate(rows):
        if NEEDLE in line:
            end = rows[j + 1][0] - 1 if j + 1 < len(rows) else ""
            span = (start, end)
            break
    if span is None:
        return None
    r = s.get("%s/%s" % (BASE, key), headers={"Range": "bytes=%s-%s" % span}, timeout=180)
    if r.status_code not in (200, 206):
        return None
    fp = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
    try:
        fp.write(r.content)
        fp.close()
        out = {}
        with open(fp.name, "rb") as fh:
            gid = eccodes.codes_grib_new_from_file(fh)
            if gid is None:
                return None
            for st, c in pts.items():
                n = eccodes.codes_grib_find_nearest(gid, c["lat"], c["lon"])[0]
                out[st] = (n.value - 273.15) * 9.0 / 5.0 + 32.0
            eccodes.codes_release(gid)
        return out
    finally:
        try:
            os.unlink(fp.name)
        except OSError:
            pass


def member_gwdd(day, member, cycle_date, cycle_hour, pts, session=None):
    """One member -> its gas-weighted (gw_hdd, gw_cdd) for `day`, or None if under-covered.

    Daily mean per station across the gas day, then OUR weights. A member covering fewer than 6 of
    the ~9 three-hourly slots is dropped rather than extrapolated, and the drop is counted.
    """
    fhrs = target_fhrs(day, cycle_date, cycle_hour)
    acc = {st: [] for st in pts}
    for fhr in fhrs:
        t = station_temps_f(cycle_date, cycle_hour, member, fhr, pts, session)
        if t is None:
            continue
        for st, v in t.items():
            acc[st].append(v)
    n = min(len(v) for v in acc.values()) if acc else 0
    if n < 6:
        return None
    w = ntf.station_weights()
    wsum = sum(w[st] for st in acc)
    hdd = cdd = 0.0
    for st, vals in acc.items():
        # Tmean = (Tmax + Tmin)/2, THE SAME ESTIMATOR the realized feed uses (nws_temp_feed
        # .daily_from_obs: "Tmean = (Tmax+Tmin)/2 (the degree-day convention)"). Getting this wrong
        # is not cosmetic and it was caught by validating against realized rather than by reading
        # the output: an ARITHMETIC MEAN of the 3-hourly values put the whole 6-member density
        # ABOVE the realized 20260720 gw_cdd of 13.331 - ensemble minimum 13.934 - because a real
        # diurnal curve is asymmetric (fast morning warming, long warm afternoon, slow overnight
        # cooling) so its arithmetic mean exceeds its midrange in summer. Importing the WEIGHTS and
        # the degree-day math was not enough; the daily-mean step is part of the same scale.
        h, c = ntf.degree_days((max(vals) + min(vals)) / 2.0)
        hdd += w[st] * h
        cdd += w[st] * c
    return round(hdd / wsum, 3), round(cdd / wsum, 3), n


def density(day, members=None, cycle_hour=12, verbose=True):
    """-> the record: per-member GWDD plus the distribution, with the vintage declared."""
    pts = coords()
    cycle_date, ch, known = cycle_for(day, cycle_hour)
    mems = members or MEMBERS
    s = requests.Session()
    rows, dropped = [], []
    for m in mems:
        r = member_gwdd(day, m, cycle_date, ch, pts, s)
        if r is None:
            dropped.append(m)
            if verbose:
                print("  %-6s DROPPED (under-covered)" % m)
            continue
        hdd, cdd, n = r
        rows.append({"member": m, "gw_hdd": hdd, "gw_cdd": cdd, "slots": n})
        if verbose:
            print("  %-6s gw_hdd %6.3f  gw_cdd %6.3f  (%d slots)" % (m, hdd, cdd, n))
    if not rows:
        raise SystemExit("gefs: no member produced a value for %s - refusing to emit an empty "
                         "density, which would read downstream exactly like a narrow one" % day)

    def dist(field):
        v = sorted(r[field] for r in rows)
        q = lambda p: v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]  # noqa: E731
        return {"n": len(v), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90),
                "min": v[0], "max": v[-1], "spread_p90_p10": round(q(0.90) - q(0.10), 3),
                "stdev": round(statistics.pstdev(v), 3) if len(v) > 1 else 0.0}
    return {
        "day": day, "product": PRODUCT,
        "cycle_utc": "%sT%s:00:00Z" % (dt.datetime.strptime(cycle_date, "%Y%m%d").date(), ch),
        "knowable_from": known,
        "vintage_rule": ("the D-1 %sZ cycle, published ~5h later, against a 20:00 ET reopen on D-1. "
                         "Blind-legal by publication time, and recorded here so the claim is "
                         "auditable rather than asserted." % ch),
        "weighting": "nws_temp_feed.station_weights() and degree_days(), IMPORTED not reimplemented",
        "daily_mean_estimator": ("(Tmax+Tmin)/2 over the gas day - the SAME estimator as the "
                                 "realized feed. SAMPLING CAVEAT, declared: realized extremes come "
                                 "from HOURLY obs, ours from 3-HOURLY model steps, so our range is "
                                 "slightly compressed and the density is marginally narrow at the "
                                 "tails. Declared rather than corrected, because a fudge factor "
                                 "would be a fitted constant."),
        "gas_day_boundary": str(GAS_TZ),
        "members_requested": len(mems), "members_used": len(rows), "members_dropped": dropped,
        "gw_hdd": dist("gw_hdd"), "gw_cdd": dist("gw_cdd"),
        "members": rows,
    }


def cmd_probe(date):
    """Is this cycle actually retrievable? Probe exact keys, never a truncated listing."""
    pts = coords()
    cd, ch, known = cycle_for(date)
    print("day %s -> cycle %s %sZ (knowable from %s)" % (date, cd, ch, known))
    print("target fhrs (Chicago gas day):", target_fhrs(date, cd, ch))
    t = station_temps_f(cd, ch, "gec00", target_fhrs(date, cd, ch)[0], pts)
    if t is None:
        print("  control member NOT retrievable for that cycle/hour")
        return 1
    for st in sorted(t):
        print("  %-4s %6.1f F" % (st, t[st]))
    return 0


def cmd_selftest():
    fails = []

    def check(name, cond, detail=""):
        print("  %-58s %s%s" % (name, "PASS" if cond else "FAIL", ("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    print("gefs_ensemble selftest")
    pts = coords()
    check("all 16 weighted stations have coordinates",
          set(pts) == set(ntf.STATION_WEIGHTS_RAW), "%d resolved" % len(pts))
    check("coordinates are plausible US lat/lon",
          all(24 < c["lat"] < 50 and -125 < c["lon"] < -66 for c in pts.values()))

    cd, ch, known = cycle_for("20260720")
    check("vintage: day D uses the D-1 cycle", cd == "20260719", "%s %sZ" % (cd, ch))
    check("vintage: knowable_from precedes the 20:00 ET D-1 reopen",
          dt.datetime.fromisoformat(known) <
          dt.datetime(2026, 7, 20, 0, 0, tzinfo=dt.timezone.utc), known)

    fh = target_fhrs("20260720", cd, ch)
    check("fhrs cover a full 24h gas day", fh[-1] - fh[0] >= 24, "f%03d..f%03d" % (fh[0], fh[-1]))
    check("fhrs are 3-hourly", all(b - a == 3 for a, b in zip(fh, fh[1:])))

    # the weighting must be the imported one, not a copy
    w = ntf.station_weights()
    check("weights sum to 1 and come from nws_temp_feed",
          abs(sum(w.values()) - 1.0) < 1e-9 and set(w) == set(pts))
    h, c = ntf.degree_days(75.0)
    check("degree_days is the imported base-65 math", (h, c) == (0.0, 10.0), "75F -> %s/%s" % (h, c))

    # NEGATIVE: an absent message returns None rather than a fabricated temperature
    bad = station_temps_f("19000101", "12", "gep01", 24, pts)
    print("     guard output: absent cycle -> %r" % bad)
    check("NEGATIVE an absent message returns None, never a value", bad is None)

    print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % fails))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coords").add_argument("--write", action="store_true")
    p = sub.add_parser("probe"); p.add_argument("--date", required=True)
    d = sub.add_parser("density")
    d.add_argument("--day", required=True)
    d.add_argument("--members", type=int, default=0, help="first N members (0 = all 31)")
    d.add_argument("--out", default="")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.cmd == "coords":
        fetch_coords(write=a.write)
        print("coords written" if a.write else "coords resolved (dry run)")
        return 0
    if a.cmd == "probe":
        return cmd_probe(a.date)
    rec = density(a.day, MEMBERS[:a.members] if a.members else None)
    print(json.dumps({k: v for k, v in rec.items() if k != "members"}, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        print("written ->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
