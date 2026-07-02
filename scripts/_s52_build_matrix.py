"""_s52_build_matrix.py — S52 JOB 1 deliverable: the canonical per-cell $/hr matrix WITH SIZING factored.

Consumes `_capacity_model_results.json` (scenario grid: flat/entry-sized, v1/v2, all cells) + the S52 audit
JSONs (`_s52_sizing_audit_results.json` corr/capital-matched, `_s52_winner_persistence_results.json`,
`_s52_winner_fillability_results.json`) and writes `S52_SIZING_MATRIX.md` — the airtight "$/hr with sizing"
Greg asked for: flat vs ENTRY-sized vs WINNER-sided, per cell, per fee scenario, per fill model (v1/v2).

Winner-sided sizing is reported FALSIFIED (both mechanisms — sequence persistence + within-leg green-adds), so
the deployable sizing = entry conviction, which Job 1a proves is CORRECTLY credited by the min() flow cap.
Pure-numpy/json; no pipeline re-run (reads the JSONs the runs already produced).
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cap = json.load(open(os.path.join(ROOT, "_capacity_model_results.json")))
aud = {c["coin"]: c for c in json.load(open(os.path.join(ROOT, "_s52_sizing_audit_results.json")))}
per = json.load(open(os.path.join(ROOT, "_s52_winner_persistence_results.json")))
fil = {c["coin"]: c for c in json.load(open(os.path.join(ROOT, "_s52_winner_fillability_results.json")))}
capd = {c["coin"]: c for c in cap}
ORDER = ["sol", "doge", "xrp", "eth", "btc"]

L = []
def w(s=""): L.append(s)

w("# S52 — Canonical $/hr MATRIX with SIZING factored (Greg Job 1)")
w()
w("> **⚠ There is no single \"$X/hr ceiling.\"** Every number below is one CELL of the matrix "
  "{venue, maker fee, FLAT|ENTRY-SIZED|winner-sided, v1|v2 fill, window}. Cite the cell, or cite the matrix. "
  "All numbers are on **Coinbase** books (pre-Bybit, ~10x tape smaller) over the S51 windows.")
w()
w("This resolves Greg's S51 concern — *\"you aren't factoring in the size up on the winners.\"* The accounting "
  "is now airtight: **(1a)** the flow-cap model credits entry-conviction sizing correctly; **(1b)** the two "
  "winner-side sizing mechanisms *beyond* entry conviction are **falsified** on the forward ledger + "
  "microstructure. So the deployable sizing lever is entry conviction, and the matrix reports it explicitly.")
w()

# ---------------- Job 1a ----------------
w("## Job 1a — is `_dollars()`'s `min(size×S, flow)` under-crediting sizing? **No.**")
w()
w("Per cell (mk0, deploy $1k/leg): `corr(size,cap)` is **positive on all 5** — high-conviction legs sit on "
  "slightly fatter-flow turns, so the `min()` model *does* capture the fat-leg concentration (it is not thrown "
  "away). `corr(size,net)≈+0.03` (entry conviction loads |move|, not wins — S47, re-confirmed). The sizing "
  "lift →0 at the flow-capped ceiling is the **physical flow wall** (you cannot fill more than the real "
  "opposing $), not a modeling artifact. At deploy $1k the cap already binds 54–87% of legs, so sizing acts "
  "on the fat-flow minority — exactly where `corr(size,cap)>0` puts the conviction.")
w()
w("| cell | mean_size | corr(size,net) | corr(size,cap) | corr(cap,net) | cap-binds @$1k | raw lift (uncapped) | "
  "$/hr lift @$1k | capital-MATCHED lift |")
w("|------|-----------|----------------|----------------|---------------|----------------|----------------|"
  "----------------|----------------------|")
for c in ORDER:
    a = aud[c]
    w(f"| {c} | {a['mean_size']:.3f} | {a['c_size_net']:+.3f} | {a['c_size_cap']:+.3f} | {a['c_cap_net']:+.3f} | "
      f"{a['bind_frac_rep']*100:.0f}% | {a['raw_lift']:+.0f}% | {a['rep_lift']:+.0f}% | {a['cm_lift']:+.0f}% |")
w()
w("- **raw lift** = the ledger view (sum net×size, no flow bound) = the UPPER bound if flow were unlimited "
  "(+16..+47%).")
w("- **$/hr lift @$1k** = flow-bounded, as-deployed (mean_size≈1.07 ⇒ ~7% more notional on conviction).")
w("- **capital-matched lift** = rescaled so sized deploys the SAME total notional as flat = pure allocation "
  "skill (SOL +21%→+17%; the ~4pp gap is the small deploy-more effect). ETH/BTC % are on near-zero baselines "
  "(±$1–3/hr absolute) — read them as noise, not signal.")
w()

# ---------------- Job 1b ----------------
w("## Job 1b — winner-side sizing BEYOND entry conviction: both mechanisms **FALSIFIED**")
w()
w("**(i) Sequence anti-martingale** (\"size up after recent winners\") needs leg outcomes to PERSIST. They do "
  "not — lag-1 net autocorrelation is ~0 on every cell and never significantly positive (ETH is mildly "
  "*anti*-persistent, shuffle z=−3.2); prior-k mean predicts next-leg net at corr ≤ |0.035|, E[next|winning]"
  "−E[next|losing] ≈ 0 bps. Leg outcomes are essentially independent (the swing regime resets each turn).")
w()
w("| cell | lag-1 net AC | shuffle z | prior-10 corr | E[next\\|prior>0]−E[next\\|prior<0] |")
w("|------|--------------|-----------|---------------|-----------------------------------|")
for c in ORDER:
    p = per[c]
    w(f"| {c} | {p['ac_net']:+.3f} | {p['shuffle_z']:+.1f} | {p['preds']['10']['corr']:+.3f} | "
      f"{p['preds']['10']['updn']:+.2f} bps |")
w()
w("**(ii) Within-leg green-adds** (\"only add when the leg is green\") needs GREEN legs to offer opposing maker "
  "flow to fill the add. They offer LESS: winners' fillable $ is **0.32–0.65×** losers' on 4/5 cells (only "
  "thin/noisy DOGE inverts). The market force-feeds fill to LOSERS (S45/S51 adverse selection), so a green-only "
  "add structurally cannot load winners harder than losers — dead on the microstructure, not just this window.")
w()
w("| cell | winner fillable $ (med) | loser fillable $ (med) | win/lose ratio |")
w("|------|-------------------------|------------------------|----------------|")
for c in ORDER:
    f = fil[c]
    w(f"| {c} | ${f['cap_win_med']:,.0f} | ${f['cap_los_med']:,.0f} | {f['ratio_med']:.2f} |")
w()
w("**Verdict:** \"size on winners\" that survives falsification = **entry-conviction sizing** (already "
  "deployed; +8–21% at deploy sizes, correctly credited per 1a). A *realized*-winner add fails because you "
  "cannot preferentially fill winners as a maker. This is gated on the Bybit venue book + queue-aware fill "
  "(Job 2) where fill share and the reversed-control test can be re-run — not deployable off Coinbase.")
w()

# ---------------- the matrix ----------------
w("## The canonical matrix — $/hr per cell × fee scenario × fill model")
w()
w("`flat` = $1k/leg every leg. `sized` = entry-conviction (`size_legs`, leakage-clean, hi_clip=4.0). "
  "`winner-sided` = **n/a (falsified, Job 1b)** ⇒ equals `sized`. v1 = front-of-queue (we improve the book at "
  "the turn); v2 = queue-honest (join the back of the best level). Ceiling = all real opposing flow captured "
  "(sizing lift = 0 there by the flow wall). Deploy size $1k/leg.")
w()
for c in ORDER:
    d = capd[c]
    w(f"### {c.upper()} — {d['hrs']:.0f}h, {d['turns_hr']:.0f} turns/hr, med leg-cap ${d['med_cap']:,.0f}, "
      f"v2 {d['fillable_leg_frac_v2']*100:.0f}% legs fillable")
    w("| scenario | net/leg | v1 flat | v1 sized | lift | v2 flat | v2 sized | v1 ceil (sized) |")
    w("|----------|---------|---------|----------|------|---------|----------|-----------------|")
    for s in d["scen"]:
        w(f"| {s['label']} | {s['mean_net']:+.2f}b | ${s['flat_rep']:+,.0f} | ${s['sized_rep']:+,.0f} | "
          f"{s['sizing_lift_pct']:+.0f}% | ${s['v2_flat_rep']:+,.0f} | ${s['v2_sized_rep']:+,.0f} | "
          f"${s['sized_ceil']:+,.0f} |")
    w()

w("## How to cite this (the standing rule)")
w("- **Never** \"$X/hr.\" Say e.g. *\"SOL, Coinbase, mk0, entry-sized, v1, $1k/leg ⇒ +$9/hr; ceiling +$18/hr; "
  "at −1bp v1 ceiling +$71/hr.\"*")
w("- The **sizing contribution** is: +8–21% as-deployed at $1k (mostly SOL/ETH), SHRINKING with the rebate "
  "(uniform per-leg add lifts the flat baseline faster), and →0 at the flow ceiling. It is a "
  "**capital-constrained-regime lever**, real and kept, NOT an order-of-magnitude multiplier.")
w("- The order-of-magnitude levers remain the **REBATE** (mk0→−1bp ≈ 3.9× on SOL, super-linear) and **venue "
  "FLOW** (Bybit ~10× Coinbase tape ⇒ ~10× the ceiling) — the Bybit MM path. Sizing rides on top, it is not "
  "the headline.")

out = os.path.join(ROOT, "S52_SIZING_MATRIX.md")
open(out, "w").write("\n".join(L) + "\n")
print(f"wrote {out} ({len(L)} lines)")
print("\n".join(L[:4]))
