"""Independently recount the retained dipole direction cells and adjust for base rates."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

from scipy.stats import spearmanr

from audit_october18_touch_mechanisms import git_blob

REVISION = "6787252c7"
ROOT = "tasks/family-research-20261022/claude-code"
SOURCES = ("pol", "next_state", "next_seed", "dip300", "dip300_strong", "book10", "touch", "recruit", "mom300")
TARGETS = ("net300", "net600", "first3")


def load(file):
    return [json.loads(line) for line in gzip.decompress(git_blob(REVISION, f"{ROOT}/{file}")).splitlines()]


def score(rows, source, target):
    by_hour = defaultdict(Counter)
    whole = Counter()
    for row in rows:
        call, move = row["sources"].get(source), row["targets"][target]
        if call not in (-1, 1):
            whole["no_call"] += 1
        elif move is None:
            whole["unavailable"] += 1
        elif move == 0:
            whole["flat"] += 1
        else:
            direction = 1 if move > 0 else -1
            cell = (call, direction)
            whole[cell] += 1
            # The saved hour describes t0. The prediction anchor is t0+60 seconds.
            anchor_hour = (row["hour_utc"] + (row["t0"] % 3600 + 60)//3600) % 24
            by_hour[anchor_hour][cell] += 1

    def margins(table):
        uu, ud, du, dd = (table[c] for c in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
        n = uu + ud + du + dd
        expected = ((uu+ud)*(uu+du)+(du+dd)*(ud+dd))/n if n else 0
        return n, uu+dd, expected

    n, hits, expected = margins(whole)
    if n < 30:
        return None
    return dict(
        n=n, hits=hits, flat=whole["flat"], unavailable=whole["unavailable"], no_call=whole["no_call"],
        hit=hits/n, expected_with_cell_margins=expected/n,
        lift_cell=(hits-expected)/n,
        lift_after_hour_margins=(hits-sum(margins(bucket)[2] for bucket in by_hour.values()))/n,
        call_up_outcome_up=whole[(1, 1)], call_up_outcome_down=whole[(1, -1)],
        call_down_outcome_up=whole[(-1, 1)], call_down_outcome_down=whole[(-1, -1)],
    )


def cells(rows, cuts=None):
    groups = defaultdict(list)
    for row in rows:
        volume = row["pre300_volume"]
        tercile = row["vol_tercile"] if cuts is None else "low" if volume <= cuts[0] else "mid" if volume <= cuts[1] else "high"
        state = row["a_state"]
        for key in ("all", f"a_state={state}", f"vol_tercile={tercile}",
                    f"state_x_tercile={state}|{tercile}", f"hour_class={row['hour_class']}"):
            groups[key].append(row)
    return {
        f"{key}|{source}|{target}": result
        for key, bucket in groups.items()
        for source in SOURCES
        for target in TARGETS
        if (result := score(bucket, source, target)) is not None
    }


def compare(day18, day17):
    common = sorted(day18.keys() & day17.keys())
    raw = [dict(cell=k, oct18=day18[k], oct17=day17[k]) for k in common]
    cross = {}
    for metric, pivot in (("hit", 0.5), ("lift_cell", 0), ("lift_after_hour_margins", 0)):
        first = [r["oct18"][metric]-pivot for r in raw]
        second = [r["oct17"][metric]-pivot for r in raw]
        cross[metric] = dict(
            same_sign=sum(x*y > 0 for x, y in zip(first, second)),
            flips=sum(x*y < 0 for x, y in zip(first, second)),
            ties=sum(x*y == 0 for x, y in zip(first, second)),
            rank_correlation=float(spearmanr(first, second).statistic),
        )
    watched = [
        row["cell"] for row in raw
        if abs(round(row["oct18"]["hit"], 3)-0.5) >= 0.06
        and abs(round(row["oct17"]["hit"], 3)-0.5) >= 0.06
        and (row["oct18"]["hit"]-0.5)*(row["oct17"]["hit"]-0.5) > 0
    ]
    return dict(common=len(common), agreement=cross, raw_six_point_screen=watched, cells=raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    oct18 = load("stack-direction-sources-oct18-events.jsonl.gz")
    full = load("stack-direction-sources-oct17-events.jsonl.gz")
    partial = load("no-prefix-oct17/stack-direction-sources-oct17-events.jsonl.gz")
    vols = sorted(row["pre300_volume"] for row in oct18)
    cuts = (vols[len(vols)//3], vols[2*len(vols)//3])
    out = dict(
        revision=REVISION, counts=dict(oct18=len(oct18), oct17_partial=len(partial), oct17_full=len(full)),
        original_partial=compare(cells(oct18), cells(partial)),
        full_oct17=compare(cells(oct18), cells(full)),
        full_common_oct18_activity_cuts=compare(cells(oct18, cuts), cells(full, cuts)),
        common_cuts=cuts,
        note="Margins use the realized outcome balance on eligible decided rows for diagnosis. They are not forecasts.",
    )
    output.write_bytes(gzip.compress((json.dumps(out, sort_keys=True)+"\n").encode(), mtime=0))
    for variant in ("original_partial", "full_oct17", "full_common_oct18_activity_cuts"):
        v = out[variant]
        print(variant, v["common"], v["agreement"], len(v["raw_six_point_screen"]))
        for row in v["cells"]:
            if row["cell"] in (
                "state_x_tercile=A-fast-collapse|mid|book10|net300",
                "state_x_tercile=A-fast-collapse|mid|next_seed|net300",
                "state_x_tercile=A-fast-collapse|high|book10|net600",
                "vol_tercile=mid|dip300_strong|net300",
                "a_state=A-persistent|pol|net300",
            ):
                print(row)


if __name__ == "__main__":
    main()
