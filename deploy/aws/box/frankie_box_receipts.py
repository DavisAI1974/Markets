"""The session receipts packet (Frankie's own ask, cycle 0 ledgers, 2026-09-21): the observed facts three output ledgers
could not be filled without. Cycle 0 filed output_provider_invocation_response_receipts, output_answer_wall_access_receipts
and output_knowledge_retrieval_receipts as could_not because "no observed fact ... present in the delivered evidence";
the facts exist on the box: every BOSS and serverless job the session made (request and result witnesses, usage, model),
what the session read (the corpus, the parts, the notes and merges, the reading ledger) and the wall the session kept
(the request's as_of and learning cutoff, the input hash, the timing labels computed by code from the next cycle's
authored marks). This packet renders them into the writing base so the ledgers are filled from observed facts.

Pure functions; the session writes work/session-receipts.json and work/session-receipts.md. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_SESSION_RECEIPTS_V1'


def _load(path):
    try:
        return json.loads(Path(path).read_bytes())
    except Exception:
        return None


def _witness(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def provider_invocations(work):
    """Every model call the session made, from the durable job directories: the BOSS (Pod, jobs_v1) and the reading lane
    (RunPod serverless), each with its request witness, result witness, usage and model as the provider reported them."""
    work = Path(work)
    out = []
    for lane, folder in (('boss', 'boss-jobs'), ('serverless', 'serverless-jobs')):
        base = work / folder
        if not base.is_dir():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            request, outcome = _load(d / 'request.json') or {}, _load(d / 'outcome.json') or {}
            item = dict(lane=lane, name=request.get('name') or outcome.get('name') or d.name, job_directory=d.name,
                        request_sha256=request.get('body_sha256'), request_bytes=request.get('body_bytes'),
                        estimated_input_tokens=request.get('estimated_input_tokens'), max_tokens=request.get('max_tokens'),
                        served_model_name=request.get('served_model_name'), pod_id=request.get('pod_id'), endpoint_id=request.get('endpoint_id') or outcome.get('endpoint_id'),
                        job_id=outcome.get('job_id') or request.get('job_id') or outcome.get('runpod_job_id'), runpod_job_id=outcome.get('runpod_job_id'),
                        worker_id=outcome.get('worker_id'), result=_witness(d / 'result.json'), model=outcome.get('model'), usage=outcome.get('usage'),
                        incomplete=bool(outcome.get('incomplete')), error=outcome.get('error'), seconds=outcome.get('seconds'), submissions=outcome.get('submissions'))
            out.append(item)
    return out


def knowledge_retrieval(work, reading_ledger=None):
    """What the session read: the corpus and its plan, every note and merge, the merged notes, the brain members, and the
    reading ledger's record for this cycle."""
    work = Path(work)
    reading, plan = _load(work / 'reading.json') or {}, _load(work / 'reading-plan.json') or {}
    notes_dir = Path(plan['notes_dir']) if plan.get('notes_dir') else None
    notes = []
    if notes_dir and notes_dir.is_dir():
        notes = [dict(name=p.name, **_witness(p)) for p in sorted(notes_dir.glob('note-*.md'))]
    merges = [dict(name=p.name, **_witness(p)) for p in sorted((work / 'merges').glob('merge-*.md'))] if (work / 'merges').is_dir() else []
    ledger = _load(reading_ledger) if reading_ledger else None
    corpus_receipts = [dict(name=p.name, **_witness(p)) for p in sorted(work.glob('reading-corpus*.json'))]
    return dict(corpus=reading.get('corpus') or plan.get('corpus'), corpus_sha256=reading.get('corpus_sha256'), parts=reading.get('parts'),
                chunk_bytes=plan.get('chunk_bytes'), part_input_tokens=plan.get('part_input_tokens'), lane=reading.get('lane'),
                notes_dir=str(notes_dir) if notes_dir else None, notes=notes, merges=merges, merged=reading.get('merged') or _witness(work / 'merged-notes.md'),
                corpus_receipts=corpus_receipts,
                reading_ledger=dict(values=len(ledger.get('values', {})), cycles=sorted(ledger.get('cycles', {}))) if isinstance(ledger, dict) else None,
                brain=dict(comparison=_witness(work / 'comparison.md'), classroom=_witness(work / 'classroom' / 'classroom.md')))


def answer_wall(work):
    """The wall the session kept: the request's causal cutoff and learning cutoff, the one input hash it verified, the
    prompt it read, and the timing labels it computed by code (each mark's available_ns at or before the learning cutoff)."""
    work = Path(work)
    verify, labels = _load(work / 'verify.json') or {}, _load(work / 'labels.json') or {}
    marks = labels.get('labels') or []
    return dict(request_sha256=verify.get('request_sha256'), request_id=verify.get('request_id'), cycle_index=verify.get('cycle_index'),
                as_of=verify.get('as_of'), learning_cutoff_ns=verify.get('learning_cutoff_ns'), source_hash=verify.get('source_hash'),
                input_hash=verify.get('input_hash'), input_hash_sources=verify.get('input_hash_sources'), prompt=verify.get('prompt'),
                session_id=verify.get('session_id'), labels=dict(count=len(marks), available_ns=labels.get('available_ns'), gap=labels.get('gap'), path=labels.get('path'),
                                                              first=marks[:1], last=marks[-1:], all_available_at_or_before_cutoff=all(m.get('available_ns', 0) <= (verify.get('learning_cutoff_ns') or 0) for m in marks) if marks else None),
                rule='nothing received after the learning cutoff was read; the labels come from the next authored cycle\'s marks by code, never from a later outcome')


def build(work, reading_ledger=None):
    return dict(schema=SCHEMA, at=time.time(), provider_invocations=provider_invocations(work), knowledge_retrieval=knowledge_retrieval(work, reading_ledger),
                answer_wall=answer_wall(work))


def render(report):
    p, k, w = report['provider_invocations'], report['knowledge_retrieval'], report['answer_wall']
    lines = ['# Session receipts packet (written by the session code; observed facts of THIS session for the receipt ledgers)', '',
             'These are the session\'s own records: every provider invocation it made, what it retrieved and read, and the wall it kept. '
             'Cite them as observed facts in output_provider_invocation_response_receipts, output_knowledge_retrieval_receipts and '
             'output_answer_wall_access_receipts (and anywhere else they bear); nothing here is inferred.', '',
             f'## Provider invocations ({len(p)}: {sum(1 for i in p if i["lane"] == "boss")} BOSS jobs on the Pod, {sum(1 for i in p if i["lane"] == "serverless")} serverless jobs)', '',
             '| lane | name | request sha256 | job id | model | prompt tokens | completion tokens | incomplete | error | seconds |', '|---|---|---|---|---|---:|---:|---|---|---:|']
    for i in p:
        usage = i.get('usage') or {}
        lines.append(f'| {i["lane"]} | {i["name"]} | {(i.get("request_sha256") or "")[:16]} | {(i.get("job_id") or "")[:16]} | {i.get("model") or ""} | '
                     f'{usage.get("prompt_tokens", "")} | {usage.get("completion_tokens", "")} | {"yes" if i["incomplete"] else ""} | {(i.get("error") or "")[:60]} | '
                     f'{round(i["seconds"]) if isinstance(i.get("seconds"), (int, float)) else ""} |')
    lines += ['', '## Knowledge retrieval (what the session read)', '',
              f'- corpus: {json.dumps(k.get("corpus"), sort_keys=True)}; corpus sha256 {k.get("corpus_sha256")}; {k.get("parts")} parts of {k.get("chunk_bytes")} bytes '
              f'({k.get("part_input_tokens")} tokens per part); lane {json.dumps(k.get("lane"), sort_keys=True)}',
              f'- notes: {len(k["notes"])} in {k.get("notes_dir")}; merges: {len(k["merges"])}; merged notes: {json.dumps(k.get("merged"), sort_keys=True)}',
              f'- reading ledger: {json.dumps(k.get("reading_ledger"), sort_keys=True)}; corpus receipts: {json.dumps(k.get("corpus_receipts"), sort_keys=True)}',
              f'- brain packets in the writing base: comparison {json.dumps(k["brain"].get("comparison"), sort_keys=True)}, classroom {json.dumps(k["brain"].get("classroom"), sort_keys=True)}',
              '', '## Answer wall (the causal wall the session kept)', '',
              f'- request {w.get("request_sha256")} ({w.get("request_id")}, cycle {w.get("cycle_index")}); as_of {w.get("as_of")}; learning cutoff {w.get("learning_cutoff_ns")}; '
              f'source_hash {w.get("source_hash")}; input_hash {w.get("input_hash")} (found in {json.dumps(w.get("input_hash_sources"), sort_keys=True)})',
              f'- prompt read: {json.dumps(w.get("prompt"), sort_keys=True)}; session {w.get("session_id")}',
              f'- timing labels by code: {json.dumps(w.get("labels"), sort_keys=True)}',
              f'- rule: {w.get("rule")}']
    return '\n'.join(lines) + '\n'


def write(work, reading_ledger=None):
    work = Path(work)
    report = build(work, reading_ledger)
    (work / 'session-receipts.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    (work / 'session-receipts.md').write_text(render(report), encoding='utf-8')
    return report
