import re
from pathlib import Path
root = Path('/home/user/Markets')

def sub(path, old, new, count=1):
    p = root / path; t = p.read_text()
    assert t.count(old) == count, (path, old[:80], t.count(old))
    p.write_text(t.replace(old, new))

S = 'deploy/aws/box/frankie_box_boss_session.py'
t = (root / S).read_text()
# 1. Critical: one module object per box module (the retry's except must see the class parse raises)
old_loaders = t[t.index('def docs_module():'):t.index("PACKETS = ('comparison.md'")]
new_loaders = '''_MODULES = {}


def _box_module(stem, what):
    """A sibling module of this file, loaded by path ONCE per process (this directory is not a package). One object per
    module: the classes it defines (frankie_box_classroom.ClassroomOutput) must be the same class wherever the session
    raises and catches them; a fresh exec per call made the classroom retry dead code (ship review, 2026-09-21)."""
    if stem not in _MODULES:
        import importlib.util
        path = Path(__file__).resolve().parent / f'{stem}.py'
        spec = importlib.util.spec_from_file_location(stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES[stem] = module
    return _MODULES[stem]


def docs_module():
    """deploy/aws/box/frankie_box_docs.py (the session documents; tolerant JSON; the refusal pattern)."""
    return _box_module('frankie_box_docs', 'docs')


def brain_module():
    """deploy/aws/box/frankie_box_brain.py (Frankie's brain: prior cycles' calculation findings)."""
    return _box_module('frankie_box_brain', 'brain')


def classroom_module():
    """deploy/aws/box/frankie_box_classroom.py (the Dipole classroom exchange, both turns)."""
    return _box_module('frankie_box_classroom', 'classroom')


def compare_module():
    """deploy/aws/box/frankie_box_compare.py (the comparison packet: derived layers beside the frozen files)."""
    return _box_module('frankie_box_compare', 'compare')


def receipts_module():
    """deploy/aws/box/frankie_box_receipts.py (the session receipts packet)."""
    return _box_module('frankie_box_receipts', 'receipts')


'''
t = t.replace(old_loaders, new_loaders)
(root / S).write_text(t)

# 2. Required: the reading lane's resume is bound to the prompt, not the job name
sub(S, '''        directory = self.work / 'serverless-jobs' / name
        directory.mkdir(parents=True, exist_ok=True)
        outcome_path = directory / 'outcome.json'
        if outcome_path.exists():
            return load_json(outcome_path)
        estimate = self._input_tokens(text)''',
'''        directory = self.work / 'serverless-jobs' / name
        directory.mkdir(parents=True, exist_ok=True)
        outcome_path = directory / 'outcome.json'
        prompt_path = directory / 'prompt.txt'
        if outcome_path.exists():
            # Durable by NAME, bound by CONTENT: an outcome is resumed only when it answered this exact prompt. A prompt
            # that moved (a code fix on restart) moves the old job aside with a receipt and the part is asked again.
            if prompt_path.is_file() and prompt_path.read_text(encoding='utf-8') == text:
                return load_json(outcome_path)
            self._supersede_job(directory, name, text)
        estimate = self._input_tokens(text)''')
sub(S, '''    def serverless_job(self, name, text):''',
'''    def _supersede_job(self, directory, name, text):
        """Move a durable job directory whose prompt is not the one asked now aside (never deleted), with a receipt."""
        stamp = f'{int(time.time())}-{uuid.uuid4().hex[:8]}'
        aside = directory.parent / f'{directory.name}.superseded-{stamp}'
        os.replace(directory, aside)
        write_json(aside / 'superseded.json', dict(schema='FRANKIE_BOX_JOB_SUPERSEDED_V1', at=time.time(), name=name, moved_to=str(aside),
                   reason='the prompt asked now differs from the prompt this job answered', prompt_sha256_now=sha256_bytes(text.encode('utf-8'))))
        directory.mkdir(parents=True, exist_ok=True)
        self.note(f'{name}: durable outcome answered a different prompt; moved aside to {aside.name} and asked again')

    def serverless_job(self, name, text):''')
if not re.search(r'^import os$', t, re.M):
    sub(S, 'import argparse\n', 'import argparse\nimport os\n')
# each component call records the prompt sha
sub(S, '''                return parsed, dict(attempt=attempt, job_id=outcome.get('job_id') or outcome.get('runpod_job_id'), lane=lane,
                                    incomplete=bool(outcome.get('incomplete')), repairs=repairs, estimated_input_tokens=estimate, usage=outcome.get('usage'))''',
'''                return parsed, dict(attempt=attempt, job_id=outcome.get('job_id') or outcome.get('runpod_job_id'), lane=lane,
                                    prompt_sha256=sha256_bytes(text.encode('utf-8')), incomplete=bool(outcome.get('incomplete')),
                                    repairs=repairs, estimated_input_tokens=estimate, usage=outcome.get('usage'))''')
# 3. writing gate keyed on the ledgers too
sub(S, '''        names = ('merged-notes.md', 'derivation-digest-full.md') + PACKETS
        return {n: sha256_bytes((self.work / n).read_bytes()) for n in names if (self.work / n).is_file()}''',
'''        names = ('merged-notes.md', 'derivation-digest-full.md') + PACKETS
        inputs = {n: sha256_bytes((self.work / n).read_bytes()) for n in names if (self.work / n).is_file()}
        ledgers = self.work / 'classroom' / 'ledgers.json'
        if ledgers.is_file():
            inputs['classroom/ledgers.json'] = sha256_bytes(ledgers.read_bytes())
        return inputs''')
# 4. the correction stage renders its docs
sub(S, '''        write_json(d / 'correction-receipt.json', dict(schema='FRANKIE_BOX_CORRECTION_RECEIPT_V1', at=time.time(), request_sha256=request_sha256,''',
'''        self.docs()
        write_json(d / 'correction-receipt.json', dict(schema='FRANKIE_BOX_CORRECTION_RECEIPT_V1', at=time.time(), request_sha256=request_sha256,''')

# 5. classroom.py: one docs module; a finding that claims a future outcome is dropped, never rewritten; COMPOSITION names the stamps
K = 'deploy/aws/box/frankie_box_classroom.py'
sub(K, '''def tolerant_json(text):
    """frankie_box_docs.tolerant_json (fences, first balanced object, comments, trailing commas, truncated close)."""
    path = Path(__file__).resolve().parent / 'frankie_box_docs.py'
    spec = importlib.util.spec_from_file_location('frankie_box_docs_for_classroom', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tolerant_json(text)''',
'''_DOCS = []


def _docs():
    if not _DOCS:
        path = Path(__file__).resolve().parent / 'frankie_box_docs.py'
        spec = importlib.util.spec_from_file_location('frankie_box_docs_for_classroom', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _DOCS.append(module)
    return _DOCS[0]


def tolerant_json(text):
    """frankie_box_docs.tolerant_json (fences, first balanced object, comments, trailing commas, truncated close)."""
    return _docs().tolerant_json(text)''')
sub(K, '''               "acknowledgement are the BOSS's own text, parsed from its JSON answers; nothing else is written on its behalf")''',
'''               "acknowledgement are the BOSS's own text, parsed from its JSON answers. Three flags are stamped by the session code: "
               'the teach-back and every filed finding carry future_outcome_claimed=false because a finding the BOSS marks '
               'future_outcome_claimed=true is dropped with its reason, never rewritten; the acknowledgement carries acknowledged=true and '
               'resolved_correction_ids=every correction id because an answer lacking a corrected_understanding for any id is refused, '
               'so the ids are exactly the ones the BOSS resolved. Nothing else is written on its behalf')''')
sub(K, '''        if not isinstance(raw, dict):
            dropped.append(dict(finding_id=None, reason='not an object', raw=raw))
            continue
        candidate =''',
'''        if not isinstance(raw, dict):
            dropped.append(dict(finding_id=None, reason='not an object', raw=raw))
            continue
        if raw.get('future_outcome_claimed'):
            dropped.append(dict(finding_id=raw.get('finding_id'), reason='the finding claims a future outcome (future_outcome_claimed true); not filed', raw=raw))
            continue
        candidate =''')
sub(K, '''"novel_findings": [{"finding_id": "short-id", "premise": "...", "why_novel": "...", "evidence_refs": [ \'''',
'''"novel_findings": [{"finding_id": "short-id", "premise": "...", "why_novel": "...", "future_outcome_claimed": false, "evidence_refs": [ \'''')
sub(K, '''no finding claims an outcome after the causal cutoff; cycle_summary''',
'''no finding claims an outcome after the causal cutoff (a finding marked future_outcome_claimed true is dropped, not filed); cycle_summary''')

# 6. session.sh: never move the checkout under a running cycle session
sub('deploy/aws/box/frankie_box_session.sh',
'''  U="frankie-correction-$CYCLE"
  if systemctl is-active --quiet "$U.service"; then echo "$U is already running"; status; return 0; fi''',
'''  U="frankie-correction-$CYCLE"
  if systemctl is-active --quiet "$U.service"; then echo "$U is already running"; status; return 0; fi
  if systemctl is-active --quiet "frankie-session-$CYCLE.service"; then echo "frankie-session-$CYCLE is running: the correction waits (its checkout would move the code under the running session)"; return 2; fi''')

# 7. push receipt: files as a JSON array under the same schema
sub('deploy/aws/box/frankie_box_push_response.sh',
'''printf '{"schema":"FRANKIE_BOX_RESPONSE_PUSH_RECEIPT_V1","at":%s,"branch":"%s","commit":"%s","turn":"%s","files":"%s"}\\n' "$(date +%s)" "$BR" "$sha" "$TURN" "${FILES:-docs}" > "$ROOT/receipts/response-push-$(date +%s).json"''',
'''files_json=$(printf '%s\\n' ${FILES:-docs} | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
printf '{"schema":"FRANKIE_BOX_RESPONSE_PUSH_RECEIPT_V1","at":%s,"branch":"%s","commit":"%s","turn":"%s","files":%s}\\n' "$(date +%s)" "$BR" "$sha" "$TURN" "$files_json" > "$ROOT/receipts/response-push-$(date +%s).json"''')

# 8. fetch workflow: hex-validate the sha before it reaches GITHUB_OUTPUT (both turns)
Y = '.github/workflows/frankie_box_fetch_response.yml'
y = (root / Y).read_text()
old1 = """              with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                  out.write(f"request_sha256={r['request_sha256']}\\n")
              raise SystemExit(0)"""
assert y.count(old1) == 1
y = y.replace(old1, """              if not re.fullmatch(r'[0-9a-f]{64}', str(r['request_sha256'])):
                  raise SystemExit('request_sha256 is not 64 hex characters; not exported')
              with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                  out.write(f"request_sha256={r['request_sha256']}\\n")
              raise SystemExit(0)""")
old2 = """              out.write(f"request_sha256={r['request_sha256']}\\n")"""
# second occurrence (initial turn) - after replacement above there are two lines with this text; guard the initial one
idx = y.rindex(old2)
line_start = y.rindex('\n', 0, idx) + 1
indent = y[line_start:idx]
prev_line_start = y.rindex('\n', 0, line_start - 1) + 1
prev = y[prev_line_start:line_start]
assert 'with open(os.environ' in prev, prev
y = y[:prev_line_start] + indent[:-4] + "if not re.fullmatch(r'[0-9a-f]{64}', str(r['request_sha256'])):\n" + indent[:-4] + "    raise SystemExit('request_sha256 is not 64 hex characters; not exported')\n" + y[prev_line_start:]
if 'import re' not in y:
    y = y.replace('import json, os', 'import json, os, re', 1) if 'import json, os' in y else y
(root / Y).write_text(y)
print('review fixes applied')
