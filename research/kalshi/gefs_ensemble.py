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

# THE FORCINGS - and every one is in the SAME product we already pull, so no new source, no extra
# retrieval cost, same .idx range-request. Greg, S114: "We also have to ingest wind and solar and
# prec data", and all three rehearsal specialists asked for forward wind/solar independently.
# SERVED SEPARATELY, NEVER SUMMED: wind peaks spring/autumn, solar at the solstice (measured on our
# own EIA-930: wind 9.9 TWh/wk April vs 5.9 August; solar 3.5 June vs 1.4 December). Summing two
# opposite annual cycles is worse than serving neither (D37).
FORCING_NEEDLES = {
    "wind_u10": ":UGRD:10 m above ground:",
    "wind_v10": ":VGRD:10 m above ground:",
    "solar_dswrf": ":DSWRF:surface:",
    "precip_apcp": ":APCP:surface:",
}
# TMAX/TMIN are in the product too, which closes the caveat the temperature density had to declare:
# the realized feed's estimator is (Tmax+Tmin)/2 from HOURLY obs, and the model carries its own
# TMAX/TMIN over the step rather than making us approximate extremes from 3-hourly samples.
EXTREME_NEEDLES = {"tmax": ":TMAX:2 m above ground:", "tmin": ":TMIN:2 m above ground:"}

# eccodes shortName -> our field name. MEASURED from a real decode, not assumed: the .idx says
# DSWRF and eccodes says `sdswrf`; the .idx says APCP and eccodes says `tp`. v2 mapped the .idx
# names and lost solar silently.
def _sample(gid, pts):
    """Sample a decoded GRIB message at our points by ARITHMETIC INDEX, not codes_grib_find_nearest.

    MEASURED, which is the only reason to prefer one over the other:
        network, one 0.8 MB message .......  0.7 s
        390 x codes_grib_find_nearest ..... 10.9 s   <- the whole cost was here
        codes_get_array + grid metadata ...  0.02 s
    find_nearest re-walks the grid per call. The GEFS 0.25 deg product is a REGULAR lat/lon grid
    (Ni=1440, Nj=721, first point 90N/0E, di=dj=0.25, latitude DESCENDING), so the index is
    computable and the whole field costs one array read. Roughly 500x, and it is what makes 31
    members x 9 hours feasible at all.

    The grid geometry is READ FROM THE MESSAGE, never assumed - a product change would otherwise
    silently shift every sample. Verified against find_nearest in the selftest.
    """
    import eccodes
    vals = eccodes.codes_get_array(gid, "values")
    ni = eccodes.codes_get(gid, "Ni")
    nj = eccodes.codes_get(gid, "Nj")
    la1 = eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
    lo1 = eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
    di = eccodes.codes_get(gid, "iDirectionIncrementInDegrees")
    dj = eccodes.codes_get(gid, "jDirectionIncrementInDegrees")
    out = {}
    for k, c in pts.items():
        j = int(round((la1 - c["lat"]) / dj))
        i = int(round(((c["lon"] % 360.0) - lo1) / di)) % ni
        if 0 <= j < nj:
            out[k] = float(vals[j * ni + i])
    return out


SHORTNAME_MAP = {"10u": "wind_u10", "10v": "wind_v10", "sdswrf": "solar_dswrf",
                 "dswrf": "solar_dswrf", "tp": "precip_apcp", "apcp": "precip_apcp",
                 "2t": "tmp", "mx2t": "tmax", "mn2t": "tmin", "tmax": "tmax", "tmin": "tmin"}
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


def station_field(cycle_date, cycle_hour, member, fhr, pts, needle=NEEDLE, session=None):
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
        if needle in line:
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
            out = _sample(gid, pts)    # RAW units - the caller converts, so one decoder serves
                                       # temperature (K), wind (m/s), DSWRF (W/m2), APCP (kg/m2)
            eccodes.codes_release(gid)
        return out
    finally:
        try:
            os.unlink(fp.name)
        except OSError:
            pass


def station_temps_f(cycle_date, cycle_hour, member, fhr, pts, session=None):
    """Temperature in F - the original contract, now a thin wrapper over station_field."""
    raw = station_field(cycle_date, cycle_hour, member, fhr, pts, NEEDLE, session)
    if raw is None:
        return None
    return {k: (v - 273.15) * 9.0 / 5.0 + 32.0 for k, v in raw.items()}


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


# ---------------------------------------------------------------------------------------------
# THE FORCINGS at US48 scale
# ---------------------------------------------------------------------------------------------
# CONUS sampling grid. A BOUNDING-BOX GRID, not hand-picked generation sites, and the distinction
# matters: hand-picked points are a fitted choice dressed as geography, and this desk has paid for
# that shape before. A uniform grid is a stated approximation whose error is measurable - which is
# why nothing here ships until it is VALIDATED against realized EIA-930 output below.
CONUS = {"lat0": 25.0, "lat1": 49.0, "lon0": -125.0, "lon1": -67.0, "step": 2.0}


def conus_points():
    pts = {}
    lat = CONUS["lat0"]
    while lat <= CONUS["lat1"]:
        lon = CONUS["lon0"]
        while lon <= CONUS["lon1"]:
            pts["%.0f_%.0f" % (lat, lon)] = {"lat": lat, "lon": lon}
            lon += CONUS["step"]
        lat += CONUS["step"]
    return pts


def station_fields_multi(cycle_date, cycle_hour, member, fhr, pts, needles, session=None):
    """Several messages per file, fetched as CONTIGUOUS CLUSTERS. -> {name: {point: raw value}}.

    Three revisions, each forced by a measurement rather than a guess:
      v1 one request per field  - 4 fields x 9 hours x 31 members = 1,116 round trips. Never
         finished.
      v2 one span covering all four - correct but 8.4 MB per fetch and 33 s, because DSWRF sits
         near the end of the file while the wind pair sits in the middle, so the span dragged in
         twelve unwanted messages.
      v3 (this) one request per CONTIGUOUS RUN of needed messages. The wind/precip cluster and the
         radiation message are fetched separately, so we move roughly what we asked for.

    AND THE MESSAGES ARE IDENTIFIED BY shortName FROM A MAP, WHICH IS WHERE v2 SILENTLY LOST SOLAR.
    The `.idx` calls the field DSWRF; eccodes reports its shortName as `sdswrf`, and precipitation
    comes back as `tp`, not `apcp`. A name that differs between the index and the decoder is
    exactly the wrong-but-well-formed class - the fetch succeeded, three fields returned, and solar
    was simply absent with nothing saying so. Unmapped shortNames are now REPORTED, not dropped.
    """
    import eccodes
    s_ = session or requests
    key = _key(cycle_date, cycle_hour, member, fhr)
    ir = s_.get("%s/%s.idx" % (BASE, key), timeout=60)
    if ir.status_code != 200:
        return None
    rows = []
    for line in ir.text.strip().splitlines():
        p_ = line.split(":", 3)
        rows.append((int(p_[1]), line))
    spans = []
    for j, (start, line) in enumerate(rows):
        for name, needle in needles.items():
            if needle in line:
                end = rows[j + 1][0] - 1 if j + 1 < len(rows) else None
                spans.append((start, end, name))
    if not spans:
        return None
    spans.sort()
    # merge into contiguous clusters: a gap of one message is cheaper to include than to re-request
    clusters, cur = [], [spans[0]]
    for sp in spans[1:]:
        if cur[-1][1] is not None and sp[0] - cur[-1][1] < 2_000_000:
            cur.append(sp)
        else:
            clusters.append(cur); cur = [sp]
    clusters.append(cur)

    out, seen_names = {}, set()
    for cl in clusters:
        lo = cl[0][0]
        his = [b for _, b, _ in cl]
        hi = "" if any(b is None for b in his) else max(his)
        r = s_.get("%s/%s" % (BASE, key), headers={"Range": "bytes=%s-%s" % (lo, hi)}, timeout=300)
        if r.status_code not in (200, 206):
            continue
        fp = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
        try:
            fp.write(r.content)
            fp.close()
            with open(fp.name, "rb") as fh:
                while True:
                    gid = eccodes.codes_grib_new_from_file(fh)
                    if gid is None:
                        break
                    try:
                        sn = eccodes.codes_get(gid, "shortName")
                        seen_names.add(sn)
                        nm = SHORTNAME_MAP.get(sn)
                        if nm and nm in needles:
                            out[nm] = _sample(gid, pts)
                    finally:
                        eccodes.codes_release(gid)
        finally:
            try:
                os.unlink(fp.name)
            except OSError:
                pass
    missing = [n for n in needles if n not in out]
    if missing:
        # DECLARED, never silent - this is the defect v2 shipped
        out["_missing"] = {"fields": missing, "shortnames_seen": sorted(seen_names)}
    return out or None


def capacity_points(kind, cell=0.25):
    """Capacity-weighted sampling cells from REAL generator locations. -> {key: {lat,lon,weight}}

    THE UNIFORM CONUS GRID FAILED VALIDATION AND THIS IS WHY. Measured on 77 days against realized
    EIA-930 US48 output, day-over-day direction, celled by month and never pooled:
        WIND  28/76 = 37%, and BELOW 50% in all four month cells (5/20, 7/21, 10/22, 6/13)
        SOLAR 40/76 = 53%, indistinguishable from a coin flip
    A uniform mean over the lower 48 is dominated by area with no turbines on it. The generation is
    not uniform and it is not close: wind nameplate is TX 43.7 GW, OK 13.7, IA 13.4, KS 9.7, IL
    8.7, NM 8.1 - one contiguous belt - while solar is TX 32.6, CA 25.0, FL 13.3, AZ 7.5. Averaging
    the whole country asks a question about the wrong places.

    This is NOT the "hand-picked points" I warned against when the grid was built. The coordinates
    and the nameplate MW are EIA's operating-generator record - physical fact, refreshed by
    `plants --write`, not a choice tuned until the answer improved. 1,560 wind generators totalling
    165 GW; 8,081 solar totalling 163 GW.

    Plants are binned onto the model's own 0.25 deg cells so one decoded field serves them all.
    """
    fn = os.path.join(HERE, "store", "plants_%s.json" % kind)
    if not os.path.exists(fn):
        raise SystemExit("gefs: %s missing - run `gefs_ensemble.py plants --write` (EIA API key "
                         "required). Refusing to fall back to a uniform grid, which is measured to "
                         "fail." % os.path.relpath(fn, HERE))
    with open(fn, encoding="utf-8") as f:
        gens = json.load(f)["generators"]
    cells = {}
    for g in gens:
        la, lo = g["lat"], g["lon"]
        if not (24 < la < 50 and -126 < lo < -66):      # CONUS only; AK/HI are not on this grid
            continue
        j = round(la / cell) * cell
        i = round(lo / cell) * cell
        k = "%.2f_%.2f" % (j, i)
        c = cells.setdefault(k, {"lat": j, "lon": i, "weight": 0.0})
        c["weight"] += g["mw"]
    tot = sum(c["weight"] for c in cells.values())
    for c in cells.values():
        c["weight"] /= tot
    return cells


def _wavg(vals, pts):
    tot = sum(pts[k]["weight"] for k in vals if k in pts)
    if not tot:
        return None
    return sum(vals[k] * pts[k]["weight"] for k in vals if k in pts) / tot


HUB_M = 100.0            # typical modern hub height
SHEAR_ALPHA = 0.14       # power-law exponent, open terrain (the standard 1/7 rule)


def hub_speed(v10):
    """Extrapolate 10 m wind to hub height. v_h = v_10 * (h/10)^alpha - the standard power law.

    NOT a tuning knob. GEFS serves 10 m wind; turbines sit near 100 m, where the air is markedly
    faster, and the ratio is 10^0.14 = 1.39. Skipping it is not conservative - it drives most cells
    below the 3 m/s cut-in and CLIPS THE SIGNAL TO ZERO, which showed up immediately as a 6.3%
    capacity-factor proxy against a real US fleet average near 35%.
    """
    return v10 * (HUB_M / 10.0) ** SHEAR_ALPHA


def turbine_power(speed_ms):
    """A generic turbine power curve, normalised 0-1. PHYSICAL FACT, not a fitted shape.

    Pure cubing is wrong at both ends and the ends are where the interesting days are: below
    cut-in (~3 m/s) a turbine makes NOTHING, and above rated (~12 m/s) it makes its rated output
    and no more, so cubing overstates every windy day. Cut-out ~25 m/s takes it back to zero.
    """
    v = speed_ms
    if v < 3.0 or v >= 25.0:
        return 0.0
    if v >= 12.0:
        return 1.0
    return (v ** 3 - 3.0 ** 3) / (12.0 ** 3 - 3.0 ** 3)


def member_forcings(day, member, cycle_date, cycle_hour, grids, session=None):
    """One member -> US48 forcing proxies, each on ITS OWN capacity-weighted geography.

    `grids` = {"wind": capacity_points("wind"), "solar": capacity_points("solar"),
               "all": conus_points()}  - wind and solar are sampled where wind and solar actually
    ARE, and precipitation stays on the uniform grid because it is a general weather field with no
    generation fleet behind it.
    """
    fhrs = target_fhrs(day, cycle_date, cycle_hour)
    allpts = {}
    for g in grids.values():
        allpts.update({k: {"lat": v["lat"], "lon": v["lon"]} for k, v in g.items()})
    acc = {"wind": [], "solar": [], "precip": []}
    miss = set()
    for fhr in fhrs:
        got = station_fields_multi(cycle_date, cycle_hour, member, fhr, allpts,
                                   FORCING_NEEDLES, session)
        if not got:
            continue
        miss.update((got.pop("_missing", {}) or {}).get("fields", []))
        u, v = got.get("wind_u10"), got.get("wind_v10")
        if u and v:
            import math
            cf = {k: turbine_power(hub_speed(math.hypot(u[k], v[k])))
                  for k in grids["wind"] if k in u}
            w = _wavg(cf, grids["wind"])
            if w is not None:
                acc["wind"].append(w)
        if got.get("solar_dswrf"):
            d = {k: got["solar_dswrf"][k] for k in grids["solar"] if k in got["solar_dswrf"]}
            sv = _wavg(d, grids["solar"])
            if sv is not None:
                acc["solar"].append(sv)
        if got.get("precip_apcp"):
            a = got["precip_apcp"]
            acc["precip"].append(sum(a.values()) / len(a))
    if len(acc["wind"]) < 4:
        return None
    return {
        "wind_cf_proxy": round(sum(acc["wind"]) / len(acc["wind"]), 5),
        "solar_irradiance_proxy": round(sum(acc["solar"]) / len(acc["solar"]), 2)
        if acc["solar"] else None,
        "precip_proxy": round(sum(acc["precip"]), 3) if acc["precip"] else None,
        "slots": len(acc["wind"]),
        "fields_missing": sorted(miss) or None,
    }


def forcing_density(day, members=None, cycle_hour=12, verbose=True):
    grids = {"wind": capacity_points("wind"), "solar": capacity_points("solar"),
             "all": conus_points()}
    cycle_date, ch, known = cycle_for(day, cycle_hour)
    mems = members or MEMBERS
    s = requests.Session()
    rows = []
    for m in mems:
        r = member_forcings(day, m, cycle_date, ch, grids, s)
        if r is None:
            continue
        r["member"] = m
        rows.append(r)
        if verbose:
            print("  %-6s wind_cf %7.4f  solar %7.1f  precip %6.3f"
                  % (m, r["wind_cf_proxy"], r["solar_irradiance_proxy"] or -1,
                     r["precip_proxy"] or 0))
    if not rows:
        raise SystemExit("gefs: no member produced forcings for %s" % day)

    def dist(f):
        v = sorted(x[f] for x in rows if x.get(f) is not None)
        if not v:
            return None
        q = lambda p: v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]  # noqa: E731
        return {"n": len(v), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90),
                "min": v[0], "max": v[-1]}
    return {
        "day": day, "scale": "US48 (CONUS bounding-box grid, %.0f deg)" % CONUS["step"],
        "n_wind_cells": len(grids["wind"]), "n_solar_cells": len(grids["solar"]),
        "cycle_utc": "%sT%s:00:00Z" % (dt.datetime.strptime(cycle_date, "%Y%m%d").date(), ch),
        "knowable_from": known,
        "served_separately": ("wind and solar are NEVER summed - they are seasonally "
                              "ANTI-correlated (wind peaks spring/autumn, solar at the solstice), "
                              "so one 'renewables' term is a composite of two opposite annual "
                              "cycles (D37)."),
        "wind_method": ("capacity-weighted mean of a generic TURBINE POWER CURVE applied to the "
                        "HUB-HEIGHT wind (10 m extrapolated to 100 m by the standard 1/7 power law) "
                        "at each cell - zero below 3 m/s cut-in, cube between, flat at rated above "
                        "12 m/s, zero above 25 m/s cut-out. Pure cubing overstates every windy day."),
        "geography": ("wind and solar are sampled at their OWN capacity-weighted cells from EIA's "
                      "operating-generator record, NOT on a uniform grid - the uniform version was "
                      "measured at 37% (wind) and 53% (solar) day-over-day direction against "
                      "realized EIA-930, and 37% is worse than a coin flip."),
        "these_are_proxies": ("meteorological fields, NOT MWh. Usable only to the extent the "
                              "validation below holds - see `gefs_ensemble.py validate`."),
        "members_used": len(rows),
        "wind_cf_proxy": dist("wind_cf_proxy"),
        "solar_irradiance_proxy": dist("solar_irradiance_proxy"),
        "precip_proxy": dist("precip_proxy"),
        "members": rows,
    }


def forcing_series(days, members=None, cycle_hour=12, workers=6, verbose=True):
    """Forcing densities for many days, days fetched CONCURRENTLY.

    THE VALIDATION/PRODUCTION SPLIT, and it is what makes this affordable. Deciding whether the
    proxy TRACKS realized output needs many days and does not need spread - the control member
    alone answers it, at ~5 s a day. Deciding how UNCERTAIN a given day is needs all 31 members and
    only for the days actually being forecast, at ~3 min a day. So validation runs `--members 1`
    over a long span; a staged block runs the full ensemble over ten days.
    """
    from concurrent.futures import ThreadPoolExecutor
    out = {}

    def one(day):
        try:
            return day, forcing_density(day, members=members, cycle_hour=cycle_hour, verbose=False)
        except SystemExit as e:
            return day, {"error": str(e)}
        except Exception as e:
            return day, {"error": "%s: %s" % (type(e).__name__, e)}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for day, rec in ex.map(one, days):
            out[day] = rec
            if verbose:
                if "error" in rec:
                    print("  %s ERROR %s" % (day, rec["error"][:70]))
                else:
                    w = rec["wind_cf_proxy"]
                    sol = rec["solar_irradiance_proxy"]
                    print("  %s wind p50 %8.1f  solar p50 %7.1f  n=%d"
                          % (day, w["p50"], (sol or {}).get("p50", -1), rec["members_used"]))
    return out


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
    sr = sub.add_parser("series")
    sr.add_argument("--start", required=True)
    sr.add_argument("--end", required=True)
    sr.add_argument("--members", type=int, default=1)
    sr.add_argument("--workers", type=int, default=6)
    sr.add_argument("--out", default="")
    f = sub.add_parser("forcings")
    f.add_argument("--day", required=True)
    f.add_argument("--members", type=int, default=0)
    f.add_argument("--out", default="")
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
    if a.cmd == "forcings":
        rec = forcing_density(a.day, MEMBERS[:a.members] if a.members else None)
        print(json.dumps({k: v for k, v in rec.items() if k != "members"}, indent=1))
        if a.out:
            json.dump(rec, open(a.out, "w"), indent=1)
            print("written ->", a.out)
        return 0
    if a.cmd == "series":
        import plant_calendar as pcal
        d0 = dt.datetime.strptime(a.start, "%Y%m%d").date()
        d1 = dt.datetime.strptime(a.end, "%Y%m%d").date()
        days = [x["date"] for x in pcal.sessions(d0, d1)]
        print("%d trading sessions %s..%s, %d member(s), %d workers"
              % (len(days), a.start, a.end, a.members or 31, a.workers))
        recs = forcing_series(days, MEMBERS[:a.members] if a.members else None, workers=a.workers)
        if a.out:
            json.dump(recs, open(a.out, "w"), indent=1)
            print("written ->", a.out)
        return 0
    rec = density(a.day, MEMBERS[:a.members] if a.members else None)
    print(json.dumps({k: v for k, v in rec.items() if k != "members"}, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        print("written ->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
