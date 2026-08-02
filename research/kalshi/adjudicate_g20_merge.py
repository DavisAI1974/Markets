"""Adjudicate G20_MERGE_PROPOSAL_S108 against the live brain.

Doctrine: a brain merge is a PROPOSAL FILE + adjudication, never a direct edit, and incumbents must
come out BYTE-IDENTICAL. This checks that mechanically rather than by eye:
  1. every play_id referenced actually exists,
  2. every amendment ADDS a key that does not already exist (no silent rewrite),
  3. simulating the merge leaves all pre-existing keys on all incumbents byte-identical,
  4. new plays do not collide with existing ids.
Read-only unless --write is passed.
"""
import json, os, sys, copy

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
# S108: takes a proposal path so the same adjudication runs on any proposal file, not just G20's.
_paths = [a for a in sys.argv[1:] if not a.startswith("--")]
PROP = _paths[0] if _paths else os.path.join(HERE, "G20_MERGE_PROPOSAL_S108.json")

brain = json.load(open(BRAIN))
prop = json.load(open(PROP))
prop.setdefault("new_plays_proposed", [])
prop.setdefault("data_plane_items_NOT_PLAYS", [])
prop.setdefault("refuted_DO_NOT_BANK", [])
plays = {p["id"]: p for p in brain["plays"]}
fail = []

print(f"brain: {brain['meta'].get('version', '?')}  plays: {len(plays)}")
print(f"proposal: {prop['meta']['proposes']}  "
      f"scope: {prop['meta'].get('scope_decision_greg_s108', prop['meta'].get('merge_rule', ''))[:90]}\n")

print("=== 1. amendments: id exists, key is NEW (additive, no rewrite) ===")
for a in prop["amendments_to_incumbents"]:
    pid, field = a["play_id"], a["add_field"]
    if pid not in plays:
        fail.append(f"amendment targets missing play {pid}"); print(f"  MISSING PLAY  {pid}"); continue
    clash = field in plays[pid]
    if clash:
        fail.append(f"{pid}.{field} ALREADY EXISTS - would rewrite an incumbent")
    print(f"  {'CLASH ' if clash else 'ok    '} {pid:58} + {field}")

print("\n=== 2. new plays do not collide ===")
for np_ in prop["new_plays_proposed"]:
    clash = np_["id"] in plays
    if clash:
        fail.append(f"new play {np_['id']} collides with an incumbent")
    print(f"  {'CLASH ' if clash else 'ok    '} {np_['id']:58} n={np_.get('n', '-')} {np_.get('status','')[:34]}")

print("\n=== 3. simulate the merge, then diff every incumbent key-by-key ===")
merged = copy.deepcopy(brain)
mplays = {p["id"]: p for p in merged["plays"]}
for a in prop["amendments_to_incumbents"]:
    if a["play_id"] in mplays:
        mplays[a["play_id"]][a["add_field"]] = a["value"]
for np_ in prop["new_plays_proposed"]:
    merged["plays"].append({k: v for k, v in np_.items()})

touched, identical = set(a["play_id"] for a in prop["amendments_to_incumbents"]), 0
for pid, orig in plays.items():
    new = mplays[pid]
    for k, v in orig.items():
        if json.dumps(new.get(k), sort_keys=True) != json.dumps(v, sort_keys=True):
            fail.append(f"{pid}.{k} MUTATED - incumbent not byte-identical")
    if json.dumps(orig, sort_keys=True) == json.dumps(new, sort_keys=True):
        identical += 1
print(f"  incumbents byte-identical (untouched): {identical}/{len(plays)}")
print(f"  incumbents with keys ADDED only:       {len(touched)}")
print(f"  every pre-existing key preserved:      {'YES' if not [f for f in fail if 'MUTATED' in f] else 'NO'}")

print("\n=== 4. non-play sections unchanged ===")
for sec in brain:
    if sec == "plays":
        continue
    same = json.dumps(brain[sec], sort_keys=True) == json.dumps(merged[sec], sort_keys=True)
    if not same:
        fail.append(f"non-play section {sec} changed")
    print(f"  {'ok    ' if same else 'CHANGED'} {sec}")

print(f"\n=== 5. discipline checks ===")
dp = prop["data_plane_items_NOT_PLAYS"]
rf = prop["refuted_DO_NOT_BANK"]
print(f"  data-plane items kept OUT of plays: {len(dp)}")
print(f"  refuted claims recorded:            {len(rf)}")
print(f"  new plays, all marked PROPOSED:     "
      f"{sum(1 for n in prop['new_plays_proposed'] if 'PROPOSED' in n.get('status',''))}"
      f"/{len(prop['new_plays_proposed'])}")
weather = json.dumps(prop).lower().count("weather earned nothing")
print(f"  weather recorded as earning nothing: {'YES' if weather else 'NO'}")

print("\n" + "=" * 72)
if fail:
    print(f"ADJUDICATION FAILED - {len(fail)} problem(s):")
    for f in fail:
        print("  -", f)
    sys.exit(1)
print(f"ADJUDICATION PASSED. Strictly additive: {len(touched)} incumbents gain keys, "
      f"{identical} untouched and byte-identical, 0 pre-existing keys mutated, "
      f"{len(prop['new_plays_proposed'])} new plays -> {len(plays)}+{len(prop['new_plays_proposed'])} "
      f"= {len(plays) + len(prop['new_plays_proposed'])} plays.")

if "--write" in sys.argv:
    # S110: backup name derives from the LIVE version (was hardcoded to the S108 vintage - a
    # second run would have silently skipped the backup because the stale name already existed).
    bak = os.path.join(HERE, "knowledge", f"ng_brain_{brain['meta'].get('version', 'unknown')}_backup.json")
    if not os.path.exists(bak):
        json.dump(brain, open(bak, "w"), indent=1)
        print(f"backup -> {os.path.relpath(bak, HERE)}")
    merged["meta"]["version"] = prop["meta"]["proposes"]
    json.dump(merged, open(BRAIN, "w"), indent=1)
    print(f"MERGED -> {prop['meta']['proposes']} ({len(merged['plays'])} plays)")
else:
    print("DRY RUN - no brain edit. Pass --write to merge (Greg's go only).")
