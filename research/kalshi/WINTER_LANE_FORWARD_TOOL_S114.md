# THE WINTER STORAGE LANE AS A FORWARD FORECASTING TOOL — S114 (2026-08-05)

**Status: DESIGN + EVIDENCE. Nothing here is built.** Greg, S114, on seeing the two-class
taxonomy and the hydro cycle: *"Definitely write this up as a forward forecasting tool also.
This is huge."* This document is that write-up. It came out of the S114 per-event dissection of
the A-24 hidden-edge paper, run under two binding instructions: *"Don't average anything and
just see what the data tells you"* and *"Do not let your assumed finding kill what the data is
saying."* Every claim below is carried by named events or a labeled p50; no fitted coefficient,
no R2, no pooled anything.

Read with: `OPEN_ITEMS.md` A-38 / G-4 / A-29 / A-33 / A-34 / A-31 / A-24a, `DECISIONS.md` D37
(no average may be a verdict) and D31 (refutations are scoped), `FORECAST_ARCHITECTURE_S111.md`
(the product is a curve; the adjustment loop is the product).

Evidence files, all committed:
- `data_records/storage_week_by_week_S113.csv` — 391 storage weeks (dS, burn, breadth, dVRE).
- `data_records/us48_hydro_daily_S114.csv` — 1,093 days of national hydro (NEW, S114; see s3).
- `data_records/walk_census_g18_g23_S114.csv` — all 60 modern scored walk days with error,
  revisions, disagreement, ages, tape panel (NEW, S114).
- `data_records/us_gas_demand_by_sector_S113.csv` — the A-38 monthly sector table.

---

## 0. THE ONE-PARAGRAPH VERSION

The winter storage draw has two drivers the desk does not model and one it does. The one it
models (power burn) is the MINORITY term in winter (A-38). The two it does not: **res/comm
heating sets the SIZE of the draw**, and **the renewables term sets which way the burn stack
errs** — renewables UP masks the draw (burn reads soft while the tank drains through the
heating meter), renewables DOWN joins the demand and marks the tail regime. Hydro — never in
the renewables composite at all — turns out to be **winter-strong and dispatched INTO cold
events**: it is the reliability buffer, and its failure mode (a drought winter) is the
unobserved tail. Every input needed to run this forward exists or is already a registry item;
what is missing is the joins.

---

## 1. THE TWO-CLASS TAXONOMY OF WINTER DEEP-DRAW WEEKS (measured, named)

From the 391-week file, at fixed burn, the deep-draw weeks split into two classes with
different mechanics and different model errors. "Deep" here means the weeks that move the
print; every member is named.

### Class 1 — cold with renewables UP: heating drives the draw, wind mutes the burn

Of the fourteen deepest breadth-0/1 winter weeks, **twelve carry POSITIVE dVRE** — renewables
rose into the draw:

```
2025-01-16  dS -258  dVRE +1,493k      2026-02-12  dS -252  dVRE +1,461k
2022-01-20  dS -206  dVRE   +680k      2019-03-14  dS -200  dVRE +1,608k
2024-02-01  dS -197  dVRE   +838k      2025-02-20  dS -196  dVRE +3,078k
2022-02-17  dS -190  dVRE +1,484k      2024-12-12  dS -190  dVRE +1,986k
2021-01-21  dS -187  dVRE +2,653k      2019-01-24  dS -163  dVRE +3,819k
2020-12-24  dS -152  dVRE +3,286k      2020-02-20  dS -151  dVRE   +110k
(exceptions: 2025-02-27 dS -261 dVRE -195k; 2019-03-07 dS -149 dVRE -4k - both near-zero dVRE)
```

Mechanism (and it is the A-38 mechanism, not a new one): wind displaces gas in the power
stack, so **power burn reads soft exactly while heating drains the tank**. A burn-based model
under-calls every one of these. The extreme of the class is Uri — **2021-02-25, dS −338 on
burn 168.3, the LOWEST burn in the winter table, dVRE +4,761k** — heating plus supply
freeze-offs with the power sector barely burning.

### Class 2 — cold with renewables DOWN: the conjunction, and it is the tail

The deep draws at breadth 4–6 all carry negative dVRE, and they are the named freeze weeks:

```
2024-01-25  dS -326  br6  dVRE -4,157k   (the January 2024 freeze)
2026-01-29  dS -241  br5  dVRE -2,748k   (the Arctic-high week - cold outbreaks are CALM)
2019-01-31  dS -173  br6  dVRE -1,791k   (the 2019 polar vortex)
2021-01-28  dS -128  br6  dVRE -1,843k   (the week into Uri's ramp)
```

Heating demand exploding AND the wind term gone AND (in '21/'24) supply freezing — A-33's
correlated-failure class. The crowd behaves: ordinary renewables-down weeks with no cold (the
rest of the breadth-6 column: −9 to −81, +10, +107) draw nothing. **A renewables drop alone is
not bullish storage; the conjunction with heating cold is.**

### The heating term isolated: the same-burn same-breadth November pairs

Four pairs, identical burn, identical breadth, 219–369 Bcf apart — and every pair is a
November/early-December week against a January/February week:

```
2021-02-25  -338 (burn 168, br2)   vs   2020-11-19   +31 (burn 174, br2)   gap 369 Bcf
2022-02-03  -268 (burn 197, br2)   vs   2022-11-10   +79 (burn 197, br2)   gap 347 Bcf
2025-01-30  -321 (burn 248, br4)   vs   2024-12-05   -30 (burn 256, br4)   gap 291 Bcf
2019-02-07  -237 (burn 171, br3)   vs   2020-11-27   -18 (burn 172, br3)   gap 219 Bcf
```

The only thing that differs is the res/comm heating term we serve nothing for. **This is
A-38's monthly finding corroborated at the WEEKLY horizon** — the horizon the EIA print
actually trades — from a second, independent, committed file. A-38's own caveat demanded this
re-check before anything was built on it; a large piece of it is now done.

### The breadth variable, correctly scoped: a one-sided EXCLUSION gate per season

Full per-level listings (391 weeks) give exclusion statements, not a sorter:

- **WINTER: breadth >= 4 nearly excludes a monster draw.** Deep weeks (<= −150) by level:
  br0 3, br1 11, br2 7, br3 13 (and br3 has ZERO builds in 30 weeks) versus br4 2, br5 3,
  br6 2 — and the exceptions at high breadth are precisely the Class-2 freeze weeks above.
  When the exclusion breaks, you are in the conjunction regime and every economic-regime model
  is off.
- **SUMMER: breadth <= 1 nearly excludes a monster build.** Builds >= +100: zero at br0, one
  at br1 (+100, 2019-05-23), 27 across br2-6. The only summer draw in the file (−6,
  2024-08-15) sits at br0.
- The middle does NOT ladder monotonically (br2 shallower-loaded than br3, br5 deeper than
  br4). The information is at the ends. Whether the winter exclusion is partly burn-driven is
  NOT settled; the same-burn neighbor bands hold it inside fixed burn, but the full
  burn-inside-month control has not been run on the breadth count (the S113 kill tested
  wind/solar SHARES, a different variable). D24 state: not-yet-searched.

---

## 2. THE HYDRO RESULT (S114, new): winter-strong, and dispatched INTO the freeze events

Measured from the public EIA-930 six-month balance files (keyless), national daily hydro,
three-plus years. Monthly p50 of daily GWh (labeled p50s, per D37; artifact rows above
30,000 MW per BA-hour dropped and counted — 46 rows across six files):

```
mon      2021*     2024     2025     2026
 1        806      689      669      828
 2        766      737      714      728
 3        716      756      734      817
 4        685      707      792      718
 5        729      840      847      722
 6        783      788      791      766
 7          -      743      689        -
 8          -      697      650        -
 9          -      565      514        -
10          -      501      502        -
11          -      558      577        -
12          -      631      725        -
     (*2021 files predate the WAT/pumped-storage split; 2021 = hydro incl PS. Post-2023
      columns are Hydropower Excluding Pumped Storage, so the A-20 pumped-storage confounder
      is OUT of the modern numbers by construction.)
```

**The cycle: hydro TROUGHS in Sep–Oct (~500–565 GWh/d) and runs HIGH December–June (~630–850),
strongest in deep winter and early spring, in every year measured.** At ~7,900 Btu/kWh the
seasonal swing (~325 GWh/d) is ~2.6 Bcf/d of gas-equivalent, and the January level (~830) is
~6.5 Bcf/d — hydro is BIGGER than solar in January (828 vs 513 in 2026) and about half of
wind.

**And on the freeze-event days themselves, hydro ran ABOVE its month p50 — it was dispatched
into the events, not lost with the wind:**

```
Uri week:        02/15/2021  895   02/16 848   02/17 859   02/18 903   02/19 844   (p50 766)
Jan-2024 freeze: 01/15/2024  823   01/16 842   01/17 787                           (p50 689)
Jan-2026 event:  01/20/2026  883   01/22 791   01/23 787                           (p50 828)
exception:       01/25-30/2025  593/623/642                                        (p50 669)
```

**Consequence for the model: hydro belongs on the SUPPLY-BUFFER side of the winter equation,
not in the intermittent-renewables term.** It is reservoir storage being played as the
reliability trump card (the S113 doctrine, now with its instances). The dVRE composite —
wind+solar — never contained it, so nothing above double-counts it. Its failure mode is not a
calm day but a DRY YEAR: a drought winter removes up to ~6 Bcf/d-equivalent of buffer at the
worst time, and **that tail is unobserved in the three winters sampled** — the inverted-U's
drought limb (A-16/A-20). Forward instruments for it are slow and dated: reservoir state and
guide curves, TVA planned releases (A-18/A-20) — the information class that survives past the
5-7 day horizon.

Caveats, named: EIA-930 basis defects are documented (G-20); behind-the-meter solar is absent
from the file entirely; 2021 carries the definitional difference above; three winters is three
winters.

---

## 3. THE SEASONAL REVISION SIGN MAP (prerequisite for any acceptance build)

From the walk census (60 modern scored days, `walk_census_g18_g23_S114.csv`), two inversions
the data hands over, both per-event listings:

**(a) The shoulder HDD axis runs BACKWARDS.** The five biggest warm revisions (cold removed,
−1.00..−1.70 GWDD) landed **+420, +30, +370, +610, +1230 — five of five non-negative** — while
the small warm revisions (−0.45..−0.90) landed **−990, −1080, −830, −990** (the +2100 is the
EIA print Thursday), and the mid-size cold-adds (+1.31, +1.41, +1.56) landed **−1050, −530,
−960 — all down**. In April–May, removing cold is bullish and adding cold is bearish — the
opposite of the winter axis. A raw `d_gw_hdd` has no season-stable sign (D28's transfer
disease on a DELTA). Any acceptance/revision build (A-24a) needs this map first, and the data
has already supplied the shoulder's direction.

**(b) The size axis inverts.** The three largest CDD revisions in the census (+2.66, +2.51,
+2.26) landed on **+230, −60, +180 — the quietest days in the listing** — while the violence
sat at mid-size revisions (+2.01→−1110, −1.66→−2050, +1.94→−730, +1.05→+650, +1.02→−660,
+0.93→+780). The biggest forecast news produced the smallest moves. The natural story
(broadly-seen revisions are already priced) is rank 1's own pre-registered limb and is flagged
as a story, not a finding.

**(c) The mediation instances, from the served stacks themselves.** 0629 (act −1110, blind
+325): the slice served wind **+660k** MWh and gas **−556k** vs three days prior. 0601 (act
−990, blind +350): wind **+1,071k** — the largest wind move in the census — gas **−1,271k**,
coal −529k. Two B-Mondays among the walk's seven worst errors, the mediation served and unread
both times. 0601 is 0629's previously unnamed twin; G-4's canonical instance is now n=2 inside
one census. Honest counterexample, kept: 0617 (wind −514k, gas +230k, day −970) — the stack
does not explain it.

---

## 4. THE TOOL

**Target:** the weekly EIA storage print (the storage lane's traded object), with the daily
curve as context. One object, lanes diverging late (D32). The LLM is never in the hot path
(S98).

**The forecast identity, term by term, with each term's forward instrument:**

```
weekly draw =
    HEATING SIZE TERM          fwd HDD (served, dated ahead)  x  HDD->res/comm Bcf/d converter
                               [the converter is A-38 - THE missing model; STEO monthly anchors
                                the level; the weekly shape is the build]
  + POWER RESIDUAL             fwd load (demand_forecast_mwh, SERVED, all 7 BAs)
                               - fwd wind      [G-4 ISO feeds; A-29 MOS wsp fetched-and-dropped]
                               - fwd solar     [G-4; solar clock served]
                               - hydro state   [slow buffer level: reservoir/guide curves,
                                                TVA planned releases - A-18/A-20; s2 above]
                               - nuclear sched [A-17]
                               - committed-coal window [A-31's detector: starts observable in
                                                EIA-930 at period+2, ~1-2 week duration, near-
                                                deterministic once started]
                               -> gas MWh -> Bcf via the DECLARED conversion [A-27: CC/CT mix,
                                             never the bare 7,900 constant]
  + SUPPLY INTERRUPTION        freeze geometry across producing basins [A-24f fields, served
                               and unread; supply-side per A-33]
```

**Regime flags, both one-sided, both cheap:**

- **The Class-2 conjunction watch (A-33):** forecast cold + forecast calm (wind collapse) +
  supply stress = the tail alert. In this regime burn and price DECOUPLE (curtailment order)
  and the economic-regime model is explicitly OFF. Hydro state modulates it: buffer full →
  2021/2024-style absorption; buffer dry → the unobserved worse tail.
- **The breadth exclusion gates (s1), as NO-CALL inputs:** winter breadth >= 4 argues against
  a monster-draw call unless the conjunction flag is up; summer breadth <= 1 argues against a
  monster-build call. These feed A-2 (NO CALL), not a direction.

**The acceptance layer (A-24a), gated on s3's sign map:** revision size x model convergence x
completion-vs-reopen timing. The census already shows its authority half working (0713:
convergence 0.017, every fresh instrument down, posterior +550 — D25's override day; 0511:
disagreement 1.127, the walk's worst day) and its sign half unusable without the seasonal map.

**Validation (A-1, D37, binding):** every claim scored by `per_event.report(...)` against the
named benchmarks (zero-change, seasonal-naive) — sum|err|, drift, survival, p50/p90 AND MAX,
improved/worsened COUNT, largest actual moves named one by one. No scalar verdicts. The
falsifier structure per term: the converter fails if same-HDD weeks stop differing by their
res/comm share; the mediation term fails if renewable surprises stop landing on gas (0629/0601
class); the conjunction flag fails if a Class-2 week arrives without its components.

**What exists today vs what must be built:**

| term | state |
|---|---|
| fwd HDD/CDD + revisions | SERVED (weather_forecast, dated ahead) |
| fwd load | SERVED (demand_forecast_mwh, 7 BAs) |
| HDD -> res/comm converter | **A-38 — not built, the largest gap** |
| fwd wind/solar | **G-4 — research delivered, feed not built**; A-29 wind speed fetched-and-dropped |
| hydro buffer state | store rebuilt with hydro (S113); forward state = A-18/A-20 TVA/USACE instruments |
| nuclear schedule | A-17 |
| committed-coal window | A-31 — detectable from served fields, detector not built |
| conversion (CC/CT) | A-27 |
| freeze geometry | A-24f — fields served, 148/157 unread |
| acceptance layer | A-24a — blocked on the s3 sign map |
| NO CALL plumbing | A-2 |

Nothing above requires a new data source. Two items (A-38 converter, G-4 feeds) are the
long poles; everything else is joins over served fields.

---

## 5. WHAT THIS DOCUMENT CHANGES, AND WHAT IT DOES NOT

It does NOT reopen the S113 kill of the dVRE/shares regularity (D37's worked example — that
died on its own evidence and stays dead). It scopes the breadth count per D31 (exclusion gate
+ conjunction marker, not a storage forecaster). It does not touch the HH lane (A-37 still
blocks it) or the summer stack (the burn model remains the summer model). It adds hydro to
the winter account on measured instances, corrects the renewables term's composition (hydro
out of the intermittent bucket, into the buffer), and converts the A-24 paper's surviving
candidates into placed components of one forward tool instead of seven competing edges.
