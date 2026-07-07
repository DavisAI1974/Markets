import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scripts._s68_drive as D
OUT = os.path.join(D.T.ROOT, "scripts", "_s68_new_results.jsonl")
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)["coin"])
        except Exception: pass
for c in ["xrp","doge","ada","sui","ltc"]:
    if c in done:
        print(f"SKIP {c} (already done)", flush=True); continue
    t=time.time()
    r = D.drive(c, log=lambda m: print(m, flush=True))
    with open(OUT,"a") as f:
        f.write(json.dumps(r, default=str)+"\n"); f.flush()
    print(f"WROTE {c} ({time.time()-t:.0f}s)", flush=True)
print("ALL DONE", flush=True)
