"""Frankie's response written by his code (Greg, 2026-09-29: "Frankie does the analysis"; Granite's only text is its
own labelled self-assessment as the critic). SPEC-decouple-granite.md decisions 2, 4 and 5.

Pure functions over files the session already wrote (verify, labels, derive, the comparison packet, the session
receipts packet, the classroom ledgers and receipt, the classroom rules witness). Nothing here calls a model. Every
section names the file it is computed from; a section with no source yet says so and lists what is missing, never
filling it in. No average, no smoothing, no normalization of any result: counts, statuses, values and witnesses.

The response keeps the shapes the principal adapter and the recorder validate: lessons = [analysis text, ONE
calculation_accounting entry, the ten output ledgers], each ledger a JSON object whose "ledger" field is its name.
"""
from __future__ import annotations

import json

AUTHOR = 'Frankie\'s code (computed; no model)'
SECTIONS = (
    'What Frankie learned in the classroom',
    'What Frankie learned from the cycles and the calculations',
    'New exhaustion findings',
    'Suggestions to improve the daily runs, and additional calculations',
    'Things to improve Frankie',
    'Trade signal insight',
)
EXHAUSTION_WORDS = ('exhaust', 'runway', 'chain', 'depth', 'birth', 'leader')


def _j(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _unknown(what):
    return f'- UNKNOWN (no source computed yet): {what}'


def _classroom(ctx):
    ledgers, receipt = ctx.get('classroom_ledgers') or {}, ctx.get('classroom_receipt') or {}
    report = receipt.get('report') or {}
    teach = ledgers.get('dipole_teachback') or {}
    lines = [f'Source: work/classroom/ledgers.json and receipt.json (answered by Frankie\'s code under the classroom rules '
             f'{(ctx.get("rules_witness") or {}).get("sha256", "(rules witness absent)")}).',
             f'- {report.get("components")} components, {report.get("observations")} observations and {report.get("pairs")} pairs '
             f'accounted for; {report.get("novel_findings")} novel findings filed; {report.get("unresolved_questions")} unresolved questions.',
             f'- Cycle summary: {teach.get("cycle_summary", "(absent)")}',
             f'- Relationship surface: {teach.get("correlation_review", "(absent)")}']
    for f in ledgers.get('dipole_novel_findings') or []:
        lines.append(f'- Finding {f.get("finding_id")}: {f.get("premise")}')
    for q in teach.get('unresolved_questions') or []:
        lines.append(f'- Open: {q}')
    lines.append('- The grade and any corrections come from the host after this response (the correction turn); they are not '
                 'known inside this response.')
    return lines


def _cycles(ctx):
    derive, comparison = ctx.get('derive') or {}, ctx.get('comparison') or {}
    layers = derive.get('layers') or {}
    status = {}
    for v in layers.values():
        status[v.get('status')] = status.get(v.get('status'), 0) + 1
    lines = [f'Source: work/derive.json and work/comparison.json.',
             f'- {len(layers)} pin layers on {derive.get("rows", {}).get("count") if isinstance(derive.get("rows"), dict) else derive.get("rows")} '
             f'rows ({derive.get("input_records")} INPUT records); statuses {_j(status)}; derivation failures {derive.get("failure_count")}.']
    for name, v in sorted(layers.items()):
        line = f'- {name}: {v.get("status")}' + (f', sha256 {str(v.get("sha256"))[:16]}' if v.get('sha256') else '')
        if v.get('reason'):
            line += f' ({v["reason"]})'
        lines.append(line)
    counts = comparison.get('counts') or {}
    if counts:
        lines.append(f'- Beside the frozen brain: {counts.get("frozen_layers")} frozen layers, {counts.get("frozen_files_carried")} of '
                     f'{counts.get("frozen_files_delivered")} frozen files carried whole. The comparison by code is by shape '
                     '(fields and counts on each side, in comparison.md); a content-level comparison is not computed yet.')
    else:
        lines.append(_unknown('the comparison packet (work/comparison.json) is absent'))
    return lines


def _exhaustion(ctx):
    visible = ctx.get('visible') or {}
    comps = (visible.get('pre_message') or {}).get('components') or []
    related = [c for c in comps if any(w in ' '.join(str(c.get(k, '')) for k in ('name', 'role', 'behavior_basis')).lower()
                                       for w in EXHAUSTION_WORDS)]
    lines = ['Source: the classroom (the teachers teach exhaustion; the bedrock is their logic helper, never Frankie\'s knowledge base).']
    if not related:
        lines.append(_unknown('no classroom component names exhaustion, runway, chains or D-depth in this package'))
    for c in related:
        lines.append(f'- {c["name"]}: direction {c.get("first_to_last_present_direction")}, terminal {c.get("terminal_state")}, '
                     f'state counts {_j(c.get("state_counts"))}; change from the previous cycle {_j(c.get("change_from_previous"))}.')
    names = {c['name'] for c in related}
    hits = [f for f in (ctx.get('classroom_ledgers') or {}).get('dipole_novel_findings') or []
            if any(r.get('left') in names or r.get('right') in names or r.get('component') in names for r in f.get('evidence_refs') or [])]
    lines += [f'- Hypothesis {f["finding_id"]}: {f["premise"]}' for f in hits] or ['- No new exhaustion hypothesis surfaced by a computation this cycle.']
    return lines


def _suggestions(ctx):
    derive = ctx.get('derive') or {}
    lines = ['Source: the could_not layers in work/derive.json and the classroom\'s unresolved questions; each suggestion is tied to what was measured.']
    could = [(n, v.get('reason')) for n, v in sorted((derive.get('layers') or {}).items()) if v.get('status') == 'could_not']
    lines += [f'- Build or feed a producer for {n}: it could not be derived here ({r}).' for n, r in could] or ['- Every pin layer derived; no missing producer to suggest.']
    if derive.get('failure_count'):
        lines.append(f'- Trace the {derive["failure_count"]} derivation failures in work/derive.json.')
    lines.append(_unknown('stage timings and CPU use per stage are not read by this code yet (the host progress file and the '
                          'session CPU probe hold them)'))
    return lines


def _improve(ctx):
    return ['Source: what this code does not compute (listed in the classroom answers and above).',
            '- Frankie\'s code does not yet interpret market behaviour or the FIFO / full-book / order link for a component; '
            'both are listed as unknown in every classroom answer.',
            '- The GUIDED, SOCRATIC and VERIFY classroom modes need an independent source for the 19 dimensions; until it '
            'exists those modes are refused, not answered from the host key.',
            '- The comparison of derived layers with the frozen brain is by shape only; a content-level comparison is not built.']


def _trade(ctx):
    return ['Source: none this cycle.', _unknown('no trade-signal calculation ran in this principal session; no insight is '
                                                 'claimed (rule R02: no outcome after the causal cutoff)')]


def analysis_markdown(ctx):
    """The analysis: Greg's six sections, then Granite's one labelled section."""
    builders = (_classroom, _cycles, _exhaustion, _suggestions, _improve, _trade)
    parts = [f'# Frankie\'s analysis, cycle {ctx.get("cycle")} ({AUTHOR})', '',
             'Every line is computed from the file it names; UNKNOWN marks what has no source yet. Nothing is averaged, '
             'smoothed or normalized.', '']
    for title, build in zip(SECTIONS, builders):
        parts += [f'## {title}', ''] + build(ctx) + ['']
    sa = ctx.get('self_assessment') or {}
    parts += ['## Granite\'s self-assessment as the critic (Granite\'s own view, not a result)', '']
    if sa.get('text'):
        parts += [f'Source: one call to the critic\'s model on Pod {sa.get("pod_id")}, job {sa.get("job_id")}, over its own output '
                  f'{sa.get("critic_output")}. Granite\'s words follow as it gave them.', '', sa['text'], '']
    else:
        parts += [f'Not given this cycle: {sa.get("error") or "no attempt recorded"}. The run continues (C24: the critic is never a '
                  'blocking dependency).', '']
    return '\n'.join(parts)


def accounting_entry(ledger_name, derive, comparison, required_layers):
    """ONE accounting entry covering every required layer. A layer is filed as its derivation filed it (derived or
    could_not), never as compared: the comparison by code is by shape only, and that is written in compared_with."""
    layers = derive.get('layers') or {}
    frozen = (comparison or {}).get('frozen') or {}
    entries = []
    for name in sorted(set(layers) | set(required_layers)):
        v = layers.get(name)
        if v is None:
            entries.append(dict(layer=name, status='could_not', where=None, compared_with=None,
                                reason='not in this session\'s derive.json (the pin requires it)'))
            continue
        status = v.get('status') if v.get('status') in ('derived', 'could_not') else 'could_not'
        files = [dict(source=e.get('source'), sha256=e.get('sha256'), include=e.get('include')) for e in frozen.get(name, [])]
        entries.append(dict(layer=name, status=status,
                            where=f'work/derived/{name}.json sha256 {v.get("sha256")}' if v.get('sha256') else 'work/derive.json',
                            compared_with=(dict(frozen_files=files, comparison='by shape only (fields and counts in comparison.md); '
                                                'content-level comparison not computed') if files else
                                           'no frozen learned-structure file speaks to this layer'),
                            reason=v.get('reason') or (None if status == 'derived' else 'filed could_not by the derivation')))
    return dict(ledger=ledger_name, author=AUTHOR, layers=entries)


def output_ledgers(names, registry, ctx):
    """The ten output ledgers, each filled from observed files or filed with its reason (never omitted)."""
    receipts = ctx.get('receipts') or {}
    ledgers = ctx.get('classroom_ledgers') or {}
    derive = ctx.get('derive') or {}
    labels, verify = ctx.get('labels') or {}, ctx.get('verify') or {}
    fill = {
        'output_candidate_discoveries': lambda: dict(entries=[dict(finding_id=f['finding_id'], premise=f['premise'], evidence_refs=f['evidence_refs'])
                                                              for f in ledgers.get('dipole_novel_findings') or []],
                                                     reason=None if ledgers.get('dipole_novel_findings') else 'no candidate surfaced by a computation this cycle'),
        'output_first_locks_and_no_locks': lambda: dict(entries=labels.get('labels') or [], status=labels.get('status', 'labels_available'),
                                                         reason=None if labels.get('labels') else 'no timing label in work/labels.json'),
        'output_frankie_reasoning_movie': lambda: dict(entries=ctx.get('stages') or [], reason='the session stages in order, as the code ran them; no model reasoning in the principal'),
        'output_probability_movie': lambda: dict(entries=[], reason='no probability is produced by Frankie\'s code in this session'),
        'output_state_and_state_delta_movie': lambda: dict(entries=[dict(layer=n, status=v.get('status'), sha256=v.get('sha256'), reason=v.get('reason'))
                                                                    for n, v in sorted((derive.get('layers') or {}).items())],
                                                           classroom_changes=[dict(name=c['name'], change_from_previous=c.get('change_from_previous'))
                                                                              for c in ((ctx.get('visible') or {}).get('pre_message') or {}).get('components') or []]),
        'output_knowledge_retrieval_receipts': lambda: dict(entries=[receipts.get('knowledge_retrieval')], reason=None),
        'output_negative_sparse_inconclusive_ledger': lambda: dict(
            could_not=[dict(layer=n, reason=v.get('reason')) for n, v in sorted((derive.get('layers') or {}).items()) if v.get('status') == 'could_not'],
            unresolved_questions=(ledgers.get('dipole_teachback') or {}).get('unresolved_questions') or [],
            unknown=['market behaviour and the FIFO / full-book / order link per classroom component (not computed)',
                     'trade signal insight (no calculation ran)', 'content-level comparison with the frozen brain (not built)']),
        'output_provider_invocation_response_receipts': lambda: dict(entries=receipts.get('provider_invocations') or [],
                                                                     reason=None if receipts.get('provider_invocations') else 'no model call in this session before the writing (the only one is Granite\'s self-assessment, receipted in its own section)'),
        'output_answer_wall_access_receipts': lambda: dict(entries=[receipts.get('answer_wall')], reason=None),
        'output_source_state_manifest_code_model_run_hashes': lambda: dict(entries=[dict(
            request_sha256=verify.get('request_sha256'), input_hash=verify.get('input_hash'), source_hash=verify.get('source_hash'),
            code_commit=ctx.get('code_commit'), layers={n: v.get('sha256') for n, v in sorted((derive.get('layers') or {}).items())},
            classroom_rules=ctx.get('rules_witness'), model='none in the principal; Granite only in its labelled self-assessment')]),
    }
    out = []
    for name in names:
        body = fill[name]() if name in fill else dict(entries=[], reason='no code source for this ledger yet')
        item = dict(ledger=name, author=AUTHOR, **body)
        if registry.get(name):
            item['registry_description'] = registry[name]
        out.append(item)
    return out
