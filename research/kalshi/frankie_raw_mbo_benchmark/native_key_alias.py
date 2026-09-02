"""Key-name aliasing for the averaged companion rows, and the measurement that scopes it.

D67 concluded that aliasing saves essentially nothing. That is TRUE of the ledgers, where
`book_full` is one enormous nested value and swamps every name around it, and it is FALSE
of the averaged companions, which are the opposite shape: many short values, few distinct
names, hundreds of thousands of repetitions. Measured on run 33605852433 - the complete
Sunday session - key names are 49.5% of the section's 20,023,101 compact bytes and 1-2
character aliasing removes 33.8% of it, about 1.69M tokens.

**Storage and tokens are different questions.** Nothing here changes the disk conversation.
It changes what the principal is handed.

Three properties this module exists to hold, because an aliaser that has any of them wrong
is worse than none at all:

1. **Lossless.** `expand_aliases(apply_aliases(x, t), t) == x`, and the legend travels in
   the artifact beside the rows, so the mapping is never something a reader has to have.
   Aliasing is a RENAMING, not a drop - D60 is not engaged, and nothing is discarded.
2. **Keys only.** A string value that happens to equal a key name is untouched.
3. **Unambiguous.** A generated code is never also a live key name, or two different
   quantities would share one name and the artifact would still parse.

The gates never see this. They run on the unaliased rows the sections produce; only the
serialized layer is aliased, so `native_cross_section_agreement` and the eight section 6
gates are untouched by design rather than by luck.

The tension worth stating: this branch's standing lesson is that a caveat living only in
prose expires, and every S119 fix put its qualifier ON the value as a field. An alias moves
a name off the value into a legend, which pulls the other way. It is lossless and the legend
is in the same file, but it is a real cost and it is why the aliased form is DECLARED in the
layer rather than being something a reader has to notice.
"""
from __future__ import annotations

import json
import string
from collections import Counter
from typing import Any, Mapping, Sequence

# Codes are drawn from lowercase letters, then two-character combinations. Digits and
# uppercase are deliberately excluded: the vocabulary is lowercase and a code that reads
# like a real name is harder to spot in a diff than one that does not.
_ALPHABET = string.ascii_lowercase

ALIAS_LEGEND_KEY = "key_alias_legend"
ALIAS_FORM_KEY = "key_alias_form"
FORM_ALIASED = "ALIASED"
FORM_PLAIN = "PLAIN"


class AliasError(RuntimeError):
    """Raised when a mapping cannot be applied or reversed without ambiguity."""


def _codes() -> "list[str]":
    """Every 1-character code, then every 2-character one, in a fixed order."""
    single = list(_ALPHABET)
    double = [a + b for a in _ALPHABET for b in _ALPHABET]
    return single + double


def _walk_keys(node: Any, counter: Counter) -> None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            counter[str(key)] += 1
            _walk_keys(value, counter)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _walk_keys(item, counter)


def key_census(rows: Any) -> Counter:
    """Every key name at every depth, with how many times it appears.

    Top-level keys are only 7.0% of the cost. `stratum`, `declaration`, `value` and
    `excluded_missing_members` are objects carrying their own repeated names, and the
    Kaplan-Meier curve alone repeats five names once per time point.
    """
    counter: Counter = Counter()
    _walk_keys(rows, counter)
    return counter


def build_alias_table(rows: Any) -> dict[str, str]:
    """Map each key name to a shorter code, costliest name first.

    Cost is `count * len(name)`, not count: a name repeated 40,000 times saves nothing if
    it is already one character, and a long name repeated 5,000 times can be worth more
    than a short one repeated 40,000. Ties break on the name so the table is deterministic
    for a given set of rows.

    A name is left alone when its code would not be shorter than the name, and a code that
    is also a live key name is skipped rather than issued.
    """
    census = key_census(rows)
    if not census:
        return {}
    live_names = set(census)
    ordered = sorted(census.items(), key=lambda item: (-(item[1] * len(item[0])), item[0]))
    available = [code for code in _codes() if code not in live_names]
    table: dict[str, str] = {}
    index = 0
    for name, _count in ordered:
        if index >= len(available):
            # More distinct names than codes. The rest keep their names: a partial table is
            # still lossless, where reusing a code would not be.
            break
        code = available[index]
        if len(code) >= len(name):
            # The code would not be shorter than the name, so issuing it spends bytes to
            # save none. The code is NOT consumed - the next, longer name can still use it.
            continue
        table[name] = code
        index += 1
    return table


def apply_aliases(node: Any, table: Mapping[str, str]) -> Any:
    """Rename keys, recursively. Values are returned unchanged."""
    if isinstance(node, Mapping):
        return {table.get(str(k), str(k)): apply_aliases(v, table) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [apply_aliases(item, table) for item in node]
    return node


def expand_aliases(node: Any, table: Mapping[str, str]) -> Any:
    """Undo `apply_aliases`. A code the legend does not name is refused, never passed on.

    Passing an unknown code through would hand a consumer a key that is neither an alias
    nor a real name, and it would read as a new field rather than as a broken legend.
    """
    inverse = {code: name for name, code in table.items()}
    if len(inverse) != len(table):
        raise AliasError("the legend maps two names onto one code and cannot be reversed")
    return _expand(node, inverse, set(table))


def _expand(node: Any, inverse: Mapping[str, str], originals: set) -> Any:
    if isinstance(node, Mapping):
        out: dict[str, Any] = {}
        for key, value in node.items():
            name = str(key)
            if name in inverse:
                out[inverse[name]] = _expand(value, inverse, originals)
            elif name in originals:
                # A name that WAS aliased turning up unaliased means the rows and the
                # legend disagree about which form they are in.
                raise AliasError(
                    f"key {name!r} is aliased by this legend but appears unaliased; the "
                    "rows and the legend are not from the same run"
                )
            else:
                out[name] = _expand(value, inverse, originals)
        return out
    if isinstance(node, (list, tuple)):
        return [_expand(item, inverse, originals) for item in node]
    return node


def _compact(node: Any) -> int:
    return len(json.dumps(node, separators=(",", ":"), sort_keys=True))


def measure_key_names(rows: Sequence[Any]) -> dict[str, Any]:
    """What key names cost these rows, and what aliasing them would remove.

    This is the prose measurement made re-runnable. It reports the saving in ACTUAL
    serialized bytes rather than from name lengths alone, so the number cannot drift from
    what the file really loses - which is the same error, in miniature, as measuring a
    compressed artifact and calling it a disk requirement.
    """
    census = key_census(rows)
    table = build_alias_table(rows)
    compact_bytes = _compact(rows)
    # Each key costs its own characters plus the two quotes and the colon that carry it;
    # the quotes and colon do not change under aliasing, so only the name bytes are counted.
    key_name_bytes = sum(len(name) * count for name, count in census.items())
    aliased_key_name_bytes = sum(
        len(table.get(name, name)) * count for name, count in census.items()
    )
    aliased_compact_bytes = _compact(apply_aliases(rows, table))
    return {
        "rows": len(rows),
        "compact_bytes": compact_bytes,
        "aliased_compact_bytes": aliased_compact_bytes,
        "distinct_key_names": len(census),
        "key_instances": sum(census.values()),
        "key_name_bytes": key_name_bytes,
        "aliased_key_name_bytes": aliased_key_name_bytes,
        "saved_bytes": compact_bytes - aliased_compact_bytes,
        "key_name_share": (key_name_bytes / compact_bytes) if compact_bytes else 0.0,
        "saving_share": (
            (compact_bytes - aliased_compact_bytes) / compact_bytes if compact_bytes else 0.0
        ),
        "aliased_name_count": len(table),
        "costliest_names": [
            {"name": name, "instances": count, "bytes": len(name) * count,
             "alias": table.get(name)}
            for name, count in sorted(
                census.items(), key=lambda item: (-(item[1] * len(item[0])), item[0])
            )[:10]
        ],
        "basis": (
            "saved_bytes is the difference between the compact JSON of the rows and of the "
            "aliased rows, not an estimate from name lengths"
        ),
    }


def read_averaged_rows(result: Mapping[str, Any]) -> list[Any]:
    """The averaged companion rows in PLAIN form, whatever form the artifact is in.

    Every consumer must go through this rather than reaching for
    `result["layers"]["averaged_companions"]["rows"]` directly. An aliased row still parses,
    still has the right count, and still passes a presence check - `row.get("section")` just
    returns None on all of them, and a per-section table then reports every row under
    `None`. That is a present, well-formed, wrong input, which is the one shape this branch
    has repeatedly found a field-level check cannot catch.
    """
    layer = result.get("layers", {}).get("averaged_companions", {})
    rows = layer.get("rows", [])
    if layer.get(ALIAS_FORM_KEY) == FORM_ALIASED:
        return expand_aliases(rows, layer.get(ALIAS_LEGEND_KEY) or {})
    return list(rows)


def averaged_companion_layer(
    rows: Sequence[Any], *, alias_keys: bool
) -> dict[str, Any]:
    """Build the layer, DECLARING which form its rows are in either way.

    The form is stamped even when nothing is aliased. A field that appears only in one form
    means its absence has two readings - an old artifact, or a plain one - and the reader
    cannot tell which.
    """
    if not alias_keys:
        return {"rows": list(rows), ALIAS_FORM_KEY: FORM_PLAIN, ALIAS_LEGEND_KEY: {}}
    table = build_alias_table(rows)
    return {
        "rows": apply_aliases(list(rows), table),
        ALIAS_FORM_KEY: FORM_ALIASED,
        ALIAS_LEGEND_KEY: table,
        "key_alias_note": (
            "keys in `rows` are aliased; `key_alias_legend` maps every alias back to its "
            "name and is exhaustive. Nothing is dropped - this is a renaming, and a name "
            "absent from the legend was never aliased."
        ),
    }
