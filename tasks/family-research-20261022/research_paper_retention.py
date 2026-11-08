"""Index prior and new hypotheses without performance-based admission filters."""
import hashlib
import json
import re
import subprocess

import pandas as pd

from research_atlas_continuous import HERE, ATLAS, OUT, EVIDENCE_REV


def pinned_text(name):
    path = 'tasks/family-research-20261022/' + name
    return subprocess.check_output(['git', 'show', f'{EVIDENCE_REV}:{path}']).decode('utf-8')


def build_register():
    register = []

    def add(ident, kind, definition, source, evidence):
        register.append(dict(hypothesis_id=ident, version=1, kind=kind, definition=definition,
            source=source, retained_evidence=evidence, paper_disposition='retain_for_more_days',
            execution_status='not_configured_or_executed',
            execution_contract=dict(trigger=None, side=None, order_type=None, size=None,
                                    exit=None, simulator_environment=None)))

    method = json.loads(pinned_text('research-atlas-v2/stack-method.json'))
    for arm, layers in method['arms'].items():
        add('NG-STACK-v1:' + arm, 'recognition_model_arm', ['context', *layers],
            'research-atlas-v2/stack-method.json',
            'Every target, fold, prediction, ablation and contrary result in stack-* retained; no arm selected or dropped.')
    pre = pd.read_csv(ATLAS / 'prebirth-summary.csv')
    for (population, lead, feature), g in pre.groupby(['population', 'lead_s', 'feature']):
        add(f'NG-PREBIRTH-v1:{population}:{lead}:{feature}', 'retrospective_prebirth_contrast',
            dict(population=population, lead_s=int(lead), feature=feature),
            'research-atlas-v2/prebirth-summary.csv',
            dict(quarters=g.quarter.tolist(), rows=len(g), defined_pairs=int(g.defined_pairs.sum()),
                 note='All positive, negative and undefined contrasts retained; source rows preserve operands and controls.'))

    selections = {
        'codex-flow-book-discovery-20261108.md': ['Psychology and competing explanations to carry forward',
                                                 'Candidate rules, with a clear evidence status'],
        'october-discovery-log.md': ['Open relationship and mechanism studies'],
    }
    for source, headings in selections.items():
        section, n = '', 0
        for line_no, line in enumerate(pinned_text(source).splitlines(), 1):
            if line.startswith('#'):
                section = line.lstrip('# ').strip()
                n = 0
            if section in headings and line.startswith('|'):
                n += 1
                if n <= 2:
                    continue
                label = line.split('|')[1].strip()
                ident = hashlib.sha256((source + section + label).encode()).hexdigest()[:12]
                add('NG-CARRY-v1:' + ident, 'prior_mechanism_or_principle', line,
                    f'{EVIDENCE_REV}:{source}:{line_no}', 'Entire original table row retained, including rival explanations and contrary evidence.')
    for ident in re.findall(r'\*\*(NG-[A-Z0-9-]+-v1)\.', pinned_text('codex-flow-book-discovery-20261108.md')):
        add(ident, 'named_prior_finding', ident, 'codex-flow-book-discovery-20261108.md',
            'Full original finding, all associated tables and cases remain in the base revision.')
    carry = {
        'four_arm_models': 'All baseline, flow, book and both arms, embargo and initial no-embargo results.',
        'inverse_flow_and_stack': 'Original 50-case stack, inverse flow, and unsupported inverse full-stack remain distinct.',
        'order_paths': 'All 980 aggression-to-rest events, survival delays, refresh and terminal-mechanism alternatives.',
        'size_one_lifecycle': 'All 1,012 size-one episodes: recovery, retreat, improvement and entry-survival distinctions.',
        'next_print_prebirth': 'Falling touch with/without a current print; all next-print and no-print opportunities.',
        'exhaustion_print_gaps': 'All-print versus same-side pressure gaps, withdrawal, opposite flow and quote response.',
        'quote_classifier_variants': 'Wire side, action-time midpoint, preceding completed-group midpoint; unknowns retained.',
        'quote_age_control_sensitivity': 'All ordinary and equal-control weights, full and fresh-quote subsets; negative contrast retained.',
        'post_recognition_paths': 'All same/opposed/undefined flow states, fresh versus expiry paths, flats and censoring.',
        'flow_nowcast': 'Established NG flow nowcast kept separate from archived Native candidate detector.',
        'book_contrarian': 'direction.book_contrarian retained even where original trigger operands are unavailable.',
        'frozen_runway': 'Original Family A checksum and +60 availability; exact duration totals, no relabeling October candidates.',
        'continuous_timing': 'August 20 causal-instance timing precedence; exact later NG-specific look-ahead source still unresolved.',
        'external_and_psychology': 'All 99-plane/13-input, external-clock, curve/options and psychology alternatives in shared discovery log.',
        'nonlinear_combinations': 'Nonlinear, inverse and condition-specific combinations remain open; linear stack results do not eliminate them.',
    }
    for name, definition in carry.items():
        add('NG-RETAIN-v1:' + name, 'retained_research_collection', definition,
            'codex-flow-book-discovery-20261108.md; october-discovery-log.md; codex-research-memory.md',
            'Collection-level index, not a replacement for individual retained source cases or variants.')
    for name in json.loads((OUT / 'method.json').read_text())['hypotheses']:
        add('NG-CONTINUOUS-v1:' + name, 'completed_second_predicate', name,
            'research_atlas_continuous.py:predicates',
            'Every active second, onset, non-birth onset, unmatched birth and 5/20/60-second outcome retained.')
    assert len({r['hypothesis_id'] for r in register}) == len(register)
    return register


def main():
    register = build_register()
    (OUT / 'paper-hypotheses.json').write_text(json.dumps(register, indent=2) + '\n', encoding='utf-8')
    queue = []
    for r in register:
        for day, coverage in [('2023-10-02', 'partial'), ('2023-10-03', 'final_inputs_unverified'),
                              ('2023-10-17', 'partial'), ('2023-10-18', 'retained_discovery_session'),
                              ('additional_days', 'not_yet_supplied')]:
            queue.append(dict(hypothesis_id=r['hypothesis_id'], session_date=day, source_coverage=coverage,
                paper_disposition='retain_for_more_days', comparable_extension_status=(
                    'existing_evidence_retained_not_a_paper_execution' if day == '2023-10-18' else
                    'await_verified_ccode_inputs' if day != 'additional_days' else 'queued_for_future_inputs'),
                simulator_status='not_configured_or_executed'))
    pd.DataFrame(queue).to_csv(OUT / 'paper-date-queue.csv', index=False)
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', EVIDENCE_REV,
                                    'tasks/family-research-20261022']).decode().splitlines()
    sources = [p for p in paths if p.endswith(('.md', '.csv', '.csv.gz', '.json', '.jsonl.gz'))]
    manifest = dict(base_revision=EVIDENCE_REV, registry_entries=len(register), date_queue_rows=len(queue),
        registry_sha256=hashlib.sha256((OUT / 'paper-hypotheses.json').read_bytes()).hexdigest(),
        retention_boundary='All original research files at the base revision remain retained. The register expands explicit contrasts/arms and indexes broader collections; it is not an exhaustive count of conceivable hypotheses.',
        performance_filter='none', source_files=sources,
        paper_contract='Before simulator execution, version the observable trigger, side, order type, size, exit and environment. None are invented from descriptive results. Missing inputs defer an instance, never remove its hypothesis.',
        required_instance_fields=['hypothesis_id', 'version', 'session_date', 'contract', 'input_revision',
            'input_disposition', 'input_known_by_ns', 'decision_ns', 'recognition_ns', 'execution_ns',
            'signal_conditions', 'source_group', 'source_cursor', 'source_dependencies', 'outcome_horizon',
            'outcome_disposition', 'market_path', 'orchestrator_decision_reason', 'order_id', 'fill_or_miss',
            'contrary_evidence', 'noise_judgment_scope'])
    (OUT / 'paper-retention-method.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(registry_entries=len(register), date_queue_rows=len(queue), retained_source_files=len(sources))))


if __name__ == '__main__':
    main()
