# FORCING WIRING PROPOSAL - where a forward forcing block joins the served decision state

Status: PROPOSAL. NOTHING IN THIS FILE HAS BEEN APPLIED. No edit was made to
`forecast_harness.py`, `state_health.py` or `gefs_ensemble.py`.

Anchors are line numbers at branch `claude/kalshi-agents-coordinator-guard-sg0n15`, tip
`884fd7f` ("S114: GEFS forcings - forward wind, solar and precip, and a 40x decode fix"). Every
line number below was read, not remembered; re-check them if the tip has moved, because
`forecast_harness.py` is 1,622 lines and the day-dict is a single literal.

Proposed block name: `weather_forcing_forecast`.


## 1. THE SEAM - exactly where a block is built and inserted

### 1.1 The assembly function

`forecast_harness.decision_state(days, mask_after=None, group=None)` - **line 1009**.

One function builds every day. It is a `for d in days:` loop (**line 1062**) whose body assigns
ONE dict literal per day at **lines 1075-1100**. That literal IS the block list - there is no
registry, no plugin table, no ordering logic. A block exists because its key appears in that
literal, and for no other reason. This is the whole seam:

```
1094                  "weather": _weather_asof(iso, wx),
1095                  "weather_forecast": _forecast_weather_asof(iso, mos),
1096                  "weather_forecast_cycle": _mos_cycle_block(iso),
1097                  "freeze_risk": _freeze_risk_block(iso),
1098                  "model_disagreement": _model_disagreement_block(iso),
1099                  "tape_conditions": _tape_conditions_block(iso),
1100                  "holiday": _holiday_asof(iso)}
```

Downstream of the literal the loop does four things, none of which need touching for an exogenous
forward block: hoists firehose health to the day top level (1101-1106), applies the one-shot price
freeze to `_PRICE_DERIVED_BLOCKS` (1107-1116), relives distance fields (1113-1115), and flags a
frozen-front-expired structure (1120-1141).

**The forcing block is NOT price-derived and must NOT be added to `_PRICE_DERIVED_BLOCKS` (line
621).** The docstring at 1022-1023 states the rule the desk already operates under: "Exogenous
feeds (weather/storage/COT/calendar/nuclear/grid/solar/STEO) stay live - published information a
forecaster legitimately learns mid-block." A GEFS cycle published at 17Z on D-1 is exactly that
class. Freezing it at the anchor vintage would repeat the S113/A-12 defect in a new field: every
day of the block served the same forecast, which is wrong for nine days out of ten.

### 1.2 The two forward-looking analogues, and which one to copy

There are two forward blocks already in the literal, and they are built differently.

**`weather_forecast`** - `_forecast_weather_asof(iso, mos)` at **line 112**. Reads a store loaded
ONCE outside the loop (`mos = json.load(open(MOS_ASOF))` at **line 1042**, path constant
`MOS_ASOF` at **line 109**) and does a plain dict lookup per day. Cheap, no per-day import. This
is the pattern to copy IF the store is one file.

**`weather_forecast_cycle`** - `_mos_cycle_block(iso)` at **line 531**, and
**`freeze_risk`** - `_freeze_risk_block(iso)` at **line 589**. These are the closer analogue for a
new feed, and the shape is uniform:

```
531 def _mos_cycle_block(iso: str) -> dict | None:
539     try:
540         import mos_cycle_feed
541     except Exception:
542         return None
543     rec = mos_cycle_feed.mos_cycle_asof(iso)
544     if rec is None:
545         return None
546     ... _compact(view) ...
580     out = {"weekday_open": _compact(rec.get("weekday_open")), "note": (...)}
584     if rec.get("sunday_reopen"):
585         out["sunday_reopen"] = _compact(rec["sunday_reopen"])
586     return out
```

Four properties of that shape are load-bearing and the forcing block must reproduce all four:

1. The feed module owns the STORE and exposes a single `*_asof(day)` accessor
   (`freeze_risk_feed.freeze_risk_asof`, `freeze_risk_feed.py:167`). The harness never reaches
   into a store layout.
2. The import is inside the function and wrapped in `try/except` - a missing module degrades to
   `None` rather than breaking every other block. **This is only safe when the block is declared
   in `state_health.REQUIRED_EVERY_DAY`**; without that declaration the same `try/except` is the
   S107 disease (see section 3.1).
3. The block is COMPACTED. `_compact` selects named fields; it does not pass the raw record
   through. `freeze_risk` reduces a per-basin horizon walk to five fields per basin
   (601-611). The full 31-member payload must not reach the state file.
4. Absence is `None`, never zero. Every docstring in this family says so explicitly
   (`_forecast_weather_asof`: "Missing coverage is None, NEVER 0", line 125; `_mos_cycle_block`:
   "None = store absent for the day, never zeros", line 538).

### 1.3 The blind wall audit

`audit_joins(start_iso, end_iso)` - **line 1244**. Rebuilds the whole state over a date span and
checks each feed's publication wall per day. Two dicts to extend:

- `viol = {...}` at **lines 1256-1259** - one counter per wall.
- `absent = {...}` at **lines 1260-1263** - per-feed absence, with every date NAMED
  (printed at 1374-1378; the docstring at 1248 says "gaps individually, never a percentage").

The nearest existing wall check is the freeze/cycle pair at **lines 1341-1371**: parse
`max_cycle_runtime_utc`, add the dissemination lag, require it not to pass the view's own
`asof_utc`. The forcing wall is simpler because `gefs_ensemble.cycle_for()` already emits
`knowable_from` as an ISO instant (`gefs_ensemble.py:171-183`).


## 2. HOW BLOCKS DECLARE VINTAGE AND STALENESS

Measured across the blocks that carry each convention:

| Mechanism | Where | Meaning |
| --- | --- | --- |
| `asof_utc` / `asof_session` / `as_of` | `weather_forecast` 167, `options_surface`, `storage` | The instant/session the value was true as of. Audited `< iso`. |
| `knowable_from` | `steo_vintage` (1324), `nuclear_outages`, `grid_stack`, `cash_basis` | The first date a forecaster could legitimately have it. Audited `<= iso`. |
| `age_days` | `cash_basis`, `vol_regime` (`n0_prev_age_days`) | Distance from vintage to the reading day. **Relived, not frozen** - see below. |
| `period` | `nuclear_outages` (1329), `grid_stack` (1334) | The data period, audited against a lag wall (grid = period + 2). |
| `masked_one_shot` + `vintage_asof` | 1110-1111 | The one-shot price freeze envelope. **Not for exogenous blocks.** |
| `_relived` / `_relive_note` | `_relive_distance_fields` 744, `_relive_squeeze_live` 682 | A frozen block's day-counts recomputed against the reading day, each change declared. |
| `provisional_tail` | `nws_temp_feed.py:376`, checked `state_health.py:113-117` | A value computed on incomplete inputs, declared so the group can be refused. |

The doctrine those encode, stated at **lines 623-663** (the S113 `_RELIVE_FIELDS` memo): **a
vintage is masked; a distance from today to that vintage is not.** A forcing block is never
masked, so it does not need `_relived` machinery - but it must serve BOTH the vintage
(`cycle_utc`) and the distance (`cycle_age_hours` / `horizon_days`), because the specialist is
reading a forecast whose useful life is measured in hours and nothing else in the block says so.

Note also `_RELIVE_UNRESOLVED` (673-679) and its lesson: a field that cannot be honestly
recomputed is reported UNRESOLVED with a pointer, never guessed from a neighbouring block.


## 3. WHAT `state_health.py` REQUIRES OF A NEW BLOCK

### 3.1 The finding that matters most: silence is the default

`state_health.audit()` iterates exactly two tuples - `REQUIRED_EVERY_DAY` (lines 29-35, checked
at line 70) and `MASKED_MUST_HAVE_FROZEN_VALUE` (40-42, checked at 76) - plus a fixed list of
named reconciliations (82-274).

**A block that appears in `decision_state` but in neither tuple is never checked at all.** It can
be `None` on every day of every group forever and `assert_healthy` will print
"PASS - every required block carries content on every day". `EXPECTED_SPARSE = ("holiday",)` at
line 45 is **dead code** - grep confirms it is defined and never read; the sparse exemption is
achieved by omission from `REQUIRED_EVERY_DAY`, not by that tuple.

So the single most important wiring step is not the harness edit. It is adding the block name to
`REQUIRED_EVERY_DAY`. Wiring the block WITHOUT that line reproduces hole #4 exactly - `vol_regime`
dead on every group from G16 on, five groups scaled without the module built to condition
magnitude, nothing said so.

### 3.2 What "empty" means

`_empty(v)` at line 51: `None`, `{}`, `[]` are empty; a dict is empty if it is a bare mask
envelope. A dict with any real key passes. So a block that returns
`{"error": "store absent"}` PASSES the emptiness check - presence is not correctness. The
emptiness gate is necessary and not sufficient, which is why sections 3.3 and 5 add
reconciliations.

### 3.3 The guard roster

`GUARD_ROSTER` at **lines 292-299** is the versioned list stapled into every inspection
certificate by `write_manifest` (302). A new guard that is not added to the roster produces a
certificate that under-reports what was checked. Any new check must land in both places.

### 3.4 Where the gate fires

`stage_group.stage()` writes the state via the `decision-state` CLI, then at **stage_group.py:90-92**:

```
    import state_health
    _st = json.load(open(out_state))
    state_health.assert_healthy(_st, gid)
```

`assert_healthy` (state_health.py:336) raises `SystemExit` on any hard finding. So the ordering
constraint is absolute: **the store must exist and be restorable BEFORE the block is added to
`REQUIRED_EVERY_DAY`, or every group stage hard-fails.** Serve first, require second.

### 3.5 Unrelated defect noticed while reading (declared, not fixed)

`state_health.py` has TWO `if __name__ == "__main__":` blocks, at **line 321** and **line 347**.
Both execute, in order. Running `python state_health.py g22` therefore reports g22 twice, and
running it with no arguments prints the usage line from the first block and then audits the
default five groups from the second. Harmless today, but it means the file has two entry points
that can drift apart. Not touched here - it is outside this task's file scope.


## 4. THE PROPOSED BLOCK

### 4.1 Schema

```json
"weather_forcing_forecast": {
  "cycle_utc":        "2026-07-19T12:00:00Z",
  "cycle_date":       "20260719",
  "knowable_from":    "2026-07-19T17:00:00+00:00",
  "cycle_age_hours":  32,
  "horizon_days":     0,
  "product":          "pgrb2sp25",
  "members_used":     31,
  "members_requested":31,
  "members_dropped":  [],
  "scale":            "US48 (capacity-weighted wind/solar cells; precip on a 2 deg CONUS grid)",
  "n_wind_cells":     ...,
  "n_solar_cells":    ...,

  "wind_cf_proxy":            {"n":31,"p10":...,"p50":...,"p90":...,"min":...,"max":...},
  "solar_irradiance_proxy":   {"n":31,"p10":...,"p50":...,"p90":...,"min":...,"max":...},
  "precip_proxy":             {"n":31,"p10":...,"p50":...,"p90":...,"min":...,"max":...},

  "d1_wind_cf_proxy_p50":     0.0123,
  "d1_solar_irradiance_p50":  -14.2,

  "gwdd_density": {
    "gw_hdd": {"n":31,"p10":...,"p50":...,"p90":...,"min":...,"max":...,"spread_p90_p10":...},
    "gw_cdd": {"n":31,"p10":...,"p50":...,"p90":...,"min":...,"max":...,"spread_p90_p10":...}
  },

  "served_separately": "wind and solar are NEVER summed - seasonally ANTI-correlated (wind peaks spring/autumn, solar at the solstice). One 'renewables' term is a composite of two opposite annual cycles (D37).",
  "these_are_proxies": "meteorological fields, NOT MWh. Usable only to the extent gefs_ensemble.py validate holds.",
  "wind_method":       "<carried verbatim from the density record>",
  "geography":         "<carried verbatim from the density record>",
  "note":              "forward US48 forcings from the D-1 12Z GEFS cycle; additive beside weather_forecast (temperature) - it does not replace it. The forcing is the term the 0629 miss turned on: gw_cdd rose as forecast and burn FELL 4.2 Bcf/d because wind rose 62%."
}
```

Design points, each with its reason:

- **Three separate distributions, never a sum and never a ratio.** The block carries no
  `renewables_proxy` key and must never acquire one. `gefs_ensemble.forcing_density` already
  states this at its own line 615-618; the served block restates it so a specialist reading only
  the state file sees the constraint.
- **Distributions, not point values.** `p10/p50/p90/min/max` is what `forcing_density` returns
  (`gefs_ensemble.py:603-609`). Serving only `p50` would throw away the width, which is the
  reason G-5 exists.
- **`d1_*_p50` day-over-day level deltas, not run deltas.** This is the S109 seam finding,
  already written into `_mos_cycle_block` at lines 568-577: "a RUN delta baselines against the
  previous model RUN, not the previous SESSION... Across any weekend or holiday boundary,
  difference the LEVELS." The 0629 event was a 62% wind rise across a weekend seam. A run-delta
  channel is structurally blind to it. Compute the delta from the PRIOR SESSION's stored p50 -
  which requires the store to be built over the whole group before the state is assembled.
- **`gwdd_density` is OPTIONAL and declared.** It comes from `gefs_ensemble.density()` (line
  302), a separate set of GRIB messages. If the store carries it, serve it; if not, omit the key
  entirely rather than serving `null` sub-fields. Its value is not only the width - it enables
  the cross-feed reconciliation in section 5.2.
- **`members_dropped` is served even when empty.** See section 6.2: a silently narrow density
  reads downstream as confidence.
- **No per-member rows.** `forcing_density` returns `members` (line 633); the block drops it, the
  way `_mos_cycle_block._compact` drops the horizon walk. The store keeps them for audit.

### 4.2 The vintage claim, and one honest correction to it

`gefs_ensemble.cycle_for` (line 171) returns `knowable_from = cycle 12Z + 5h = 17:00Z on D-1`,
and the module docstring (lines 29-33) argues legality against a "20:00 ET reopen".

The reopen in this repo's own doctrine is **18:00 ET**, not 20:00: `INFORMATION_CLOCK` at
`forecast_harness.py:188-189` says `globex_reopen_et: "Sun 18:00"` and
`session_close_et: "17:00, next session opens 18:00"`.

17:00Z on D-1 is 12:00/13:00 ET on D-1. Against an 18:00 ET open that is **5-6 hours of margin,
not eight**. The claim is still comfortably legal - this is a correction to the stated margin, not
to the conclusion - but the block should not repeat the 20:00 figure. The proposed
`vintage_rule` text below states 18:00 ET and lets the number be checked.

The audit wall should therefore be: `knowable_from` strictly before `D-1 18:00 ET`, which is the
earliest decision point of any session class including a Sunday reopen.


## 5. THE PROPOSED PATCH (diff, NOT APPLIED)

Four files. Order matters: 5.1 and 5.4 (build + restore) must land and be verified before 5.3
(the requirement), or every stage hard-fails.

### 5.1 NEW FILE `research/kalshi/gefs_forcing_feed.py` - the store owner

Rationale: `gefs_ensemble.py` is a FETCHER. It has no store path and no `*_asof` accessor - its
CLI writes wherever `--out` points (`gefs_ensemble.py:757-775`). `forcing_density` costs roughly
3 minutes per day at 31 members by its own docstring (lines 637-644), and `audit_joins` builds
~80 days in one call. **A network fetch inside `decision_state` is not an option.** The block
must read a prebuilt store, and the accessor must live in a module the harness can import
cheaply.

```
+"""gefs_forcing_feed.py - the STORE for the GEFS forward forcings, and the only accessor the
+harness uses. Mirrors freeze_risk_feed.py exactly: pull/build writes a day-keyed index, and
+forcing_asof(day) reads it or returns None.
+
+Split, and it is the reason this is a separate module: gefs_ensemble.py RETRIEVES (network,
+eccodes, minutes per day). This module SERVES (a dict lookup). decision_state calls the server
+in a per-day loop and audit_joins calls it ~80 times in one process; a retrieval in that path
+would make the harness unusable.
+"""
+import datetime, json, os, sys
+HERE = os.path.dirname(os.path.abspath(__file__))
+sys.path.insert(0, HERE)
+
+STORE_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "weather", "gefs_forcing"),
+                    os.path.join("data", "weather", "gefs_forcing")]
+STORE_NAME = "gefs_forcing_index.json"
+MIN_MEMBERS = 20          # DATA, not a tuning knob - see the floor argument in the proposal
+
+def _store_path(create=False):
+    for p in STORE_CANDIDATES:
+        if os.path.isdir(p):
+            return os.path.join(p, STORE_NAME)
+    if create:
+        os.makedirs(STORE_CANDIDATES[0], exist_ok=True)
+        return os.path.join(STORE_CANDIDATES[0], STORE_NAME)
+    return os.path.join(STORE_CANDIDATES[0], STORE_NAME)   # non-existent: caller gets None
+
+def forcing_asof(day):
+    """day = YYYYMMDD or YYYY-MM-DD. -> the stored record or None. Never fetches."""
+    p = _store_path()
+    if not os.path.exists(p):
+        return None
+    with open(p, encoding="utf-8") as fh:
+        store = json.load(fh)
+    return store.get(day.replace("-", ""))
+
+def build(days, members=None, workers=6):
+    """MERGES into any existing store (the feed-A trap-1 discipline freeze_risk_feed follows).
+    Calls gefs_ensemble.forcing_series - the import is HERE, not at module scope, so the harness
+    never pays for requests/eccodes just to read a stored value."""
+    import gefs_ensemble as ge
+    p = _store_path(create=True)
+    store = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
+    recs = ge.forcing_series(days, members=members, workers=workers)
+    for d, r in recs.items():
+        if "error" in r:
+            print("[gefs_forcing] %s ERROR %s - NOT stored (absence is declared, never filled)"
+                  % (d, r["error"][:80]))
+            continue
+        store[d] = r
+    with open(p, "w", encoding="utf-8") as fh:
+        json.dump(store, fh, sort_keys=True)
+    return store
```

Note the deliberate choice in `build`: a day whose fetch errored is NOT written. An error record
in the store would be non-empty, would pass `state_health._empty`, and would read as data.

### 5.2 `research/kalshi/forecast_harness.py` - the block builder and the day literal

Insert after `_freeze_risk_block` (which ends at line 618) and before `_PRICE_DERIVED_BLOCKS`
(line 621):

```
+def _weather_forcing_block(iso: str) -> dict | None:
+    """(S114, registry G-5) FORWARD US48 FORCINGS from the D-1 12Z GEFS cycle - wind, solar and
+    precipitation as DENSITIES, each on its own capacity-weighted geography, plus the optional
+    gas-weighted degree-day density from the same cycle.
+
+    WHY IT EXISTS. Three forecaster specialists independently reported that the desk serves a
+    7-day CDD ladder and NOTHING forward on wind or solar. It is the term the cleanest miss of
+    the walk turned on: on 0629 gw_cdd rose exactly as forecast and gas burn FELL 4.2 Bcf/d
+    because wind rose 62%, with `wind_mwh` served only as a REALIZED value in every slice.
+
+    WIND AND SOLAR ARE NEVER SUMMED (D37). They are seasonally ANTI-correlated - measured on our
+    own EIA-930: wind 9.9 TWh/wk in April vs 5.9 in August, solar 3.5 in June vs 1.4 in December.
+    A single 'renewables' term is a composite of two opposite annual cycles and any coefficient
+    fitted on it is fitted on their ratio, which is a season proxy.
+
+    Vintage: the D-1 12Z cycle, knowable ~17:00Z on D-1, against an 18:00 ET reopen
+    (INFORMATION_CLOCK above) - 5-6 hours of margin, recorded per record as `knowable_from` so
+    the claim is auditable rather than asserted. NOT price-derived: it stays LIVE under the
+    one-shot mask, like every other exogenous published feed.
+
+    None = the day is absent from the store, never zeros, never a narrowed density."""
+    try:
+        import gefs_forcing_feed as gff
+    except Exception:
+        return None
+    rec = gff.forcing_asof(iso.replace("-", ""))
+    if not rec:
+        return None
+
+    def _dist(d):
+        return {k: d[k] for k in ("n", "p10", "p50", "p90", "min", "max") if k in d} if d else None
+
+    prev = gff.forcing_prev(iso.replace("-", ""))      # the PRIOR STORED SESSION, for level deltas
+    out = {
+        "cycle_utc": rec.get("cycle_utc"), "knowable_from": rec.get("knowable_from"),
+        "cycle_date": (rec.get("cycle_utc") or "")[:10].replace("-", "") or None,
+        "product": rec.get("product"), "scale": rec.get("scale"),
+        "n_wind_cells": rec.get("n_wind_cells"), "n_solar_cells": rec.get("n_solar_cells"),
+        "members_used": rec.get("members_used"),
+        "members_requested": rec.get("members_requested"),
+        "members_dropped": rec.get("members_dropped") or [],
+        "wind_cf_proxy": _dist(rec.get("wind_cf_proxy")),
+        "solar_irradiance_proxy": _dist(rec.get("solar_irradiance_proxy")),
+        "precip_proxy": _dist(rec.get("precip_proxy")),
+        "served_separately": rec.get("served_separately"),
+        "these_are_proxies": rec.get("these_are_proxies"),
+        "wind_method": rec.get("wind_method"), "geography": rec.get("geography"),
+        "seam_delta_note": ("the d1_* fields difference LEVELS between this session and the "
+                            "prior STORED session, never model run-over-run. A run delta "
+                            "baselines against the previous RUN and is structurally blind "
+                            "across a weekend seam - measured -0.219 on 0629 against a +4.7 "
+                            "CDD level move."),
+        "note": ("forward US48 forcings, D-1 12Z GEFS. ADDITIVE beside weather_forecast - it does "
+                 "not replace the temperature ladder. Wind and solar are separate terms by "
+                 "construction and must never be summed (D37)."),
+    }
+    if rec.get("gwdd_density"):
+        out["gwdd_density"] = rec["gwdd_density"]
+    for k, sk in (("d1_wind_cf_proxy_p50", "wind_cf_proxy"),
+                  ("d1_solar_irradiance_p50", "solar_irradiance_proxy")):
+        a = (rec.get(sk) or {}).get("p50")
+        b = ((prev or {}).get(sk) or {}).get("p50")
+        out[k] = round(a - b, 5) if (a is not None and b is not None) else None
+    if out["d1_wind_cf_proxy_p50"] is None:
+        out["d1_basis"] = ("no prior stored session - the level delta is UNRESOLVED, not zero "
+                           "(build the store from at least one session before the block)")
+    return out
```

(`forcing_prev(day)` is a companion accessor in 5.1: the greatest stored key strictly less than
`day`. It must return the PRIOR STORED session and declare when there is none - filling it with
the same day's value would manufacture a zero delta, which is the exact shape of the 0629 miss.)

Then the day literal, at line 1097:

```
                   "weather_forecast_cycle": _mos_cycle_block(iso),
                   "freeze_risk": _freeze_risk_block(iso),
+                  "weather_forcing_forecast": _weather_forcing_block(iso),
                   "model_disagreement": _model_disagreement_block(iso),
```

And `audit_joins`, at lines 1256-1263:

```
     viol = {..., "mos_cycle_wall": 0, "freeze_wall": 0,
+            "forcing_wall": 0, "forcing_members": 0}
     absent = {..., "weather_forecast_cycle": [], "freeze_risk": [],
+              "weather_forcing_forecast": []}
```

with the check inserted after the freeze block (after line 1371):

```
+        wf = st.get("weather_forcing_forecast")
+        if wf is None:
+            absent["weather_forcing_forecast"].append(iso)
+        else:
+            # THE WALL: the cycle must be knowable before the EARLIEST decision point of any
+            # session class - the 18:00 ET reopen on D-1 (INFORMATION_CLOCK), not the 20:00 the
+            # fetcher's docstring cites. 17:00Z on D-1 clears it by 5-6h.
+            kf, cu = wf.get("knowable_from"), wf.get("cycle_utc")
+            if kf:
+                open_et = datetime.datetime.combine(
+                    datetime.date.fromisoformat(iso) - datetime.timedelta(days=1),
+                    datetime.time(18, 0), tzinfo=ZoneInfo("America/New_York"))
+                if datetime.datetime.fromisoformat(kf) >= open_et.astimezone(datetime.timezone.utc):
+                    viol["forcing_wall"] += 1
+                    print(f"  VIOLATION forcing {iso}: knowable_from {kf} not before the "
+                          f"D-1 18:00 ET reopen")
+            if cu and cu[:10] >= iso:
+                viol["forcing_wall"] += 1
+                print(f"  VIOLATION forcing {iso}: cycle {cu} is not from a prior day")
+            mu = wf.get("members_used")
+            if isinstance(mu, int) and mu < 20:
+                viol["forcing_members"] += 1
+                print(f"  VIOLATION forcing {iso}: only {mu} members - a thin ensemble is a "
+                      f"NARROW density, which reads downstream as confidence")
```

(`ZoneInfo` needs `from zoneinfo import ZoneInfo` at the harness top; `datetime` is already
imported at line 18.)

### 5.3 `research/kalshi/state_health.py` - the declaration (LAND THIS LAST)

```
     "steo_vintage", "cot", "flow_calendar", "solar", "nuclear_outages", "grid_stack",
     "weather", "weather_forecast", "weather_forecast_cycle", "freeze_risk",
+    "weather_forcing_forecast",
     "model_disagreement", "tape_conditions",
 )
```

Plus two guards inside the per-day loop of `audit()`, both RECONCILIATIONS against an independent
source rather than presence checks - the only kind that catches a well-formed wrong value:

```
+        # S114 THE THIN-ENSEMBLE NARROWING. gefs_ensemble.station_field returns None on ANY
+        # non-200 idx response (gefs_ensemble.py:222), and the archive throttles: MEASURED
+        # 2026-08-06, 2 of 5 first-attempt HEAD probes returned 503 and all 5 returned 200 on
+        # retry. A throttled member is therefore INDISTINGUISHABLE from an absent one, and the
+        # loss shows up as a NARROWER density - i.e. as confidence. HARD, because narrow is
+        # exactly the direction a forecaster acts on.
+        wf = state[d].get("weather_forcing_forecast") or {}
+        if isinstance(wf, dict) and wf:
+            mu = wf.get("members_used")
+            if isinstance(mu, int) and mu < 20 and not wf.get("thin_ensemble_basis"):
+                hard.append(f"{d}: weather_forcing_forecast members_used={mu} of "
+                            f"{wf.get('members_requested')} with no thin_ensemble_basis declared "
+                            f"- a dropped member is silent (any non-200 reads as absent) and the "
+                            f"loss appears as a NARROWER density, which reads as confidence.")
+            if "renewables_proxy" in wf or "wind_solar_sum" in wf:
+                hard.append(f"{d}: weather_forcing_forecast carries a SUMMED renewables term. "
+                            f"Wind and solar are seasonally ANTI-correlated (D37); a coefficient "
+                            f"fitted on their sum is fitted on their ratio, a season proxy.")
+
+        # S114 THE CROSS-FEED SCALE RECONCILIATION. weather_forecast (MOS) and the GEFS
+        # gwdd_density are two INDEPENDENT forecasts of the SAME quantity on the SAME scale -
+        # gefs_ensemble imports nws_temp_feed.station_weights() and degree_days() rather than
+        # reimplementing them, which is what makes the comparison legitimate. Disagreement is
+        # real information and must NOT be hard-failed; but a MOS value outside [min,max] by
+        # more than the ensemble's own full range is a scale/units/day-alignment defect, not
+        # forecast spread. SOFT, and it is a scale check, never a skill check.
+        gd = (wf.get("gwdd_density") or {}) if isinstance(wf, dict) else {}
+        mos = state[d].get("weather_forecast") or {}
+        for fld, key in (("gw_cdd", "forecast_gw_cdd"), ("gw_hdd", "forecast_gw_hdd")):
+            dd, mv = gd.get(fld), mos.get(key)
+            if isinstance(dd, dict) and isinstance(mv, (int, float)):
+                lo, hi = dd.get("min"), dd.get("max")
+                if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
+                    rng = hi - lo
+                    if mv < lo - rng or mv > hi + rng:
+                        soft.append(f"{d}: MOS {key}={mv} sits more than one ensemble range "
+                                    f"outside the GEFS {fld} density [{lo}, {hi}] - two "
+                                    f"independent forecasts of one quantity that should share a "
+                                    f"scale. Suspect units or day alignment, not skill.")
```

and the roster at lines 292-299:

```
     "vol_regime n0 era vs same-session tape when undeclared [S110 f3]",
+    "forcing thin-ensemble floor + no summed renewables term [S114]",
+    "MOS-vs-GEFS degree-day scale reconciliation (soft) [S114]",
 )
```

### 5.4 `research/kalshi/restore_substrate.py` - the path trap

`data/` is disposable (D34) and does not survive a session. The restore table at lines 37-55
carries an explicit warning about exactly this class of bug: `weather/nws_temp/ -> data/nws_temp`
is annotated "THE PATH TRAP", and it is hole #6 - the degree-day store one directory off the path
the harness reads, empty on EVERY staged group.

```
     ("weather/mos_cycle/",        "data/weather/mos_cycle"),
     ("weather/mos_freeze/",       "data/weather/mos_freeze"),
+    ("weather/gefs_forcing/",     "data/weather/gefs_forcing"),
```

Without this line, a fresh session restores everything except the forcing store, the block is
`None` on every day, and (once 5.3 lands) every `stage_group` call hard-fails. That is the
designed behaviour, but it is a session-killer if discovered at stage time instead of here.


## 6. WHAT WOULD BLOCK WIRING

Ordered by how hard each one bites.

### 6.1 BLOCKER - there is no store and no accessor. `gefs_ensemble.py` cannot be called from `decision_state`

`gefs_ensemble` exposes `density()`, `forcing_density()` and `forcing_series()`; all three FETCH.
The module has no store path, no `*_asof` function, and its CLI writes only to an explicit
`--out` (lines 738-775). `forcing_density` at 31 members is ~3 minutes per day by its own
docstring; `decision_state` calls each block builder once per day in a loop, and `audit_joins`
builds ~80 days in one process. Wiring the fetcher directly would make a single `audit-joins`
run a multi-hour network job with no cache.

Since `gefs_ensemble.py` is off-limits (another process owns it), the store owner has to be the
new module in 5.1. This is a build, not a config change - **it is the actual gate on this wiring.**

### 6.2 BLOCKER for correctness - a throttled member is indistinguishable from an absent one

MEASURED today, 2026-08-06, against the live bucket: HEAD probes of
`gefs.YYYYMMDD/12/atmos/pgrb2sp25/gec00.t12z.pgrb2s.0p25.f012.idx` returned

```
20251104 -> 200   20260201 -> 200   20260615 -> 503   20260718 -> 503   20260804 -> 200
```

and on retry three seconds later, `20260615 -> 200`, `20260718 -> 200`, `20260628 -> 200`. The
503s were throttling, not absence.

`station_field` returns `None` for any non-200 (`gefs_ensemble.py:222` and `237`). So under load,
members drop for a reason that has nothing to do with weather, and the density gets NARROWER.
`density()` at least declares `members_dropped` (line 345); `member_forcings` returns `None`
without naming the member, so `forcing_density` records only `members_used` (line 629).

This is the S107-S110 disease family in a new field: present, numeric, in range, internally
consistent, and wrong in the confident direction. Two mitigations, both required:

- retry with backoff in the STORE BUILDER (5.1), so a 503 is never recorded as a drop;
- the members floor guard in `state_health` (5.3), so a thin day cannot be staged undeclared.

The floor of 20 of 31 is a stated choice, not a fitted one, and it should be recorded as such.

### 6.3 BLOCKER for historical groups - coverage must be probed, never assumed

`REQUIRED_EVERY_DAY` is checked on EVERY day of EVERY group that gets staged or re-staged, and
`audit_joins` defaults to `2025-11-03..2026-02-27` (line 1244). Adding the block to
`REQUIRED_EVERY_DAY` before the store covers those dates turns every historical re-stage into a
hard failure.

Retention looks adequate on the dates probed above (2025-11-04 and 2026-02-01 both 200), which is
consistent with the fetcher's own measured claim of 217 retained 2026 days. But **five HEAD probes
are not a coverage audit.** Required before 5.3 lands: build the store across every group window
that may be re-staged, and confirm the day count matches the session count from
`plant_calendar.sessions`. If any window cannot be covered, the block must be served (5.2) and
NOT required (5.3) until it can, with the gap named per date the way `audit_joins` names absences.

### 6.4 The `d1_*` level delta needs the prior session in the store

The forcing delta that matters is a level difference across sessions, including weekend seams -
that is the whole S109 seam finding, and the 0629 event is a weekend. A block built for day 1 of a
group with no earlier stored day cannot compute it. The proposal returns `None` plus a `d1_basis`
note rather than 0.0; a zero would say "wind unchanged" on precisely the day the mechanism fires.
Practical consequence: **build the store from at least one session BEFORE each group window.**

### 6.5 Dependencies and cost

`eccodes` is present in this container (verified: 2.48.0). `requests` is imported at
`gefs_ensemble` module scope, which is why 5.1 defers the `import gefs_ensemble` into `build()` -
the serving path must not require either library. Retrieval is unsigned and free (no credentials,
no AWS keys, so nothing here touches the S107/S100 key path). Cost is time, not money: ~3 min/day
at 31 members, ~5 s/day at 1 member for validation.

### 6.6 Not a blocker, but must be stated - these are PROXIES

`forcing_density` says it outright at its line 627: "meteorological fields, NOT MWh. Usable only
to the extent the validation below holds." `build_realized_forcings.py` exists to build the
validation target from EIA-930 US48 WND/SUN, and records that the uniform-grid version measured
37% (wind) and 53% (solar) day-over-day direction against realized output - 37% being worse than
a coin flip, which is why the capacity-weighted geography replaced it. The served block carries
`these_are_proxies` and `geography` verbatim so no specialist reads a `wind_cf_proxy` p50 as
generation.

Per D37 and `per_event.py`: the validation of this feed must be reported per cell (month, and a
recent-capacity window) with the largest actual moves named individually. A pooled correlation or
an R2 across the span would be fitting fleet capacity growth - `build_realized_forcings.py` names
that trap at its own lines 28-33 (US48 daily solar ~1e5 MWh in Jan 2019 vs ~1.2e6 MWh in Aug
2026).


## 7. SEQUENCE

1. Build `gefs_forcing_feed.py` (5.1), with retry/backoff. Run it over one group window.
2. Verify day count against `plant_calendar.sessions`; name any missing date.
3. Wire the block and the `audit_joins` wall (5.2). Serve it. Confirm `audit-joins` reports
   0 `forcing_wall` violations and lists absences by date.
4. Push the store to S3 and add the restore line (5.4). Verify a restore from empty.
5. ONLY THEN add `weather_forcing_forecast` to `REQUIRED_EVERY_DAY` and add the two guards and
   the roster entries (5.3).
6. Negative-test both guards by constructing a state that FIRES each one and printing the guard's
   output (NC-3: a guard whose firing branch never executed has not been tested).
