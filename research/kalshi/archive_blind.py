"""archive_blind.py - move the blind's posteriors out of the refine's filenames (S108).

THE COLLISION, three occurrences across two groups. Blind and refine run the IDENTICAL rule files, so
both write `grp<N>_mbo_specialist_<X>.json`. Before a refine, the blind's five files must be archived -
and every time this was done by hand with `cp`, the blind copies stayed at the canonical names. Every
guard then passed on them: file present, day present, magnitude numeric, owner correct. All true of a
stale blind file.

On G21 that put SIX OF TEN days one command away from being assembled as the refine (B's refine never
wrote because its agent died; C wrote to a slipped name). Nothing downstream could tell - only a sha256
against the archive.

Two defences, and they are deliberately different in kind:
  1. THIS SCRIPT: archive by MOVE. The canonical name is left ABSENT, so a specialist that fails to
     write produces a HARD guard failure ("owner posterior missing") instead of a silent blind read.
  2. group_coordinate_refine.assert_not_the_blind(): hashes any round-1 posterior against its blind
     archive and refuses a byte-identical match. Catches the case where someone re-copies by hand.

Usage:
    python research/kalshi/archive_blind.py g22          # after the blind is coordinated and committed
    python research/kalshi/archive_blind.py g22 --check  # report only, move nothing
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
TAGS = ("A", "B", "C", "D", "E")


def archive(gid: str, check_only: bool = False) -> int:
    n = gid[1:]
    dest = os.path.join(FC, f"g{n}_blind_round1")
    blind_assembled = os.path.join(FC, f"grp{n}.json")
    if not os.path.exists(blind_assembled):
        raise SystemExit(f"{gid}: forecasts/grp{n}.json does not exist - the blind has not been "
                         f"coordinated yet. Archive only AFTER the blind is scored and committed, or "
                         f"the blind's own numbers are lost.")
    os.makedirs(dest, exist_ok=True)
    moved = 0
    for t in TAGS:
        src = os.path.join(FC, f"grp{n}_mbo_specialist_{t}.json")
        dst = os.path.join(dest, f"grp{n}_mbo_specialist_{t}.json")
        if not os.path.exists(src):
            print(f"  {t}: canonical name already clear")
            continue
        if check_only:
            print(f"  {t}: WOULD MOVE -> {os.path.relpath(dst, FC)}")
            continue
        shutil.move(src, dst)          # MOVE, never copy - see the module docstring
        moved += 1
        print(f"  {t}: moved -> {os.path.relpath(dst, FC)}")
    if not check_only:
        left = [t for t in TAGS if os.path.exists(os.path.join(FC, f"grp{n}_mbo_specialist_{t}.json"))]
        if left:
            raise SystemExit(f"{gid}: canonical names still occupied for {left} - archive did not complete")
        print(f"[archive_blind] {gid}: {moved} moved. Canonical names are CLEAR - a specialist that "
              f"fails to write will now hard-fail the guard instead of serving blind numbers.")
    return moved


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("usage: archive_blind.py <gid> [--check]")
    for gid in args:
        print(f"=== {gid} ===")
        archive(gid, check_only="--check" in sys.argv)
