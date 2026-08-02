#!/usr/bin/env python3
"""S109: assemble per-DAY blind posteriors into the per-SPECIALIST shape the coordinator reads.

Per-day causal isolation (hole #11) means a specialist owning four days runs four times and writes
four files. The coordinator contract is one file per specialist carrying a days[] array. This is the
deterministic join, and it is GUARDED rather than trusting the filenames: every day must be owned by
the tag it was filed under, per group_config.owner_map, and every owned day must be present. A missing
day fails here rather than surfacing as a silently short block downstream.
"""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")

def main(gid="g22", perday_dir=None):
    # S110 (RUN_SOP): per-day dir defaults to the blind's g<N>_perday; the refine passes its own
    # (g<N>_refine_perday) so refine posteriors can never silently join from the blind's directory.
    PD = os.path.join(FC, perday_dir or f"g{gid[1:]}_perday")
    if not os.path.isdir(PD):
        raise SystemExit(f"MERGE GUARD FAILED: per-day dir does not exist: {PD}")
    owner = gc.owner_map(gid); n = gid[1:]
    by_tag, errs = {}, []
    for f in sorted(glob.glob(os.path.join(PD, f"grp{n}_*.json"))):
        base = os.path.basename(f)
        tag = base.split("_")[1]
        if tag.endswith("bridge") or "bridge" in base:
            continue                      # the weekend bridge is not a day posterior
        d = json.load(open(f))
        # S110 (found by specialist E-0717 before any gate saw it): the shared output contract is
        # read two ways in practice - a FLAT day record, or a {days:[...]} wrapper carrying one day
        # (the per-specialist shape). Both are legitimate readings of the same contract, so the JOIN
        # normalizes rather than rejecting: a single-day wrapper is unwrapped, a multi-day wrapper in
        # a per-DAY file is still an error. Fixing the tool, not the posteriors - the posteriors are
        # the record and must not be edited to suit a reader.
        if not d.get("date") and isinstance(d.get("days"), list):
            if len(d["days"]) != 1:
                errs.append(f"{base}: days[] carries {len(d['days'])} days in a per-day file"); continue
            inner = d["days"][0]
            d = {**{k: v for k, v in d.items() if k != "days"}, **inner}
        day = str(d.get("date", "")).replace("-", "")
        if not day:
            errs.append(f"{base}: no date"); continue
        if owner.get(day) != tag:
            errs.append(f"{base}: filed under {tag} but {day} is owned by {owner.get(day)}"); continue
        by_tag.setdefault(tag, []).append(d)
    for day, o in owner.items():
        if not any(str(x.get("date")) == day for x in by_tag.get(o, [])):
            errs.append(f"{day}: owner {o} posterior MISSING")
    if errs:
        raise SystemExit("MERGE GUARD FAILED:\n  " + "\n  ".join(errs))
    for tag, days in by_tag.items():
        days.sort(key=lambda x: x["date"])
        out = os.path.join(FC, f"grp{n}_mbo_specialist_{tag}.json")
        json.dump({"specialist": tag, "group": gid, "days": days}, open(out, "w"), indent=1)
        print(f"  {tag}: {len(days)} day(s) -> {os.path.basename(out)}  {[x['date'] for x in days]}")
    print(f"[merge] {gid}: {sum(len(v) for v in by_tag.values())}/{len(owner)} days assembled")

if __name__ == "__main__":
    main(*(sys.argv[1:] or ["g22"]))
