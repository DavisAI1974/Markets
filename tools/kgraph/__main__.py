"""python3 -m tools.kgraph check | counts | manifest   (on the graph in a markets-data checkout)

check     every breach of a write rule in the stored graph, one line each (none: prints "no breach")
counts    how many nodes and links of each type, and how many lines in all
manifest  write graph/MANIFEST.json again from the files (after a merge of two writers' lines)
"""

import argparse
import json
import sys

from .store import GraphStore


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("verb", choices=("check", "counts", "manifest"))
    ap.add_argument("--data")
    ap.add_argument("--graph-dir")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    if a.verb == "check":
        breaches = store.check_all()
        print("\n".join(breaches) if breaches else "no breach")
        return 1 if breaches else 0
    if a.verb == "counts":
        print(json.dumps(store.counts(), indent=1))
    else:
        print(store.write_manifest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
