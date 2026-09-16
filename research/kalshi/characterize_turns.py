"""characterize_turns.py — run month_characterize.characterize_day on the pivotal turn days of the
consecutive blocks and save the per-leg fingerprints (flow dip_imb_level, dipole, exhaustion, turning-point
far-side recruitment, depth, move path) for the UNBLINDED refine dig (S95). Saved to a committed json so
the refine agent reasons off the fingerprints without needing S3/creds itself.

  python characterize_turns.py 20250916 20250925 20250929 20251008 20251016 20251020
"""
import sys, json, os, time
import month_characterize as mc

OUT = os.path.join("renders", "ng_refine_s95", "fingerprints.json")

if __name__ == "__main__":
    days = sys.argv[1:]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}   # MERGE into existing (never clobber prior days)
    t0 = time.time()
    for d in days:
        try:
            rows = mc.characterize_day("NG", d, source="s3")
            out[d] = rows
            print(f"[{d}] {len(rows)} legs  ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            out[d] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            print(f"[{d}] ERROR {type(e).__name__}: {str(e)[:120]}", flush=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"[characterize_turns] {len(days)} days -> {OUT}  ({time.time()-t0:.0f}s)")
