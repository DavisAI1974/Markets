#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

PAIR_SEEDS = ('PP|S','PO|S','OO|F','OP|F','XP|F','SS|S','PP|F','XP|S')
TRIPLET_SEEDS = ('PPP|SS','PPX|SS','OOO|FF','PPS|SS','POP|SF')

PHASE2_CONTEXT = {
    'OOSS->FLIP': {'orientation':'AGAINST_CURRENT','role':'INDEPENDENT_HIGHER_SUPPORT_CANDIDATE_QUEUE'},
    'SOOS->SAME': {'orientation':'WITH_CURRENT','role':'INDEPENDENT_HIGHER_SUPPORT_CANDIDATE_QUEUE'},
    'OOO->SAME': {'orientation':'AGAINST_CURRENT','role':'INDEPENDENT_HIGHER_SUPPORT_CANDIDATE_QUEUE'},
    'XSX->FLIP': {'orientation':'AGAINST_CURRENT','role':'INDEPENDENT_HIGHER_SUPPORT_CANDIDATE_QUEUE'},
    'OSP->SAME': {'orientation':'WITH_CURRENT','role':'INDEPENDENT_HIGHER_MAGNITUDE_SPARSE_CANDIDATE_QUEUE'},
    'OSP->FLIP': {'orientation':'WITH_CURRENT','role':'INDEPENDENT_HIGHER_MAGNITUDE_SPARSE_CANDIDATE_QUEUE'},
    'PSOS->FLIP': {'orientation':'WITH_CURRENT','role':'INDEPENDENT_HIGHER_MAGNITUDE_SPARSE_CANDIDATE_QUEUE'},
    'SXOO->FLIP': {'orientation':'WITH_CURRENT','role':'INDEPENDENT_HIGHER_MAGNITUDE_SPARSE_CANDIDATE_QUEUE'},
    'O->FLIP': {'orientation':'WITH_CURRENT','role':'PHASE2_SIGN_CHANGING_INVESTIGATOR'},
    'P->FLIP': {'orientation':'WITH_CURRENT','role':'PHASE2_SIGN_CHANGING_INVESTIGATOR'},
    'OOO->FLIP': {'orientation':'WITH_CURRENT','role':'PHASE2_SIGN_CHANGING_INVESTIGATOR'},
    'POX->SAME': {'orientation':'WITH_CURRENT','role':'PHASE2_SIGN_CHANGING_INVESTIGATOR_AND_DELAYED_REEXPRESSION_THREAD'},
}

KNOWN_OVERLAP = {
    'POX->FLIP': 'KNOWN_POX_OPPOSITE_ZERO_UNIQUE_AFTER_KNOWN_SETUP_REMOVAL',
    'SOS->FLIP': 'SSOS_OVERLAP_REMOVAL_LOSES_STABLE_CONFIRMATION',
}

PROTECTED = {
    'detector': False,
    'canonical_rows': False,
    'runway_clock': False,
    'permanent_frankie': False,
    'frankie_1': False,
    'spawn_py': False,
    'ssos_play': False,
}


def load_json(path: str):
    return json.loads(Path(path).read_text())


def load_text(path: str):
    return Path(path).read_text()


def result_list(path: str):
    d = load_json(path)
    r = d.get('result')
    if isinstance(r, list):
        return r
    return []


def index_patterns(rows):
    out = {}
    for r in rows:
        p = r.get('pattern')
        if p:
            out[p] = r
    return out


def systematic_index(path: str):
    d = load_json(path)
    r = d.get('result') or {}
    rows = r.get('candidates') or []
    return {x['pattern']: x for x in rows if x.get('pattern')}, d


def compact_blocks(row):
    if not row:
        return None
    blocks = row.get('blocks') or row.get('outcome_blocks') or {}
    out = {}
    for b in ('train','era13','era45','conf','held'):
        z = blocks.get(b)
        if not z:
            continue
        out[b] = {
            'n': z.get('n'),
            'mean_oriented_ticks': z.get('mean_oriented_ticks'),
            'week_demeaned_mean_ticks': z.get('week_demeaned_mean_ticks'),
            'positive_rate': z.get('positive_rate'),
        }
    return out


def classify(pattern, exec_row, red_row, systematic_row):
    if pattern in KNOWN_OVERLAP:
        return 'DUPLICATE_OR_OVERLAP_NOT_NEW_REQUIRES_PHASE2_NOVELTY_BOUNDARY'
    if pattern in PAIR_SEEDS or pattern in TRIPLET_SEEDS:
        return 'NEW_EXECUTION_HYPOTHESIS_ON_PHASE2_STRUCTURAL_MODULE_PROSPECTIVE_REQUIRED'
    meta = PHASE2_CONTEXT.get(pattern)
    if not meta:
        return 'SYSTEMATIC_ONLY_NEW_MOTIF_HISTORICAL_RESEARCH_PROSPECTIVE_REQUIRED'
    new_orientation = (exec_row or {}).get('orientation')
    if new_orientation and new_orientation != meta['orientation']:
        return 'METHODOLOGY_OR_SIGN_CONVENTION_MISMATCH_BLOCKED_NOT_PHASE2_CONTRADICTION'
    if pattern == 'POX->SAME':
        return 'PHASE2_INVESTIGATOR_DELAYED_REEXPRESSION_THREAD_DIRECT_TRADE_BLOCKED'
    if meta['role'] == 'PHASE2_SIGN_CHANGING_INVESTIGATOR':
        held = (red_row or {}).get('held_mean')
        min_oot = (red_row or {}).get('min_oot_block_mean')
        if held is not None and min_oot is not None and min_oot > 0 and held < 0:
            return 'CONFIRMS_PHASE2_SIGN_CHANGE_DEEPER_DECOMPOSITION_REQUIRED'
        return 'PHASE2_INVESTIGATOR_CONTINUES_FLAG_AND_DECOMPOSE'
    return 'CONSISTENT_EXTENSION_OF_PHASE2_CANDIDATE_PROSPECTIVE_REQUIRED'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase2-freeze', required=True)
    ap.add_argument('--phase2-all', required=True)
    ap.add_argument('--phase2-index', required=True)
    ap.add_argument('--phase2-proposal', required=True)
    ap.add_argument('--continuation', required=True)
    ap.add_argument('--decompose', required=True)
    ap.add_argument('--execution', required=True)
    ap.add_argument('--redteam', required=True)
    ap.add_argument('--causality', required=True)
    ap.add_argument('--systematic', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--out-md', required=True)
    a = ap.parse_args()

    freeze = load_text(a.phase2_freeze)
    all_agent = load_text(a.phase2_all)
    index = load_text(a.phase2_index)
    proposal = load_json(a.phase2_proposal)

    assertions = {
        'phase2_finalized': 'PHASE-2 CHARACTERIZATION FINALIZED' in freeze,
        'flag_and_decompose_present': 'FLAG_AND_DECOMPOSE' in all_agent,
        'pox_flip_overlap_present': 'POX -> FLIP' in all_agent and 'zero unique' in all_agent,
        'sos_flip_overlap_present': 'SOS -> FLIP' in all_agent and 'loses stable confirmation' in all_agent,
        'proposal_extends_parent': 'EXTENDS' in json.dumps(proposal) and 'DOES_NOT_REPLACE' in json.dumps(proposal),
        'permanent_frankie_unchanged': 'permanent Frankie remains unchanged' in index,
    }
    if not all(assertions.values()):
        raise SystemExit('Phase-2 authoritative assertion failed: ' + json.dumps(assertions, sort_keys=True))

    cont = index_patterns(result_list(a.continuation))
    decomp = index_patterns(result_list(a.decompose))
    exe = index_patterns(result_list(a.execution))
    red = index_patterns(result_list(a.redteam))
    causal = index_patterns(result_list(a.causality))
    systematic, systematic_raw = systematic_index(a.systematic)

    seeded = list(PAIR_SEEDS) + list(TRIPLET_SEEDS) + list(PHASE2_CONTEXT)
    records = []
    violations = []

    for p in seeded:
        phase2 = None
        if p in PAIR_SEEDS:
            phase2 = {'role':'PHASE2_RECURRING_PAIR_STRUCTURAL_ONLY','orientation':None}
        elif p in TRIPLET_SEEDS:
            phase2 = {'role':'PHASE2_RECURRING_TRIPLET_STRUCTURAL_ONLY','orientation':None}
        else:
            phase2 = PHASE2_CONTEXT[p]
        er = exe.get(p)
        rr = red.get(p)
        sr = systematic.get(p)
        cr = causal.get(p)
        cls = classify(p, er, rr, sr)
        if cls.startswith('METHODOLOGY_OR_SIGN'):
            violations.append({'pattern':p,'type':'SEEDED_ORIENTATION_MISMATCH','phase2_orientation':phase2.get('orientation'),'new_orientation':(er or {}).get('orientation')})
        if cr and cr.get('causal_contract_passed_all_occurrences') is not True:
            violations.append({'pattern':p,'type':'CAUSAL_CONTRACT_FAILURE'})
        sys_cross = None
        if sr:
            sys_cross = {
                'orientation': sr.get('orientation'),
                'eligible': sr.get('eligible'),
                'stable_preheld_oot': sr.get('stable_preheld_oot'),
                'oot_week_sign_q_bh': sr.get('oot_week_sign_q_bh'),
            }
            if phase2.get('orientation') and sr.get('orientation') and sr.get('orientation') != phase2['orientation']:
                sys_cross['interpretation'] = 'TRAIN_FIXED_SYSTEMATIC_DIRECTION_DIFFERS_FROM_FROZEN_PHASE2_CONTEXT; METHODOLOGICAL_RESELECTION_ONLY; DO_NOT_TREAT_AS_PHASE2_CONTRADICTION'
            elif phase2.get('orientation'):
                sys_cross['interpretation'] = 'SYSTEMATIC_DIRECTION_AGREES_WITH_FROZEN_PHASE2_CONTEXT'
        records.append({
            'pattern': p,
            'phase2_role': phase2['role'],
            'phase2_orientation': phase2.get('orientation'),
            'postphase2_execution_orientation': (er or {}).get('orientation'),
            'classification': cls,
            'causal_contract_passed_all_occurrences': (cr or {}).get('causal_contract_passed_all_occurrences'),
            'execution_blocks': compact_blocks(er),
            'redteam': None if not rr else {
                'min_oot_block_mean': rr.get('min_oot_block_mean'),
                'held_mean': rr.get('held_mean'),
                'leave_one_week_out_min_mean': rr.get('leave_one_week_out_min_mean'),
                'positive_oot_week_fraction': rr.get('positive_oot_week_fraction'),
                'max_abs_week_contribution_share': rr.get('max_abs_week_contribution_share'),
                'policy': rr.get('policy'),
            },
            'decomposition_present': p in decomp,
            'continuation_present': p in cont,
            'systematic_crosscheck': sys_cross,
        })

    overlap_records = []
    for p, reason in KNOWN_OVERLAP.items():
        sr = systematic.get(p)
        overlap_records.append({
            'pattern': p,
            'phase2_overlap_reason': reason,
            'present_in_systematic_atlas': sr is not None,
            'systematic_orientation': None if sr is None else sr.get('orientation'),
            'systematic_eligible': None if sr is None else sr.get('eligible'),
            'systematic_stable_preheld_oot': None if sr is None else sr.get('stable_preheld_oot'),
            'systematic_oot_week_sign_q_bh': None if sr is None else sr.get('oot_week_sign_q_bh'),
            'classification': 'NOT_NEW_AND_NOT_PROMOTABLE_FROM_BROAD_ATLAS_WITHOUT_PHASE2_OVERLAP_ADJUDICATION',
        })

    class_counts = Counter(r['classification'] for r in records)
    systematic_mismatch = [r['pattern'] for r in records if r.get('systematic_crosscheck',{}).get('interpretation','').startswith('TRAIN_FIXED_SYSTEMATIC_DIRECTION_DIFFERS')]

    out = {
        'status':'POST_PHASE2_PHASE2_CROSSWALK_AGENT_COMPLETE',
        'mode':'phase2_crosswalk',
        'phase2_policy':'AUTHORITATIVE_FREEZE_CROSSWALK_ONLY_DO_NOT_REOPEN_OR_RESELECT',
        'authoritative_assertions': assertions,
        'classification_counts': dict(class_counts),
        'records': records,
        'known_overlap_records': overlap_records,
        'systematic_train_direction_mismatches_vs_frozen_phase2_context': systematic_mismatch,
        'protocol_violations': violations,
        'promotion_performed': False,
        'brain_merge_performed': False,
        'prospective_boundary':'No candidate is frozen from the historically surfaced 55-week evidence; surviving trade hypotheses require a fresh prospective/OOT contract.',
        'brain_implications': [
            'Phase-2 context orientation/status remains authoritative when a named Phase-2 context is revisited.',
            'A train-fixed systematic orientation disagreement with a frozen Phase-2 context is a methodology/sign-selection mismatch, not evidence that Phase 2 should be rewritten.',
            'Pair/triplet recurrence remains structural; post-Phase-2 execution direction is a separate hypothesis requiring prospective validation.',
            'Sign-changing investigator failures remain information to decompose, never rows to delete.',
            'POX->FLIP is the known P-O-X-opposite mechanism, not a new recurrence module.',
            'SOS->FLIP requires SSOS overlap adjudication and cannot graduate from the broad atlas alone.',
            'POX->SAME remains a delayed-reexpression/investigator thread and does not become an automatic direct trade.',
        ],
        'protected_mutations': PROTECTED,
        'systematic_candidate_count': (systematic_raw.get('result') or {}).get('candidate_count'),
        'systematic_stable_count': (systematic_raw.get('result') or {}).get('stable_count'),
    }
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')

    lines = [
        '# NG Exhaustion Post-Phase-2 — Phase-2 Reconciliation Crosswalk — 2026-08-18',
        '',
        'Status: **CROSSWALK COMPLETE; PHASE 2 NOT REOPENED; NO PLAY PROMOTED; PERMANENT FRANKIE UNCHANGED.**',
        '',
        'This ninth lane rereads Phase 2 as immutable truth and reconciles the post-Phase-2 agents against it. It does not recompute or reselect Phase-2 findings.',
        '',
        '## Core conclusions',
        '',
        '- Named Phase-2 context orientations remain authoritative; a different train-fixed direction from the broad systematic atlas is a methodological reselection, not a Phase-2 contradiction.',
        '- Pair/triplet recurrence was structural in Phase 2. Any new execution direction attached to those modules is a separate historical strategy hypothesis and still requires fresh prospective/OOT evidence.',
        '- `POX->FLIP` is the already-known P-O-X-opposite mechanism, not a new motif.',
        '- `SOS->FLIP` cannot be promoted from the broad atlas without the SSOS-overlap adjudication that caused it to lose stable confirmation in Phase 2.',
        '- `POX->SAME` remains an investigator/delayed-reexpression thread; it is not converted into an automatic direct trade.',
        '- True/false cases remain under `FLAG_AND_DECOMPOSE`, never delete-to-improve.',
        '',
        '## Seeded crosswalk',
        '',
        '| Pattern | Phase-2 role | Frozen orientation | New execution orientation | Crosswalk classification |',
        '|---|---|---|---|---|',
    ]
    for r in records:
        lines.append(f"| `{r['pattern']}` | {r['phase2_role']} | {r['phase2_orientation'] or 'not frozen as trade direction'} | {r['postphase2_execution_orientation'] or 'n/a'} | {r['classification']} |")
    lines += ['', '## Known overlap sanity checks', '']
    for r in overlap_records:
        lines.append(f"- `{r['pattern']}`: {r['phase2_overlap_reason']}; systematic-atlas presence={r['present_in_systematic_atlas']}. **Not new / not promotable from the broad atlas alone.**")
    lines += ['', '## Systematic-direction mismatches', '']
    if systematic_mismatch:
        lines.append('These named Phase-2 contexts received a different direction when the systematic lane independently fixed direction from the first 18 train weeks: ' + ', '.join(f'`{p}`' for p in systematic_mismatch) + '. Those differences are retained as methodology diagnostics only; they do not rewrite Phase 2.')
    else:
        lines.append('No named Phase-2 context had a train-fixed systematic direction mismatch in the current outputs.')
    lines += ['', '## Promotion boundary', '', 'No candidate is frozen here. Surviving strategy hypotheses remain historical and require a fresh prospective/OOT promotion contract. Permanent Frankie, Frankie 1, the detector, canonical evidence, runway clock, `spawn.py`, and the frozen SSOS paper play remain unchanged.', '']
    Path(a.out_md).write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
