#!/usr/bin/env python3
"""Protocol-corrected exact-D1 runner.

The frozen Phase-1 lineage is out-of-time by construction and begins at base week
index 18. Therefore the original first 18 Phase-1 training weeks have no honest
exact-D1 labels. This wrapper preserves the frozen lineage and reassigns chronology
only for the post-Phase-2 D1 characterization:

- base weeks 0..17: PRELINEAGE_UNLABELED (never used as D1 negatives or fitting rows)
- base weeks 18..35: internal `train` = D1 DISCOVERY/FIT block
- base weeks 36..47: `era45` validation
- base weeks 48..53: `conf` untouched historical confirmation
- 20260329: held insert-only validation

The internal name `train` is retained only to reuse the already-written D1 lane
functions. Output metadata makes clear that it means D1_DISCOVERY_OOT, not the
original Phase-1 model-training block. No detector, canonical row, lineage score,
runway clock, Frankie component, or frozen play is changed.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import ng_exhaustion_exact_d1_agents_20260818 as _base


def d1_block_for(week, weeks):
    if week == '20260329':
        return 'held'
    i = weeks.index(week)
    if i < 18:
        return 'prelineage_unlabeled'
    if i < 36:
        return 'train'   # D1 discovery/fitting block; first genuinely OOT lineage weeks
    if i < 48:
        return 'era45'
    return 'conf'


_base.block_for = d1_block_for


def __getattr__(name):
    return getattr(_base, name)


def _out_arg(argv):
    try:
        i = argv.index('--out')
        return argv[i + 1]
    except Exception:
        return None


def main():
    _base.main()
    p = _out_arg(sys.argv)
    if not p or not Path(p).exists():
        return
    d = json.loads(Path(p).read_text())
    d['d1_chronological_protocol'] = {
        'status': 'D1_OOT_LABEL_BOUNDARY_CORRECTED',
        'phase1_base_weeks_0_17': 'PRELINEAGE_UNLABELED_NOT_USED_FOR_D1_FIT_OR_AS_NEGATIVES',
        'internal_train_field_semantics': 'D1_DISCOVERY_OOT_BASE_WEEKS_18_35',
        'validation_era45': 'BASE_WEEKS_36_47',
        'untouched_confirmation': 'BASE_WEEKS_48_53',
        'held': '20260329_INSERT_ONLY',
        'reason': 'Frozen Phase-1 lineage labels exist only for OOT test folds beginning at week index 18; no in-sample D1 labels are manufactured.'
    }
    Path(p).write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
