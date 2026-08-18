#!/usr/bin/env python3
"""Protocol-preserving wrapper for the post-Phase-2 agent runner.

Named context candidates retain the structural orientation finalized in Phase 2.
New/systematic motifs and pair/triplet execution hypotheses still fix orientation
from the first 18 train weeks. This prevents the continuation study from
re-selecting and thereby re-litigating already-characterized Phase-2 context signs.
"""
import ng_exhaustion_chain_postphase2_agents_20260818 as base

FIXED_CONTEXT_ORIENTATION = {
    'OOSS->FLIP': -1,
    'SOOS->SAME': 1,
    'OOO->SAME': -1,
    'XSX->FLIP': -1,
    'OSP->SAME': 1,
    'OSP->FLIP': 1,
    'PSOS->FLIP': 1,
    'SXOO->FLIP': 1,
    'O->FLIP': 1,
    'P->FLIP': 1,
    'OOO->FLIP': 1,
    'POX->SAME': 1,
}

_original_train_orientation = base.train_orientation

def protocol_orientation(recs):
    if recs and recs[0].get('kind') == 'context':
        p = recs[0].get('pattern')
        if p in FIXED_CONTEXT_ORIENTATION:
            return FIXED_CONTEXT_ORIENTATION[p]
    return _original_train_orientation(recs)

base.train_orientation = protocol_orientation

if __name__ == '__main__':
    base.main()
