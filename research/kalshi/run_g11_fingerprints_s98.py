"""run_g11_fingerprints_s98.py - DATA_GATE_S98 Tier 1 item 1: G11 per-leg fingerprints on NG.n.0.

Produces the G11 rows the C2 ratio reformulation needs, with the SAME tool and definitions as every
pre-G11 instance in renders/ng_refine_s95/fingerprints.json (month_characterize.characterize_day) -
closing the s100_2 comparability gap (the refine's G11 legs came from a zigzag proxy whose absolute
level was NOT comparable; only its sign was usable).

BASIS (recorded, load-bearing): G11 runs on the OI-continuous NG.n.0 tape (data/nymex_cont_n0,
instrument 1021 throughout, no intra-block roll) - the walked basis for that block. Pre-G11 days in
the same file are NG.v.0-based. Per-day rows are tagged `series_basis` so the file self-describes;
leg statistics are per-day/per-instance reads either way (never pooled across days), and the basis
difference is a recorded fact of the walk, not a comparability defect at the leg level.

  python run_g11_fingerprints_s98.py            # all 12 G11 sessions
  python run_g11_fingerprints_s98.py 20260118   # subset (canary)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)                                    # OUT + regime-tag paths are research/kalshi-relative
sys.path.insert(0, HERE)
import month_characterize as mc

REPO = os.path.dirname(os.path.dirname(HERE))
N0_DIR = os.path.join(REPO, "data", "nymex_cont_n0")
BASIS = "NG.n.0"
OUT = os.path.join("renders", "ng_refine_s95", "fingerprints.json")
G11_DAYS = ["20260118", "20260119", "20260120", "20260121", "20260122", "20260123",
            "20260125", "20260126", "20260127", "20260128", "20260129", "20260130"]

if __name__ == "__main__":
    days = sys.argv[1:] or G11_DAYS
    mc.CONT_DIR = N0_DIR                          # the .n.0 tape - month_characterize honors this override
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}   # MERGE, never clobber prior days
    t0 = time.time()
    for d in days:
        try:
            rows = mc.characterize_day("NG", d, source="local")
            for r in rows:
                r["series_basis"] = BASIS
            out[d] = rows
            print(f"[{d}] {len(rows)} legs  basis={BASIS}  ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            out[d] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            print(f"[{d}] ERROR {type(e).__name__}: {str(e)[:160]}", flush=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"[run_g11_fingerprints_s98] {len(days)} days -> {OUT}  ({time.time()-t0:.0f}s)")
