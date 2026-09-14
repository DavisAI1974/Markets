"""verify_gold.py - THE CONCRETE WALLS around the refine gold master (S105, Greg).

The 5-specialist MBO refine that produced G18 err 8 is preserved byte-frozen in
agents/refine_gold_s105/ with a committed SHA256 manifest. This guard enforces it:

  1. GOLD INTEGRITY (hard wall): recompute the sha256 of every frozen gold file and
     compare to agents/refine_gold_s105/CHECKSUMS.sha256. Any mismatch / missing / extra
     file = the untouchable copy was touched -> HARD FAIL (exit 1). Nothing forecasts.
  2. RUNTIME DRIFT (announce, not block): report whether the LIVE working reasoning
     (agents/mbo_refine_shared.md + mbo_specialist_{A..E}.md) still matches its gold twin.
     MATCH = runtime is the proven engine. DRIFT = you are running NON-GOLD reasoning
     (allowed for deliberate experiments, but you are told, loudly).

Import-and-call (assert_gold_intact()) from stage_group / the coordinators so a run refuses
to start on a violated vault; or run standalone: `python research/kalshi/verify_gold.py`.
"""
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "agents", "refine_gold_s105")
LIVE = os.path.join(HERE, "agents")
MANIFEST = os.path.join(GOLD, "CHECKSUMS.sha256")
GOLD_REASONING = ("mbo_refine_shared.md", "mbo_specialist_A.md", "mbo_specialist_B.md",
                  "mbo_specialist_C.md", "mbo_specialist_D.md", "mbo_specialist_E.md")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest():
    want = {}
    with open(MANIFEST) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            digest, name = line.split(None, 1)
            want[name.strip()] = digest
    return want


def check_gold_integrity():
    """Returns (ok, problems[]). The hard wall - the frozen copy must be byte-exact."""
    problems = []
    if not os.path.isfile(MANIFEST):
        return False, [f"MANIFEST MISSING: {MANIFEST}"]
    want = _load_manifest()
    present = {f for f in os.listdir(GOLD) if f.endswith(".md")}
    for name, digest in want.items():
        p = os.path.join(GOLD, name)
        if not os.path.isfile(p):
            problems.append(f"MISSING gold file: {name}")
        elif _sha(p) != digest:
            problems.append(f"TAMPERED gold file (sha mismatch): {name}")
    extra = present - set(want)
    for name in sorted(extra):
        problems.append(f"UNEXPECTED file in gold dir (not in manifest): {name}")
    return (len(problems) == 0), problems


def check_runtime_drift():
    """Returns (in_sync, drifted[]). Soft wall - announce non-gold runtime, never block."""
    drifted = []
    for name in GOLD_REASONING:
        live_p, gold_p = os.path.join(LIVE, name), os.path.join(GOLD, name)
        if not os.path.isfile(live_p):
            drifted.append(f"{name} (live copy missing)")
        elif not os.path.isfile(gold_p):
            drifted.append(f"{name} (gold copy missing)")
        elif _sha(live_p) != _sha(gold_p):
            drifted.append(name)
    return (len(drifted) == 0), drifted


def assert_gold_intact(loud=True):
    """The wall a run leans on. Raises SystemExit if the gold vault is violated."""
    ok, problems = check_gold_integrity()
    if not ok:
        raise SystemExit("GOLD VAULT VIOLATED - refusing to run:\n  " + "\n  ".join(problems)
                         + "\n(the refine gold master in agents/refine_gold_s105/ is untouchable; "
                           "restore it from git before any forecast run.)")
    in_sync, drifted = check_runtime_drift()
    if loud:
        if in_sync:
            print("[gold] vault intact; runtime reasoning == gold (the proven engine).", flush=True)
        else:
            print("[gold] vault intact; WARNING runtime reasoning DRIFTED from gold: "
                  + ", ".join(drifted) + " (running NON-GOLD reasoning).", flush=True)
    return in_sync


if __name__ == "__main__":
    ok, problems = check_gold_integrity()
    print("=== GOLD INTEGRITY (hard wall) ===")
    if ok:
        print("  PASS - all frozen gold files byte-exact to the committed manifest.")
    else:
        print("  FAIL:")
        for p in problems:
            print("   ", p)
    in_sync, drifted = check_runtime_drift()
    print("=== RUNTIME DRIFT (announce) ===")
    if in_sync:
        print("  runtime reasoning == gold (the proven engine is what runs).")
    else:
        print("  DRIFTED (running non-gold reasoning):")
        for d in drifted:
            print("   ", d)
    sys.exit(0 if ok else 1)