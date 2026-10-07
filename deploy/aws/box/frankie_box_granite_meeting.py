"""Granite as the bounded post-class discussion coordinator (role V2): the meeting loop, code only around one small model.

Greg, 2026-10-06 (GRANITE_DISCUSSION_REPORT_20261006.md, confirming knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md
and CLASSROOM_RULES_V3.json R17). CCode: smaller-model facilitator integration; NOT workflow Step #5.

Three code/data seats already spoke in the three-way exchange (frankie_box_experiment_exchange.py): the BOSS teacher,
the scientific teacher and Frankie, each turn source-bound with cites. Granite is given Frankie's VIEW of that exchange
(Jev's raw items withheld: the lessons wall) and coordinates: it picks the open item, asks a seat to clarify its own
statement, points out a scope mismatch, asks the scientific seat which code test would settle a claim, keeps the list of
agreements, disagreements, missing evidence and requested tests. It adds no evidence:

  - every number in a coordinator turn must already be in the item's three turns (reusing the voice validator's number
    and wording checks: frankie_box_exchange_voice._allowed / POOLED / FORWARD); pooled, forward, trade, confirming or
    deciding wording is refused and listed, never kept;
  - a code seat's answer to a question is that seat's OWN retained record (its exchange turn and side fields), supplied
    by code; no new calculation happens in the meeting. A question that needs a new calculation becomes a REQUESTED TEST
    bound to an existing proposal_id / claim_id / listed untested text of the item, executed later by the proper code
    stage; an unbound request is listed, not executed;
  - RESOLVED is accepted only when the code seats' own records already say so (Frankie's resolution RESOLVED_* and no
    remaining disagreement, and nothing open on the item); otherwise Granite may only LEAVE_OPEN. Granite never decides;
  - every item is discussed or listed; the turn budget and the meeting time budget close an item as OPEN by code.

The durable record FRANKIE_GRANITE_MEETING_V1 keeps the four categories apart: seat_statements, coordinator_turns,
code_seat_answers, open_items/requested_tests. Complete records publish immediately into Frankie's brain when given
the owning brain path. A runner retains the same bytes for an explicit owner-side return, reported by its receipt.

Recovery and evidence (Codex findings 1-3, 2026-10-06; built 2026-10-07): the settled meeting budget bounds EVERY request
(start, template, tokenize, chat); per-item progress is durable (completed rounds reused on a restart, a pending call with
unknown completion closed open and never repeated, everything bound to meeting-binding.json); the server's whole stderr
and every failed or malformed reply are retained as files under evidence/, never sliced; a startup or request failure
releases the process and keeps the partial state. return.json names the record's bytes and hash for the owner import.
Runtime: llama.cpp llama-server, ephemeral, started here and stopped here; model/release pins and the runtime parameters
live in knowledge/GRANITE_MEETING_RUNTIME_V1.json and the gate refuses to call the model while a pin is null or the
parameters are unconfirmed. `--inputs-only` writes what Granite would be given, with zero model calls.

Greg, 2026-10-07 (WORKFLOW_COVERAGE_PLAN_20261007.md): Granite sees the WHOLE shared market picture of the day's
exchange (the complete typed picture at the teachers' original cutoff, spelled through the proven token stacks),
unless the per-call token cap refuses, which it does VISIBLY: the system prompt is counted once with the server's own
tokenizer before any call; over the cap, every item is left open by code with the count on the receipt and the
one-day inspection markdown; nothing is trimmed. The number rule is unchanged: a coordinator turn may voice only
numbers that are in a seat's turn; the picture is context, never a source of new empirical content (role V2).
Hosting: the meeting is a CHILD on the owning box's held lane, CPU only, under the ONE shared runtime definition
(`local_runtime`: llama.cpp b11440 llama-server + Granite 4.2 3B Q4_K_M, pinned in GRANITE_MEETING_RUNTIME_V1.json);
`voice_route=local` is the default; the GitHub route stays listed as the unused fallback. Jev's CPU turn binds to the
same `local_runtime` (Greg: "same weight code and setup as Granite so that way it can automatically improve").
Nothing here keys on how many days a run holds.

Model-evaluation clock (Greg, 2026-10-07): every coordinator call, and every call refused over a cap or not made
(gate, start failure, budget, runtime exit, system prompt over cap), is stamped once as FRANKIE_MODEL_EVALUATION_CLOCK_V1
(frankie_box_model_clock) in <run-dir>/days/<day>/model-clock.jsonl with the meeting input's exact market cutoff, the
shared runtime pins, the lane and the wall clock; the meeting record and receipt name the file and every record of the
attempt. Threads: null resolves to the claimed adviser slot (1), never the host CPU count (threads_resolution).
"""
import argparse
import hashlib
import http.client
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
REPO = BOX.parents[2]
sys.path.insert(0, str(BOX))
sys.path.insert(0, str(REPO))

SCHEMA = 'FRANKIE_GRANITE_MEETING_V1'
INPUT_SCHEMA = 'FRANKIE_GRANITE_MEETING_INPUT_V1'
RECEIPT_SCHEMA = 'FRANKIE_GRANITE_MEETING_RECEIPT_V1'
REQUEST_SCHEMA = 'FRANKIE_MEETING_TEST_REQUEST_V1'
BINDING_SCHEMA = 'FRANKIE_GRANITE_MEETING_BINDING_V1'     # the exact inputs every model call of this meeting is bound to
PROGRESS_SCHEMA = 'FRANKIE_GRANITE_MEETING_ITEM_PROGRESS_V1'   # per-item durable progress (completed rounds; a pending call)
RETURN_SCHEMA = 'FRANKIE_GRANITE_MEETING_RETURN_V1'      # what a runner hands back: the record's bytes and hash, by name
CONFIG = REPO / 'research/kalshi/frankie_boss/knowledge/GRANITE_MEETING_RUNTIME_V1.json'
CHARTER = REPO / 'research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md'
GRANITE_ROOT = Path('/opt/frankie-box/granite')      # the box's install root (the wrapper admits paths under it only)
VOICE_ROUTES = ('local', 'github')                    # local = a child on the owning box's lane (default); github = listed fallback
DEFAULT_VOICE_ROUTE = 'local'
SHARED_RUNTIME_SCHEMA = 'FRANKIE_GRANITE_SHARED_RUNTIME_V1'   # the one runtime definition the meeting and Jev both bind to
CALL_CEILING_SECONDS = 600.0                          # per-request transport ceiling of a coordinator call (params may raise it)
SEATS = ('boss_teacher', 'scientific_teacher', 'frankie')
ACTIONS = ('ASK', 'REQUEST_TEST', 'NOTE_AGREEMENT', 'NOTE_DISAGREEMENT', 'NOTE_SCOPE_MISMATCH', 'LEAVE_OPEN', 'RESOLVED')
COORDINATOR_LABEL = 'Granite (coordinator; coordination only, never evidence)'
# Words that would make the coordinator decide, confirm, grade or promote (role V2 "must never"): refused in any turn.
DECIDING = ('confirm', 'proven', 'proves', 'survivor', 'promote', 'accept the claim', 'is true', 'is valid', 'is correct',
            'is wrong', 'reject', 'grade', 'score', 'tradable', 'signal is valid', 'i conclude', 'i decide', 'therefore the data')
ACTION_SCHEMA = {
    'type': 'object',
    'properties': {
        'item_id': {'type': 'string'},
        'action': {'type': 'string', 'enum': list(ACTIONS)},
        'seat': {'type': ['string', 'null'], 'enum': list(SEATS) + [None]},
        'text': {'type': 'string'},
        'cites': {'type': 'array', 'items': {'type': 'object',
                                             'properties': {'value': {'type': 'string'}, 'source_sha256': {'type': 'string'}},
                                             'required': ['value', 'source_sha256']}},
        'binds_to': {'type': ['string', 'null']},
    },
    'required': ['item_id', 'action', 'seat', 'text', 'cites', 'binds_to'],
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def witness_file(path):
    """Hash every byte sequentially without materializing a model-sized Python bytes object."""
    path = Path(path)
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return dict(path=str(path), bytes=size, sha256=digest.hexdigest())


def load_config(path=CONFIG):
    raw = Path(path).read_bytes()
    config = json.loads(raw)
    if config.get('schema') != 'FRANKIE_GRANITE_MEETING_RUNTIME_V1':
        raise ValueError('%s is not FRANKIE_GRANITE_MEETING_RUNTIME_V1' % path)
    return config, dict(path=str(path), bytes=len(raw), sha256=sha256_bytes(raw))


def gate(config, binary=None, model=None):
    """Every reason the model may NOT be called now; [] = the runtime may start. Explicit blanks refuse (Greg's habit)."""
    reasons = []
    pins = config.get('pins') or {}
    for key in ('model_repository', 'model_file', 'model_sha256', 'llama_cpp_release', 'llama_cpp_asset', 'llama_cpp_sha256'):
        if pins.get(key) in (None, ''):
            reasons.append('pin %s is an explicit blank in GRANITE_MEETING_RUNTIME_V1.json' % key)
    params = config.get('proposed_runtime_parameters') or {}
    if not params.get('confirmed') or not params.get('confirmed_by'):
        reasons.append('the runtime parameters are proposed, not confirmed (confirmed/confirmed_by)')
    else:
        cap, ctx, out = params.get('input_token_cap_per_call'), params.get('context_size'), params.get('max_output_tokens_per_turn')
        if not all(isinstance(v, int) and v > 0 for v in (cap, ctx, out)) or cap + out > ctx:
            reasons.append('input_token_cap_per_call + max_output_tokens_per_turn must fit inside context_size '
                           '(%r + %r vs %r): otherwise the server would shift context and drop seat material' % (cap, out, ctx))
    if binary is not None:
        reasons.extend(runtime_provenance(pins, binary)['reasons'])
    if model is not None:
        if not Path(model).is_file():
            reasons.append('model file is not at %s' % model)
        elif pins.get('model_sha256') and witness_file(model)['sha256'] != pins['model_sha256']:
            reasons.append('model file sha256 differs from the pin')
    return reasons


def runtime_provenance(pins, binary):
    """The chain pin -> archive -> extracted files. llama_cpp_sha256 is the ARCHIVE's hash, verified at fetch time by the
    setup script; the installed runtime is llama-server plus the shared libraries beside it, so the gate verifies the
    binary against llama_server_sha256 and every file of llama_cpp_files (the archive's extracted manifest) beside it.
    Comparing the extracted binary to the archive hash would refuse every correct install (Codex, 2026-10-06)."""
    reasons, verified = [], []
    path = Path(binary)
    if not path.is_file():
        return dict(reasons=['llama-server binary is not at %s' % binary], verified=verified)
    manifest = pins.get('llama_cpp_files') or {}
    server_sha = pins.get('llama_server_sha256')
    if not server_sha or not manifest:
        return dict(reasons=['pins llama_server_sha256 / llama_cpp_files are explicit blanks: the extracted runtime cannot be '
                             'verified (the archive hash llama_cpp_sha256 is not the binary\'s)'], verified=verified)
    actual = witness_file(path)['sha256']
    if actual != server_sha:
        reasons.append('llama-server binary sha256 %s differs from pin llama_server_sha256 %s' % (actual[:12], server_sha[:12]))
    root = path.parent
    for name, sha in sorted(manifest.items()):
        sibling = root / name
        if not sibling.is_file():
            reasons.append('extracted file %s missing beside llama-server' % name)
        elif witness_file(sibling)['sha256'] != sha:
            reasons.append('extracted file %s differs from pin llama_cpp_files' % name)
        else:
            verified.append(name)
    return dict(reasons=reasons, verified=verified, archive_sha256=pins.get('llama_cpp_sha256'),
                release=pins.get('llama_cpp_release'), asset=pins.get('llama_cpp_asset'))


def local_runtime(config=None, *, binary=None, model=None):
    """THE shared runtime definition (Greg, 2026-10-07): the pinned llama.cpp release and Granite 4.2 3B Q4_K_M
    weights of GRANITE_MEETING_RUNTIME_V1.json, the canonical install paths on the owning box, the thread rule and
    the exact install the box needs. The meeting and Jev both bind to this one definition, so a change to the
    Granite setup (pins, paths, threads, caps) carries to Jev automatically. `reasons` is the gate on the paths
    given (or the canonical ones): [] = the runtime may start; otherwise every reason names exactly what is missing.
    Never installs, downloads or starts anything."""
    if config is None:
        config, _ = load_config()
    pins = config.get('pins') or {}
    release = pins.get('llama_cpp_release') or '<llama_cpp_release pin blank>'
    model_file = pins.get('model_file') or '<model_file pin blank>'
    provenance = None
    if not binary:
        # The setup script extracts the pinned archive into ITS top directory under GRANITE_ROOT and writes
        # provenance.json beside llama-server after every verification passed; that receipt names the binary.
        # Without it the path is the unextracted placeholder and the gate refuses by name.
        for candidate in sorted(GRANITE_ROOT.glob('*/provenance.json')) if GRANITE_ROOT.is_dir() else []:
            try:
                body = json.loads(candidate.read_bytes())
            except (OSError, ValueError):
                continue
            if (body.get('schema') == 'FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1' and body.get('release') == release
                    and body.get('server_sha256') == pins.get('llama_server_sha256') and body.get('server')):
                binary, provenance = body['server'], witness_file(candidate)
                break
    binary = Path(binary) if binary else GRANITE_ROOT / ('<top directory of ' + str(pins.get('llama_cpp_asset') or 'the pinned asset') + '>') / 'llama-server'
    model = Path(model) if model else GRANITE_ROOT / str(model_file)
    reasons = gate(config, str(binary), str(model))
    if provenance is None and not Path(binary).is_file():
        reasons.append('the setup script (frankie_box_granite_meeting_setup.sh) has not written a provenance.json for release %s '
                       'under %s: the pinned archive is not extracted on this box' % (release, GRANITE_ROOT))
    host = os.cpu_count() or 1
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
    requirements = [
        dict(item='llama.cpp llama-server', release=release, asset=pins.get('llama_cpp_asset'),
             archive_sha256=pins.get('llama_cpp_sha256'), path=str(binary), binary_sha256=pins.get('llama_server_sha256'),
             extracted_files_beside_it=len(pins.get('llama_cpp_files') or {}),
             rule='the archive is fetched and sha256-verified by the setup script; the gate verifies llama-server and every '
                  'extracted file beside it against llama_cpp_files; libssl.so.3/libcrypto.so.3 come from the host'),
        dict(item='Granite GGUF weights', repository=pins.get('model_repository'), file=model_file, path=str(model),
             sha256=pins.get('model_sha256'), quantization=(config.get('settled') or {}).get('quantization')),
        dict(item='threads', rule=(config.get('proposed_runtime_parameters') or {}).get('threads_rule'),
             configured=(config.get('proposed_runtime_parameters') or {}).get('threads'), host_cpus=host,
             affinity_cpus=(len(affinity) if affinity is not None else None),
             note='a child inherits the owning lane\'s affinity; threads above the affinity count refuse at start'),
        dict(item='wrapper environment', LLAMA_SERVER=str(binary), GGUF_MODEL=str(model),
             rule='frankie_box_granite_meeting.sh passes --binary/--model from these; unset today means --inputs-only '
                  '(request to the wrapper owner: pass --route local instead so the gate refuses visibly)'),
        dict(item='CPU backend', expected='libggml-cpu-sapphirerapids.so on r7i (Sapphire Rapids; EC2 DescribeInstances '
                                           '2026-10-07: r7i.8xlarge main 16c/32t, r7i.4xlarge Linux 8c/16t)',
             recorded_at_run='runtime.effective.host_cpu (model name and the avx512/amx flags) in the meeting record'),
    ]
    return dict(schema=SHARED_RUNTIME_SCHEMA, route=DEFAULT_VOICE_ROUTE, routes=list(VOICE_ROUTES),
                binary=str(binary), model=str(model), setup_provenance=provenance,
                model_identity=(config.get('settled') or {}).get('model_identity'),
                quantization=(config.get('settled') or {}).get('quantization'), release=release,
                pins_sha256=sha256_bytes(json.dumps(pins, sort_keys=True).encode()),
                parameters=config.get('proposed_runtime_parameters'), requirements=requirements,
                installed=dict(binary=Path(binary).is_file(), model=Path(model).is_file()),
                reasons=reasons, status='ready' if not reasons else 'refused',
                rule='one shared runtime definition for the meeting and Jev; a blank pin, a missing or differing file '
                     'refuses visibly; nothing is installed or started here')


def host_cpu():
    """The host CPU as the kernel reports it (model name, the vector/matrix flags llama.cpp selects a backend by);
    recorded so the one-day run shows which CPU backend the pinned build could use. Unknown stays unknown."""
    try:
        text = Path('/proc/cpuinfo').read_text(encoding='utf-8', errors='replace')
    except OSError as error:
        return dict(available=False, reason=repr(error))
    model_name, flags = None, []
    for line in text.split('\n'):
        if model_name is None and line.startswith('model name'):
            model_name = line.split(':', 1)[1].strip()
        if not flags and line.startswith('flags'):
            flags = line.split(':', 1)[1].split()
    wanted = ('avx2', 'avx512f', 'avx512_vnni', 'avx512_bf16', 'amx_tile', 'amx_int8', 'amx_bf16')
    return dict(available=True, model_name=model_name, flags={f: (f in flags) for f in wanted},
                online_cpus=os.cpu_count(), affinity_cpus=(len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None))


# ------------------------------------------------------------------------------------------ what Granite is given
def _turn_fields(turn):
    """The seat's retained record fields a code answer may quote back (no private process, no grades: R09/R10)."""
    record = turn.get('record') or {}
    seat = turn.get('seat')
    common = dict(position=record.get('position'), reasoning=record.get('reasoning'),
                  evidence_checks=record.get('evidence_checks'), next_tests=record.get('next_tests'),
                  uncertainty=record.get('uncertainty'))
    if seat == 'boss_teacher':
        common.update(measured=turn.get('measured'), components=turn.get('components'), proposals=turn.get('proposals'))
    elif seat == 'scientific_teacher':
        common.update(counts_on_day=turn.get('counts_on_day'), counts_per_day=turn.get('counts_per_day'),
                      challenges_on_day=turn.get('challenges_on_day'), proposed_tests=turn.get('proposed_tests'),
                      untested=turn.get('untested'), cannot_test_yet=turn.get('cannot_test_yet'), day_text=turn.get('day_text'))
    elif seat == 'frankie':
        common.update(resolution=turn.get('resolution'), learned=record.get('learned'), next_steps=record.get('next_steps'),
                      remaining_disagreements=turn.get('remaining_disagreements'),
                      corrected_understanding=turn.get('corrected_understanding'))
    return {k: v for k, v in common.items() if v is not None}


def open_items_of(item, turns, side):
    """The open items code seeds from the seats' own records; Granite may add none of its own evidence to them."""
    out = []
    positions = {s: (t.get('record') or {}).get('position') for s, t in turns.items() if s != 'frankie'}
    if len(set(positions.values())) > 1:
        out.append(dict(kind='disagreement', seat=None, text='the BOSS teacher and the scientific teacher hold different '
                        'positions: %s' % json.dumps(positions, sort_keys=True), binds_to=None))
    science = side.get('scientific_teacher') or {}
    for p in science.get('proposed_tests') or []:
        out.append(dict(kind='proposed_test', seat='scientific_teacher', text=p.get('text'), binds_to=p.get('proposal_id')))
    for u in science.get('untested') or []:
        out.append(dict(kind='untested', seat='scientific_teacher', text=u, binds_to=u))
    for c in science.get('cannot_test_yet') or []:
        out.append(dict(kind='cannot_test_yet', seat='scientific_teacher',
                        text='%s: %s' % (c.get('series'), c.get('reason')) if isinstance(c, dict) else str(c),
                        binds_to=(c.get('series') if isinstance(c, dict) else str(c))))
    frankie = side.get('frankie') or {}
    for d in frankie.get('remaining_disagreements') or []:
        out.append(dict(kind='remaining_disagreement', seat='frankie', text=d, binds_to=d))
    return out


MATERIAL_STACKS = 'FRANKIE_ADVISER_MATERIAL_RENDER_V1'   # the layered material stacks (frankie_box_adviser_market.render_material)
ITEM_KEYS = ('item_id', 'author', 'author_label', 'claim', 'voiced', 'records', 'open_items')
ITEM_INSTRUCTION = 'Begin with this item. One action per reply.'


def _legacy_message(value):
    """The exact text a transcript message carried before the material stacks (json.dumps, sorted keys)."""
    return json.dumps(value, sort_keys=True)


def message_text(value, label, stacked, keep_texts=False):
    """(text, summary, render) of one message value: every existing lossless stack, layered where each still shortens
    and each proven by parse-back (frankie_box_adviser_market.render_material; Greg, 2026-10-07: every stack that works
    is used on everything Granite reads), when the meeting input carries them; else the legacy JSON bytes unchanged
    (a meeting bound to a legacy input keeps its exact prompts). The citation rule is untouched: the numbers a turn may
    voice are the ones in the seats' turn texts, lines and cites, all strings, which no stack rewrites."""
    if not stacked:
        return _legacy_message(value), None, None
    import frankie_box_adviser_market as AM
    render = AM.render_material(value, label=label, legacy_text=_legacy_message(value), keep_texts=keep_texts)
    return render['text'], AM.material_summary(render), (render if keep_texts else None)


def item_message(item, keep_texts=False):
    """The first user message of an item (the item's turns, records and open items, and the instruction)."""
    value = dict(item={k: item[k] for k in ITEM_KEYS}, instruction=ITEM_INSTRUCTION)
    return message_text(value, 'item %s' % item['item_id'], 'message_render' in item, keep_texts)


def context_text(given, keep_texts=False):
    """(text, summary, render) of the system prompt's retained meeting context section."""
    keys = ('knowledge_index', 'teachers_findings') + (('shared_market',) if 'shared_market' in given else ())
    return message_text({key: given[key] for key in keys}, 'retained meeting context', 'material_stacks' in given,
                        keep_texts)


def system_prompts(given, rules_ids):
    """(system prompt sent, the legacy system prompt): the charter and output contract, the retained meeting context
    (stacked when the input carries the material stacks, with the material legend once), and the whole shared market
    picture. The legacy prompt is byte-identical to the prompt before the material stacks (the before measurement)."""
    base = system_prompt(CHARTER.read_text(encoding='utf-8'), rules_ids)
    keys = ('knowledge_index', 'teachers_findings') + (('shared_market',) if 'shared_market' in given else ())
    picture = ''
    if 'shared_market_picture' in given:
        # Greg, 2026-10-07: the whole shared market picture, in the system prompt, once for every item. Its
        # numbers are context: a coordinator turn may still voice only numbers from a seat's turn.
        picture = ('\n\n## SHARED MARKET PICTURE (the whole picture the code seats stood under, at the teachers\' original '
                   'cutoff; context for coordination, never a source of new numbers for your turns; sha256 of the exact '
                   'typed picture %s)\n' % given['shared_market_picture']['picture_sha256']
                   + given['shared_market_picture']['text'])
    head = '\n\n## Retained meeting context (labels and findings summaries, not new evidence)\n'
    legacy = base + head + _legacy_message({key: given[key] for key in keys}) + picture
    if 'material_stacks' not in given:
        return legacy, legacy
    import frankie_box_adviser_market as AM
    return base + '\n\n' + AM.MATERIAL_LEGEND + head + context_text(given)[0] + picture, legacy


def _measure(server, messages, label):
    """{tokens} by the server tokenizer, or {tokens: None, reason}: a measurement, never a gate."""
    try:
        return dict(tokens=server.count_tokens(messages, label=label))
    except Exception as error:  # noqa: BLE001 - MeetingCallFailed / MeetingBudgetExpired are recorded, never raised here
        return dict(tokens=None, reason='%s: %s' % (type(error).__name__, str(error)[:200]))


def _layer_counts(server, render, label):
    """The server token count after each material layer (frankie_box_adviser_market.measure_layers)."""
    import frankie_box_adviser_market as AM
    if render is None:
        return None
    return AM.measure_layers(render, lambda text: server.count_tokens([dict(role='user', content=text)], label=label + '-layer'))


def material_record(given, basis, tokens):
    """The meeting's material-stack record: the encoding, why, every message's render summary (sizes before/after,
    layers adopted and refused, proof) and the server token counts (None before any server)."""
    stacks = given.get('material_stacks')
    return dict(schema=MATERIAL_STACKS, encoding=(stacks or {}).get('encoding') or 'legacy_json', basis=basis,
                context=(stacks or {}).get('context'),
                items={i['item_id']: i.get('message_render') for i in given.get('items') or []},
                legend=(None if stacks is None else dict(sha256=stacks.get('legend_sha256'), chars=stacks.get('legend_chars'))),
                tokens=tokens,
                rule='every existing lossless stack layered where each still shortens, each proven by parse-back to the exact '
                     'source; adoption is by characters at input time, the server token count of every layer is recorded '
                     'here at the meeting; nothing dropped, truncated or summarized')


def meeting_input(exchange, knowledge_index=None, *, stacks=True, notes=None):
    """Per item of Frankie's view: the three seats' voiced turns (text, lines, cites), their retained record fields,
    the code-seeded open items. Accumulated knowledge is listed by label and hash only (names, not content).
    stacks (default): the non-picture material is written through every proven layered stack (render_material); the
    input names the encoding and every message's render summary (sha256, chars before/after, layers), so the binding
    pins what each prompt carries. stacks=False: the legacy input, byte-identical to the input before the stacks (a
    retained binding of that input keeps its prompts and request identities).
    notes: an optional dict the caller owns; the item-render pool placement goes there (receipt only, never the input)."""
    import frankie_box_exchange_voice as V
    voiced = {i['item_id']: i for i in V.voice_input(exchange)['items']}
    items = []
    for item in exchange.get('items') or []:
        turns = {t['seat']: t for t in item.get('turns') or [] if t.get('seat') in SEATS and not t.get('withheld')}
        side = {s: _turn_fields(t) for s, t in turns.items()}
        items.append(dict(item_id=item['item_id'], author=item['author'], author_label=item['author_label'],
                          claim=item.get('claim'), lessons=item.get('lessons'),
                          voiced=voiced.get(item['item_id'], {}).get('turns') or [],
                          records=side, open_items=open_items_of(item, turns, side)))
    given = dict(schema=INPUT_SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                 exchange_hash=exchange.get('exchange_hash'), charter=witness_file(CHARTER) if CHARTER.is_file() else None,
                 teachers_findings=[dict(finding_id=f.get('finding_id'), kind=f.get('kind'), status=f.get('status'),
                                         scope=f.get('scope')) for f in exchange.get('teachers_findings') or []],
                 knowledge_index=knowledge_index or [], items=items,
                 rule='Granite is given these turns and lists; it adds no empirical content (role V2); Jev raw items are '
                      'not in this view (the lessons wall)')
    sources = exchange.get('sources') if isinstance(exchange.get('sources'), dict) else {}
    shared = sources.get('shared_market_context')
    if shared is not None:
        # Greg, 2026-10-07: the coordinator sees the WHOLE shared market picture the code seats stood under
        # (the complete typed picture at the teachers' original cutoff, spelled through the proven token stacks
        # and re-proven here), beside its exact reference (scope, clocks, hash, dispositions). The only accepted
        # cut is the per-call token cap, which refuses visibly in _meeting; nothing is trimmed. The number rule
        # stands: a coordinator turn may voice only numbers in a seat's turn (validate_action). A legacy exchange
        # without the context leaves the meeting input bytes unchanged.
        import frankie_box_adviser_market as AM
        picture_text = AM.text(shared)
        given['shared_market'] = dict(AM.reference(shared),
            role='the seats measured under this picture; Granite reads the whole picture as context and cites seat '
                 'values only; it adds no empirical content of its own (role V2)')
        given['shared_market_picture'] = dict(
            text=picture_text, sha256=sha256_bytes(picture_text.encode()), chars=len(picture_text),
            picture_sha256=shared.get('picture_sha256'), render=AM.render_summary(shared),
            delivery='whole: the complete typed picture at the original cutoff with its scope, read, coverage and all-99 '
                     'counts, as the system prompt section SHARED MARKET PICTURE; the per-call token cap is the only '
                     'accepted refusal and it is counted before any call',
            rule='context for coordination; numbers in a coordinator turn must still come from a seat\'s turn')
    if stacks:
        import frankie_box_adviser_market as AM
        given['material_stacks'] = dict(
            schema=MATERIAL_STACKS, encoding=AM.MATERIAL_ENCODING,
            legend_sha256=sha256_bytes(AM.MATERIAL_LEGEND.encode()), legend_chars=len(AM.MATERIAL_LEGEND),
            rule='the system prompt context and every transcript message (the item, a code seat answer, a recorded '
                 'request) are written through every existing lossless stack, layered where each still shortens, each '
                 'layer proven by parse-back to the exact source before it is adopted; each message is the shortest of '
                 'legacy JSON, compact JSON and the stacked text; the numbers a coordinator turn may voice are in the '
                 'seats\' turn texts, lines and cites (strings, never rewritten by a stack); nothing is dropped, '
                 'truncated or summarized')
        for item in items:
            item['message_render'] = None          # marks the item stacked; its summary is filled below
        # Every item's render (each layered stack proven by parse-back) is independent of the others: an ordered pinned
        # pool on the caller's lane CPUs when it has two or more (frankie_box_adviser_market.PinnedMap; a one-CPU slot,
        # such as the voice stage's adviser CPU, renders in-process exactly as before). Summaries are assigned in item
        # order; a worker failure is recomputed in-process at the item's turn. The pool forks before the context
        # render runs here, which then overlaps it.
        renders = AM.PinnedMap(_item_render, items, list(range(len(items))), label='meeting item renders')
        try:
            given['material_stacks']['context'] = context_text(given)[1]
            done = renders.results()
        finally:
            renders.close()
        for index, item in enumerate(items):
            ok, value = done[index]
            item['message_render'] = value if ok else item_message(item)[1]
        if notes is not None:
            notes['item_render_pool'] = renders.record
    return given


def _item_render(items, index):
    """One pinned-pool task: the unchanged render summary of item `index` (PinnedMap)."""
    return item_message(items[index])[1]


# ------------------------------------------------------------------------------------------ validation of a turn
def validate_action(value, item, turns_by_seat):
    """(accepted action, None) or (None, reason). Reuses the voice validator's number and wording rules."""
    import frankie_box_exchange_voice as V
    if not isinstance(value, dict) or set(value) != set(ACTION_SCHEMA['required']):
        return None, 'malformed coordinator turn (the contract is %s)' % sorted(ACTION_SCHEMA['required'])
    if value['item_id'] != item['item_id']:
        return None, 'the turn names another item (%r)' % value.get('item_id')
    if value['action'] not in ACTIONS:
        return None, 'unknown action %r' % value.get('action')
    if value['seat'] is not None and value['seat'] not in SEATS:
        return None, 'unknown seat %r' % value['seat']
    if value['binds_to'] is not None and not isinstance(value['binds_to'], str):
        return None, 'binds_to must be text or null'
    if not isinstance(value['cites'], list):
        return None, 'cites must be a list'
    text = value.get('text')
    if not isinstance(text, str) or not text.strip():
        return None, 'empty text'
    numbers, cited_all, shas_all = set(), {}, set()
    for turn in turns_by_seat.values():
        n, c, s = V._allowed(turn)
        numbers |= n
        for k, v in c.items():
            cited_all.setdefault(k, set()).update(v)
        shas_all |= s
    text_numbers = set(V.NUMBER.findall(text))
    for token in text_numbers:
        if token not in numbers:
            return None, 'the number %s is in no seat\'s turn on this item (role V2: never introduce empirical content)' % token
    for c in value.get('cites') or []:
        if (not isinstance(c, dict) or not isinstance(c.get('value'), str)
                or not isinstance(c.get('source_sha256'), str)):
            return None, 'malformed cite'
        v = str(c['value'])
        if v in cited_all:
            if c['source_sha256'] not in cited_all[v]:
                return None, 'the cited value %s did not come from %s in any turn' % (v, c['source_sha256'])
        elif v in numbers:
            if c['source_sha256'] not in shas_all:
                return None, 'the cited value %s names a file no turn cites' % v
        else:
            return None, 'the cited value %s is in no turn' % v
    missing_cites = text_numbers - {c['value'] for c in value['cites']}
    if missing_cites:
        return None, 'voiced numbers need their source cites: %s' % ', '.join(sorted(missing_cites))
    lower = text.lower()
    for w in V.POOLED:
        if w in lower:
            return None, 'pooled or computed wording %r (never calculate, pool or average)' % w
    for w in V.FORWARD:
        if w in lower:
            return None, 'forward or trade wording %r (never forecast, trade or advise)' % w
    for w in DECIDING:
        if w in lower:
            return None, 'deciding or confirming wording %r (Granite never grades, confirms, promotes or selects)' % w
    seat = value.get('seat')
    if value['action'] == 'ASK':
        if seat not in SEATS:
            return None, 'ASK needs a seat'
        if seat not in turns_by_seat:
            return None, 'the seat %s has no turn on this item' % seat
    if value['action'] == 'REQUEST_TEST':
        if seat != 'scientific_teacher':
            return None, 'a requested test is routed to the scientific teacher (the code test seat)'
        bound = value.get('binds_to')
        allowed = {o['binds_to'] for o in item['open_items'] if o.get('binds_to')}
        claim_id = (item.get('claim') or {}).get('claim_id')
        if claim_id:
            allowed.add(claim_id)
        if not bound or bound not in allowed:
            return None, ('the requested test is unbound: binds_to must be an existing proposal_id, claim_id or listed '
                          'untested text of this item (%r given); Granite names no new test of its own' % bound)
    if value['action'] == 'RESOLVED':
        if item['open_items']:
            return None, 'RESOLVED refused: the code seats still list open items; Granite never closes them'
        frankie = item['records'].get('frankie') or {}
        resolution = str(frankie.get('resolution') or '')
        if not resolution.startswith('RESOLVED_') or frankie.get('remaining_disagreements'):
            return None, ('RESOLVED refused: the code seats\' own records do not say so (Frankie\'s resolution %s, '
                          'remaining disagreements %s); Granite never decides' % (
                              resolution or 'none', json.dumps(frankie.get('remaining_disagreements') or [])))
    return dict(value, author=COORDINATOR_LABEL, evidentiary_weight=0), None


def seat_answer(seat, item):
    """The seat's own retained record, supplied by code. No new calculation; no private process (R09), no grades (R10)."""
    record = item['records'].get(seat)
    if record is None:
        return dict(seat=seat, kind='no_turn', content=None,
                    note='this seat has no turn on the item; nothing of its own to answer from')
    return dict(seat=seat, kind='retained_record', content=record,
                note='the seat\'s own exchange record, restated by code; a question needing a new calculation is a '
                     'requested test for the proper code stage, not an answer')


# ------------------------------------------------------------------------------------------ the model transport
CLAIMED_SLOT_THREADS = 1     # Greg, 2026-10-07: the meeting and Jev share ONE worker CPU of the day's held lane, threads=1


def threads_resolution(params):
    """How the runtime thread count is chosen, recorded on the record and the receipt (never assumed).
    threads null = the claimed adviser slot (one CPU, Greg 2026-10-07), NEVER the host's CPU count: the host count (32
    on the main box) refused at start inside a 16-CPU lane. An integer is clamped to the owning affinity (the CPUs the
    stage claim gave this process), not to the host."""
    host = os.cpu_count() or 1
    affinity = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
    wanted = params.get('threads')
    limit = affinity or host
    if wanted in (None, ''):
        threads, basis = CLAIMED_SLOT_THREADS, 'threads null: the claimed adviser slot (one lane CPU, threads=1; Greg, 2026-10-07)'
    else:
        threads = max(1, min(int(wanted), limit))
        basis = 'threads %s from %s, clamped to the owning affinity (%s CPUs)' % (
            wanted, params.get('threads_source') or 'the runtime definition', limit)
    return dict(threads=threads, requested=wanted, basis=basis, host_cpus=host, affinity_cpus=affinity,
                rule='null never resolves to the host CPU count; an integer never exceeds the claimed affinity')


def resolve_threads(params):
    """(threads, host CPU count); see threads_resolution for the rule (null = the claimed slot, 1)."""
    resolved = threads_resolution(params)
    return resolved['threads'], resolved['host_cpus']


class MeetingBudgetExpired(RuntimeError):
    """The meeting's time budget (max_meeting_seconds, settled) is spent: no further request is made.
    sent: False = no send attempted; True = a send was attempted (possibly partial); None = outside a request."""

    def __init__(self, message, sent=None):
        super().__init__(message)
        self.sent = sent


class MeetingCallFailed(RuntimeError):
    """A request to the ephemeral server failed or returned no usable reply; the whole evidence is retained by file.
    sent: False = no send was attempted; True = a send was attempted and transmission/completion may be unknown;
    None = not a transport question. A partial send must never be classified as never sent."""

    def __init__(self, message, evidence=None, sent=None):
        super().__init__(message)
        self.evidence = evidence
        self.sent = sent


class _DeadlineReader(io.RawIOBase):
    """Bound each actual socket read, including HTTP headers/chunk framing, and keep wire bytes."""

    def __init__(self, sock, timeout, chunks, transport):
        super().__init__()
        self.sock, self.timeout, self.chunks = sock, timeout, chunks
        self.transport = transport
        # SocketIO keeps the fd alive if HTTPConnection closes its socket on Connection: close.
        self.source = sock.makefile('rb', buffering=0)

    def readable(self):
        return True

    def readinto(self, buffer):
        self.sock.settimeout(self.timeout())
        count = self.source.readinto(buffer)
        if count is None:
            raise OSError('blocking HTTP socket returned no read result')
        if count:
            self.chunks.append(bytes(memoryview(buffer)[:count]))
        else:
            self.transport['eof'] = True
        return count

    def close(self):
        try:
            self.source.close()
        finally:
            super().close()


class _ResponseSocket:
    """Only the makefile boundary used by HTTPResponse; no replacement HTTP parser."""

    def __init__(self, sock, timeout, chunks, transport):
        self.sock, self.timeout, self.chunks = sock, timeout, chunks
        self.transport = transport

    def makefile(self, mode):
        if mode != 'rb':
            raise ValueError('unexpected HTTP response stream mode')
        return io.BufferedReader(_DeadlineReader(self.sock, self.timeout, self.chunks, self.transport))


class LlamaServer:
    """An ephemeral llama.cpp server: started for the meeting, stopped after it. Source-built, never run here.
    deadline (time.monotonic()) is the meeting's remaining budget: EVERY request (health wait, /apply-template,
    /tokenize, chat) is bounded by it, never by the 600 s transport ceiling alone (Codex finding 1, 2026-10-06).
    evidence_dir receives the server's whole stderr and every failed or malformed reply as durable files (finding 3)."""

    def __init__(self, binary, model, params, log=print, *, deadline=None, evidence_dir=None):
        self.binary, self.model, self.params, self.log = str(binary), str(model), params, log
        self.process, self.port, self.calls, self.tokens = None, None, 0, dict(prompt=0, completion=0)
        self.threads_resolution = threads_resolution(params)
        self.threads, self.host_cpus = self.threads_resolution['threads'], self.threads_resolution['host_cpus']
        self.last_usage = {}
        self.deadline = deadline
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        # 6R2: every process is an ATTEMPT with its own id; its stderr file and attempt record are named by it, so a retry
        # never appends to or renames a file an earlier witness pinned
        self.attempt = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + str(os.getpid())
        self.stderr_path, self._stderr_handle = None, None
        self.evidence = []
        self.cpus, self.placement = None, None

    def remaining(self):
        """Seconds of meeting budget left (None = no budget set)."""
        return None if self.deadline is None else self.deadline - time.monotonic()

    def _bounded(self, ceiling):
        remaining = self.remaining()
        if remaining is None:
            return ceiling
        if remaining <= 0:
            raise MeetingBudgetExpired('meeting time budget spent before the request (%s s)' % self.params.get('max_meeting_seconds'))
        return max(0.001, min(float(ceiling), remaining))

    def retain(self, label, data):
        """Durable file witness of whole bytes (no truncation): <evidence_dir>/<attempt>/<sha256>-<label>.bin, content-addressed
        WITHIN the attempt's own directory (6R2-F): a later attempt can never overwrite or renumber what an earlier witness
        pinned, and equal bytes retained by two attempts are two files, each attributable to its attempt."""
        from frankie_box_durable import write_bytes
        digest = sha256_bytes(data)
        if self.evidence_dir is None:
            return dict(label=label, bytes=len(data), sha256=digest, path=None, attempt=self.attempt)
        # per-attempt directory (6R2-F): an unfinished attempt's evidence stays attributable without a final record
        path = self.evidence_dir / self.attempt / ('%s-%s.bin' % (digest, re.sub(r'[^A-Za-z0-9._-]', '_', label)[:100]))
        if path.is_file():
            if sha256_bytes(path.read_bytes()) != digest:
                raise ValueError('evidence file %s does not carry the bytes its name declares' % path)
            witness = dict(bytes=len(data), sha256=digest)
        else:
            witness = write_bytes(path, data)
        item = dict(label=label, path=str(path), bytes=witness['bytes'], sha256=witness['sha256'], attempt=self.attempt)
        self.evidence.append(item)
        return item

    def stderr_witness(self):
        if self.stderr_path is None or not Path(self.stderr_path).is_file():
            return None
        if self._stderr_handle is not None:
            self._stderr_handle.flush()
        return dict(witness_file(self.stderr_path), attempt=self.attempt)

    def attempt_record(self, phase, status, **facts):
        """The immutable record of THIS attempt (6R2-F): <evidence_dir>/attempts/<attempt>-<phase>.json, write-once;
        phase 'start' is written BEFORE any process or model work (so a killed attempt is still discoverable) and
        phase 'end' carries the terminal result when one exists. A complete meeting lists every attempt, finished or not."""
        from frankie_box_durable import write_bytes
        doc = dict(schema='FRANKIE_GRANITE_MEETING_ATTEMPT_V1', attempt=self.attempt, phase=phase, status=status,
                   server_stderr=self.stderr_witness(), evidence=list(self.evidence), calls_this_attempt=self.calls,
                   tokens_this_attempt=dict(self.tokens), **facts)   # no clock inside: equal facts rewrite nothing
        if self.evidence_dir is None:
            return doc
        path = self.evidence_dir / 'attempts' / ('%s-%s.json' % (self.attempt, phase))
        data = (json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n').encode()
        if path.is_file():
            if path.read_bytes() != data:
                raise ValueError('attempt record %s already exists with other bytes' % path)
        else:
            write_bytes(path, data)
        return dict(doc, path=str(path))

    def _record_quietly(self, phase, status, **facts):
        """An attempt record written on a failure path: its own failure is logged, never allowed to replace the original
        error being raised (review finding, 2026-10-07)."""
        try:
            return self.attempt_record(phase, status, **facts)
        except Exception as error:
            self.log('attempt record %s/%s could not be written: %r' % (self.attempt, phase, error))
            return None

    @staticmethod
    def retained_attempts(evidence_dir):
        """Every attempt under <evidence_dir>/attempts/, oldest first, finished or not (6R2-F): its start record, its
        end record when one exists, its stderr file witness by name and the evidence files of its own directory (by
        content hash), so an attempt that died without a terminal record is carried forward with what it left."""
        root = Path(evidence_dir)
        directory = root / 'attempts'
        attempts = {}

        def entry_for(attempt):
            return attempts.setdefault(str(attempt), dict(attempt=str(attempt), start=None, end=None, unreadable_records=[]))
        if directory.is_dir():
            for path in sorted(directory.glob('*.json')):
                raw = path.read_bytes()
                try:
                    doc = json.loads(raw)
                except ValueError as error:
                    # a record truncated by a kill still names its attempt in the file name: listed, never skipped
                    stem = path.stem
                    attempt_id = stem[:-len('-start')] if stem.endswith('-start') else stem[:-len('-end')] if stem.endswith('-end') else stem
                    entry_for(attempt_id)['unreadable_records'].append(
                        dict(path=str(path), file_sha256=sha256_bytes(raw), file_bytes=len(raw), reason='not JSON: %s' % error))
                    continue
                entry = entry_for(doc.get('attempt'))
                entry[doc.get('phase') if doc.get('phase') in ('start', 'end') else 'end'] = dict(
                    doc, path=str(path), file_sha256=sha256_bytes(raw), file_bytes=len(raw))
        if root.is_dir():
            # an attempt that died before its start record was written still left its stderr file or evidence directory
            for path in sorted(root.glob('llama-server-stderr-*.log')):
                entry_for(path.name[len('llama-server-stderr-'):-len('.log')])
            for path in sorted(root.iterdir()):
                if path.is_dir() and path.name != 'attempts':
                    entry_for(path.name)
        out = []
        for attempt in sorted(attempts):
            entry = attempts[attempt]
            stderr = root / ('llama-server-stderr-%s.log' % attempt)
            files = []
            if (root / attempt).is_dir():
                for path in sorted((root / attempt).iterdir()):
                    if path.is_file():
                        files.append(dict(path=str(path), bytes=path.stat().st_size, sha256_by_name=path.name.split('-', 1)[0]))
            entry.update(finished=entry['end'] is not None,
                         server_stderr=witness_file(stderr) if stderr.is_file() else None,
                         evidence_files=files,
                         rule=('finished: its end record is the terminal result' if entry['end'] is not None else
                               'UNFINISHED: no terminal record exists' + ('' if entry['start'] is not None else
                               ' and no readable start record either (it died before or while writing it)') +
                               '; what it left (stderr, evidence, progress files marked pending) is carried as it is; '
                               'nothing is fabricated or re-sent on its behalf'))
            out.append(entry)
        return out

    def start(self, wait_seconds=600):
        try:
            return self._start(wait_seconds)
        except BaseException:
            try:
                self.stop()
            except Exception as error:
                self.log('server release after startup failure raised %r' % error)
            raise

    def _start(self, wait_seconds):
        available = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
        if available is not None and self.threads > len(available):
            raise MeetingCallFailed('configured %d runtime threads exceed the %d CPUs in the owning affinity; '
                                    'choose an explicit fitting thread configuration before launch' %
                                    (self.threads, len(available)), sent=False)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        command = [self.binary, '-m', self.model, '--host', '127.0.0.1', '--port', str(self.port),
                   '--ctx-size', str(int(self.params['context_size'])), '--threads', str(self.threads),
                   '--parallel', '1', '--no-context-shift', '--log-disable']
        # Explicit placement (Greg, 2026-10-07: every process pinned, physical-core aware): the server process is pinned,
        # before exec, to exactly `threads` CPUs of the owning affinity in physical-core order (distinct cores first), so
        # every thread llama.cpp creates inherits that set; on the claimed one-CPU adviser slot that is its one CPU.
        # The command line is unchanged; a refused pin keeps the inherited affinity and is recorded (L-2).
        self.cpus, self.placement = self._server_cpus(available)
        if self.params.get('cpu_only'):
            command += ['--n-gpu-layers', '0']
        # the server's stderr goes to a FILE, whole (never a pipe that nobody drains; never sliced)
        if self.evidence_dir is not None:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            self.stderr_path = self.evidence_dir / ('llama-server-stderr-%s.log' % self.attempt)   # per attempt, never appended across attempts
            if self.stderr_path.is_symlink() or self.stderr_path.exists():
                raise ValueError('server stderr path for this attempt already exists or is a symbolic link: %s' % self.stderr_path)
            self._stderr_handle = self.stderr_path.open('xb')
            stderr = self._stderr_handle
        else:
            stderr = subprocess.DEVNULL
        try:
            self.attempt_record('start', 'starting', command=command, port=self.port, threads=self.threads,
                                placement=self.placement)   # before any process work (6R2-F)
        except Exception:
            self._close_stderr()
            raise
        try:
            import threading
            before_exec = bool(self.cpus) and threading.active_count() == 1    # preexec_fn only when single-threaded
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stderr,
                                            preexec_fn=self._pin_child if before_exec else None)
            if self.cpus and not before_exec:
                try:          # other threads here: pin the new process right after the spawn instead
                    os.sched_setaffinity(self.process.pid, set(self.cpus))
                    self.placement['mode'] = 'after spawn (this process runs other threads)'
                except OSError as error:
                    self.placement['mode'] = 'inherited (after-spawn pin refused: %r)' % error
            elif self.cpus:
                self.placement['mode'] = 'before exec'

        except Exception as error:
            self._close_stderr()
            # _meeting owns the single terminal write and the bound runtime_failed receipt.
            raise MeetingCallFailed('llama-server could not be spawned (%r); stderr file: %s'
                                    % (error, json.dumps(self.stderr_witness(), sort_keys=True)), evidence=self.stderr_witness()) from error
        try:
            wait = self._bounded(wait_seconds)
        except MeetingBudgetExpired:
            self.stop()
            raise
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                code = self.process.returncode
                self.stop()
                raise MeetingCallFailed('llama-server exited while starting (returncode %s); its whole stderr is retained at %s'
                                        % (code, json.dumps(self.stderr_witness(), sort_keys=True)), evidence=self.stderr_witness())
            try:
                status, raw = self._request('GET', '/health', None, 'health', retain_transport_errors=False,
                                            ceiling=min(5.0, max(0.001, deadline - time.monotonic())))
                try:
                    health = json.loads(raw) if status < 400 else None
                except ValueError:
                    self.retain('health-malformed', raw)
                    raise
                if isinstance(health, dict) and health.get('status') == 'ok':
                    return
                if raw:
                    self.retain('health-unavailable-http-%s' % status, raw)
            except MeetingBudgetExpired:
                self.stop()
                raise
            except (MeetingCallFailed, ValueError, AttributeError, TypeError):
                pass          # not healthy yet; the loop re-checks the clock and the process
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
        self.stop()
        if self.remaining() is not None and self.remaining() <= 0:
            raise MeetingBudgetExpired('meeting time budget spent while llama-server was starting; stderr retained at %s'
                                       % json.dumps(self.stderr_witness(), sort_keys=True))
        raise MeetingCallFailed('llama-server did not report healthy within %s s; stderr retained at %s'
                                % (round(wait, 1), json.dumps(self.stderr_witness(), sort_keys=True)), evidence=self.stderr_witness())

    def _server_cpus(self, available):
        """(cpus, placement record): the first `threads` CPUs of the owning affinity in physical-core order."""
        if not available:
            return None, dict(cpus=None, basis='no affinity interface; the server inherits the owning affinity')
        try:
            import frankie_box_lane_pin as LP
            ordered, basis = LP.core_order(available)
        except Exception as error:  # noqa: BLE001 - placement never stops the meeting
            ordered, basis = sorted(available), 'plain sorted order (lane pin helper unavailable: %s)' % type(error).__name__
        cpus = ordered[:max(1, self.threads)]
        return cpus, dict(cpus=cpus, threads=self.threads, owning_affinity=sorted(available), basis=basis,
                          rule='the server process pinned before exec; its threads inherit the set; a refused pin keeps '
                               'the inherited affinity (the child cannot report it; the owning affinity bounds it)')

    def _pin_child(self):
        """preexec_fn: pin the server process before exec (never raises: a refusal keeps the inherited affinity)."""
        try:
            os.sched_setaffinity(0, set(self.cpus))
        except Exception:  # noqa: BLE001
            pass

    def _read_bounded(self, response, label, timeout, transport):
        """6R3-F: read a response body whole under the ABSOLUTE meeting deadline. Every blocking read is bounded by the
        remaining budget through the connection's own socket timeout (the connection is ours: http.client), and read1
        returns the bytes available rather than filling a buffer. Bytes already received are retained on the deadline,
        on a timeout, on a connection failure and on a truncated body, never replaced by an error string."""
        chunks = []
        try:
            while True:
                remaining = self.remaining()
                if remaining is not None and remaining <= 0:
                    raise socket.timeout('meeting deadline')
                timeout()  # Check buffered reads too; the raw reader sets the timeout before each recv.
                chunk = response.read1(65536)
                if not chunk:
                    if response.length not in (None, 0) or (response.chunked and transport['eof']):
                        raise http.client.IncompleteRead(b'', response.length)
                    return b''.join(chunks)
                chunks.append(chunk)
        except (socket.timeout, TimeoutError, ConnectionError, OSError, http.client.HTTPException, ValueError) as error:
            partial = b''.join(chunks) + (error.partial if isinstance(error, http.client.IncompleteRead) else b'')
            evidence = dict(self.retain('%s-partial-body' % label, partial), error=repr(error))
            if self.remaining() is not None and self.remaining() <= 0:
                raise MeetingBudgetExpired('meeting time budget spent while reading the %s reply body (%d bytes received and '
                                           'retained: %s)' % (label, len(partial), json.dumps(evidence, sort_keys=True)), sent=True)
            raise MeetingCallFailed('reading the %s reply body failed after %d bytes (%r); the received bytes are retained: %s'
                                    % (label, len(partial), error, json.dumps(evidence, sort_keys=True)), evidence=evidence, sent=True)

    def _request(self, method, route, body, label, retain_transport_errors=True, ceiling=600.0):
        """One HTTP exchange on a connection this meeting owns: (status, body bytes). Connect, send, headers and body
        are each bounded by the remaining budget; any transport or protocol failure is a MeetingCallFailed (or a
        MeetingBudgetExpired when the budget is spent) with whatever was received retained; the socket is always closed.
        The socket object is kept by reference: http.client drops conn.sock on a Connection: close reply while the
        response still reads from it, and the per-read deadline must keep holding there.
        retain_transport_errors=False (the health wait only): a refused connection while the server is still loading is
        expected and is not written as evidence on every poll."""
        # ceiling: the per-request transport ceiling (600 s for a model call; the health wait passes its own short one);
        # the remaining meeting budget always bounds below it
        try:
            timeout = self._bounded(ceiling)      # MeetingBudgetExpired here means: no request was sent
        except MeetingBudgetExpired as error:
            error.sent = False
            raise
        request_deadline = time.monotonic() + timeout
        if self.deadline is not None:
            request_deadline = min(request_deadline, self.deadline)

        def remaining_timeout():
            remaining = request_deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout('absolute HTTP request deadline')
            return remaining

        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        sock, sent, response = None, False, None
        wire = []
        transport = dict(eof=False)
        original_send = conn.send

        def send(data):
            nonlocal sent
            sock.settimeout(remaining_timeout())
            sent = True   # set BEFORE sendall: an exception can follow a partial transmission
            original_send(data)

        conn.send = send
        conn.response_class = lambda source, *args, **kwargs: http.client.HTTPResponse(
            _ResponseSocket(source, remaining_timeout, wire, transport), *args, **kwargs)
        try:
            try:
                encoded = None if body is None else json.dumps(body).encode()
                conn.timeout = remaining_timeout()
                conn.connect()
                sock = conn.sock
                sock.settimeout(remaining_timeout())
                conn.request(method, route, body=encoded,
                             headers={'Content-Type': 'application/json'} if body is not None else {})
                sock.settimeout(remaining_timeout())
                response = conn.getresponse()
            except MeetingBudgetExpired as error:
                error.sent = sent
                raise
            except (socket.timeout, TimeoutError, ConnectionError, OSError, http.client.HTTPException, ValueError) as error:
                evidence = (self.retain('%s-transport-error' % label, repr(error).encode()) if retain_transport_errors
                            else dict(label=label, error=repr(error), retained=False))
                if self.remaining() is not None and self.remaining() <= 0:
                    raise MeetingBudgetExpired('meeting time budget spent during %s (request sent: %s; %s)'
                                               % (route, sent, json.dumps(evidence, sort_keys=True)), sent=sent)
                raise MeetingCallFailed('%s failed with no reply (request sent: %s): %r (%s)'
                                        % (route, sent, error, json.dumps(evidence, sort_keys=True)), evidence=evidence, sent=sent)
            raw = self._read_bounded(response, label if response.status < 400 else '%s-http-%s' % (label, response.status),
                                     timeout=remaining_timeout, transport=transport)
            return response.status, raw
        finally:
            try:
                # Includes status/headers/framing received before a parsing error. Health connect
                # refusals have no wire bytes; received evidence is never suppressed with them.
                if wire:
                    self.retain('%s-http-wire' % label, b''.join(wire))
            finally:
                try:
                    if response is not None:
                        response.close()
                finally:
                    conn.close()

    def _post(self, route, body, label='request', expect=None):
        """POST and return (parsed, raw): the ORIGINAL bytes are kept beside the parsed value (6R3); `expect(parsed)` returns
        a reason the shape is unusable or None, and an unusable shape retains the raw bytes whole and raises
        MeetingCallFailed, never a KeyError/TypeError outside the meeting's own failure path. The per-request transport
        ceiling is params['call_ceiling_seconds'] (default CALL_CEILING_SECONDS; Jev's long CPU calls raise it from its
        approved runtime); the remaining meeting/process budget always bounds below it."""
        ceiling = float(self.params.get('call_ceiling_seconds') or CALL_CEILING_SECONDS)
        status, raw = self._request('POST', route, body, label, ceiling=ceiling)
        if status >= 400:
            evidence = self.retain('%s-http-%s' % (label, status), raw)
            if status == 404:
                raise MeetingCallFailed('the pinned llama-server has no %s route; the token count cannot be exact, so the meeting '
                                        'refuses rather than guess (reply retained: %s)' % (route, json.dumps(evidence, sort_keys=True)),
                                        evidence=evidence)
            raise MeetingCallFailed('%s returned HTTP %s (reply retained whole: %s)' % (route, status, json.dumps(evidence, sort_keys=True)),
                                    evidence=evidence)
        try:
            parsed = json.loads(raw)
        except ValueError as error:
            evidence = self.retain('%s-not-json' % label, raw)
            raise MeetingCallFailed('%s replied with bytes that are not JSON (%s); retained whole: %s'
                                    % (route, error, json.dumps(evidence, sort_keys=True)), evidence=evidence)
        why = expect(parsed) if expect is not None else None
        if why:
            evidence = self.retain('%s-unusable-shape' % label, raw)
            raise MeetingCallFailed('%s replied with an unusable shape (%s); the original bytes are retained whole: %s'
                                    % (route, why, json.dumps(evidence, sort_keys=True)), evidence=evidence)
        return parsed, raw

    @staticmethod
    def _expect_template(value):
        if not isinstance(value, dict) or not isinstance(value.get('prompt'), str):
            return 'expected an object with a text prompt'
        return None

    @staticmethod
    def _expect_tokens(value):
        if not isinstance(value, dict) or not isinstance(value.get('tokens'), list):
            return 'expected an object with a tokens list'
        return None

    @staticmethod
    def _expect_chat(value):
        if not isinstance(value, dict):
            return 'expected an object'
        choices = value.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return 'expected a non-empty choices list of objects'
        message = choices[0].get('message')
        if not isinstance(message, dict) or not isinstance(message.get('content'), str):
            return 'expected choices[0].message.content as text'
        usage = value.get('usage')
        if usage is not None:
            if not isinstance(usage, dict):
                return 'usage is not an object'
            for key in ('prompt_tokens', 'completion_tokens'):
                if usage.get(key) is not None and (isinstance(usage.get(key), bool) or not isinstance(usage.get(key), int)):
                    return 'usage.%s is not an integer' % key
        return None

    def count_tokens(self, messages, label='count'):
        """The input's exact token count as the server will see it: the chat template applied by the server itself
        (/apply-template), then its tokenizer with the special tokens (/tokenize add_special, the chat route's own
        setting). Reconciled against usage.prompt_tokens after each call (discuss_item records both). Both requests are
        side-effect free: an interruption here can be repeated without duplicating any model work."""
        template, _ = self._post('/apply-template', dict(messages=messages), label + '-apply-template', expect=self._expect_template)
        tokens, _ = self._post('/tokenize', dict(content=template['prompt'], add_special=True, parse_special=True),
                               label + '-tokenize', expect=self._expect_tokens)
        return len(tokens['tokens'])

    def chat(self, messages, schema, label='chat'):
        """One coordinator call; returns (content, raw reply bytes). The shape is validated with the original bytes kept."""
        body = dict(messages=messages, temperature=self.params['temperature'], top_p=self.params['top_p'],
                    max_tokens=int(self.params['max_output_tokens_per_turn']),
                    response_format=dict(type='json_schema', json_schema=dict(name='coordinator_turn', schema=schema)),
                    stream=False)
        reply, raw = self._post('/v1/chat/completions', body, label, expect=self._expect_chat)
        self.calls += 1
        usage = reply.get('usage') or {}
        self.last_usage = usage
        self.tokens['prompt'] += int(usage.get('prompt_tokens') or 0)
        self.tokens['completion'] += int(usage.get('completion_tokens') or 0)
        return reply['choices'][0]['message']['content'], raw

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def _close_stderr(self):
        if self._stderr_handle is not None:
            try:
                self._stderr_handle.flush()
                self._stderr_handle.close()
            finally:
                self._stderr_handle = None

    def stop(self):
        """Release the ephemeral process whatever state it is in; the stderr file stays (whole evidence)."""
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
        finally:
            self.process = None
            self._close_stderr()


# ------------------------------------------------------------------------------------------ the meeting
def system_prompt(charter_text, rules_ids):
    return (charter_text + '\n\n## Output contract (code-enforced)\n'
            'Reply with ONE JSON object: {"item_id", "action", "seat", "text", "cites", "binds_to"}. action is one of '
            '%s. ASK names the seat whose OWN statement you want clarified. REQUEST_TEST names seat scientific_teacher and '
            'binds_to an existing proposal_id, claim_id or listed untested text of the item. NOTE_* records an agreement, '
            'disagreement or scope mismatch between seats using only their own words and values. LEAVE_OPEN ends the item '
            'with what stays open. RESOLVED is accepted only when the seats\' own records already resolve it. Every number '
            'you write must appear in a seat\'s turn and be listed in cites with that file\'s sha256. You never calculate, '
            'pool, average, forecast, trade, grade, confirm, promote or select. Classroom rules in force: %s.'
            % (list(ACTIONS), ', '.join(rules_ids)))


def _durable_json_bytes(value):
    """The exact bytes frankie_box_durable.write_json would publish for value (same encoder settings), so a binding can
    name an input's sha256 before the file is written."""
    encoder = json.JSONEncoder(indent=1, sort_keys=True, default=str)
    return ''.join(encoder.iterencode(value)).encode('utf-8') + b'\n'


def _safe_name(item_id):
    return re.sub(r'[^A-Za-z0-9._-]', '_', str(item_id))[:80] + '-' + sha256_bytes(str(item_id).encode())[:12]


class ItemProgress:
    """Per-item durable progress (finding 2): completed rounds are written after every round through the existing
    durable writer (a rewrite retains the previous bytes beside it); a non-idempotent chat call is marked pending
    BEFORE it is sent and cleared only when its reply was received and recorded, so a restart knows exactly which call
    has unknown completion and never repeats it; everything is bound to the meeting's binding sha256."""

    def __init__(self, out_dir, item_id, binding_sha256):
        self.path = Path(out_dir) / 'progress' / (_safe_name(item_id) + '.json')
        self.item_id, self.binding_sha256 = item_id, binding_sha256

    def load(self):
        if not self.path.is_file():
            return None
        state = json.loads(self.path.read_bytes())
        if state.get('schema') != PROGRESS_SCHEMA or state.get('item_id') != self.item_id:
            raise ValueError('retained item progress %s is not this item\'s' % self.path)
        if state.get('binding_sha256') != self.binding_sha256:
            raise ValueError('retained item progress %s belongs to other meeting inputs (binding differs); move the meeting '
                             'directory aside, nothing is reused across inputs' % self.path)
        return state

    def save(self, state):
        from frankie_box_durable import write_json
        state = dict(state, schema=PROGRESS_SCHEMA, item_id=self.item_id, binding_sha256=self.binding_sha256,
                     saved_at=time.time())
        write_json(self.path, state)
        return state


def _close_item(item, state, outcome, open_item):
    """The item's record from its completed rounds (never from a call whose completion is unknown)."""
    open_items = list(item['open_items'])
    if open_item is not None:
        open_items.append(open_item)
    return dict(item_id=item['item_id'], author=item['author'], seat_statements=item['voiced'],
                coordinator_turns=state['coordinator'], code_seat_answers=state['answers'], notes=state['notes'],
                requested_tests=state['requests'], open_items=open_items, refused=state['refused'], outcome=outcome,
                token_counts=state['token_counts'], rounds_completed=state['rounds_completed'],
                pending_call_intent=state.get('pending_call'),
                rule='four categories kept apart; agreement among voices is never confirmation (R17)')


def discuss_item(server, item, system, params, log, progress=None, clock=None):
    """One item: rounds of coordinator turn -> code validation -> code seat answer, until LEAVE_OPEN/RESOLVED, the turn
    budget, the input cap, the MEETING time budget (every request bounded; finding 1) or a failed request (finding 3).
    Completed rounds are durable per item (finding 2): a retained complete item is reused without a call; a retained
    pending call (interrupted with unknown completion) is stamped unknown_completion, listed in the item's
    interrupted_calls and RE-DONE from the retained transcript (Greg, 2026-10-07 night: "re-done, never skipped");
    completed rounds of an interrupted item are kept and resumed from (an 'interrupted' item gets the caller's budget,
    liveness and cap checks like any item that will call).

    clock(call_key, outcome, wall_start, wall_end, **fields) (the meeting's model-evaluation clock, Greg 2026-10-07):
    every would-be coordinator call of a round is stamped once: answered (reply sha256, BEFORE the round's progress
    write), refused_over_cap (the counted input against the cap; no call), failed (with whether the request was sent),
    not_called (budget spent before sending) or unknown_completion (sent, no reply; or a retained pending intent found
    on restart). A reused complete item or a consumed retained outcome makes no call and no stamp. None = no clock."""
    def stamp(round_number, outcome, wall_start, wall_end, **fields):
        if clock is not None:
            clock('%s:r%d' % (_safe_name(item['item_id']), round_number), outcome, wall_start, wall_end, **fields)
    turns_by_seat = {t['seat']: t for t in item['voiced']}
    # the item's messages in the encoding its meeting input names (the proven material stacks, or the legacy JSON of
    # an input bound before them); a stacked item's first message must be the one its input summary pins
    stacked = 'message_render' in item
    first_message, first_render, _ = item_message(item)
    if stacked and (first_render or {}).get('sha256') != (item.get('message_render') or {}).get('sha256'):
        raise ValueError('item %s: the stacked first message differs from the one its meeting input pins' % item['item_id'])
    fresh = dict(status='in_progress', rounds_completed=0, coordinator=[], answers=[], requests=[], notes=[], refused=[],
                 token_counts=[], over_cap=None, outcome=None, pending_call=None, result=None,
                 transcript=[dict(role='system', content=system), dict(role='user', content=first_message)])
    state = progress.load() if progress is not None else None
    if state is not None and state.get('status') == 'complete' and isinstance(state.get('result'), dict):
        log('item %s: retained complete; reused without a model call' % item['item_id'])
        return dict(state['result'], reused_from_progress=True)
    if state is not None and state.get('pending_call'):
        # Greg, 2026-10-07 night (stacks pass): "a model call that was interrupted is re-done, never skipped". The
        # durable pre-send intent of the interrupted round is stamped unknown_completion (kept, never erased) and listed
        # on the item's progress (interrupted_calls); the round is then sent again from the SAME retained transcript (the
        # interrupted round was never appended to it), on this attempt's server. The completed rounds are reused as they
        # are. Formerly the item was closed LEFT_OPEN_BY_CODE without the call.
        pending = state['pending_call']
        log('item %s: a chat call of round %s was pending when the meeting was interrupted; stamped unknown_completion and '
            're-done from the retained transcript' % (item['item_id'], pending.get('round')))
        stamp(int(pending.get('round') or 0), 'unknown_completion',
              pending.get('started_at') if isinstance(pending.get('started_at'), (int, float)) else time.time(), None,
              reason='a durable pre-send intent of this round was found on restart with no recorded reply; transmission '
                     'and completion are unknown; the round is re-done from the retained transcript (never skipped)',
              transcript_sha256=pending.get('transcript_sha256'))
        retained_transcript = sha256_bytes(json.dumps(state.get('transcript', []), sort_keys=True).encode())
        if pending.get('transcript_sha256') not in (None, retained_transcript):
            raise ValueError('item %s: the interrupted round\'s transcript sha256 %s differs from the retained transcript '
                             '%s; the round cannot be re-done from it (explicit owner recovery)'
                             % (item['item_id'], pending.get('transcript_sha256'), retained_transcript))
        state = dict(state, status='in_progress', outcome=None, result=None, pending_call=None,
                     interrupted_calls=list(state.get('interrupted_calls') or []) + [dict(pending, redone=True)])
        state.pop('interrupted_call', None)
        if progress is not None:
            progress.save(state)
    if state is None:
        state = fresh
        if progress is not None:
            progress.save(state)
    elif (state.get('outcome') not in ('LEAVE_OPEN', 'RESOLVED') and state.get('over_cap') is None
          and state.get('transcript', [])[:2] != fresh['transcript']):
        raise ValueError('retained item transcript has another governed input or coordinator prompt; '
                         'keep its progress and resolve the input transition before another model call')
    transcript = state['transcript']
    cap = int(params['input_token_cap_per_call'])
    outcome, open_item = None, None
    label = _safe_name(item['item_id'])
    # 6R1: a retained terminal disposition (LEAVE_OPEN/RESOLVED recorded with its round) or a retained over-cap count is
    # consumed BEFORE any request: completed work whose disposition is already retained is never repeated
    if state.get('outcome') in ('LEAVE_OPEN', 'RESOLVED'):
        outcome = state['outcome']
        log('item %s: retained terminal outcome %s consumed; no call' % (item['item_id'], outcome))
    elif state.get('over_cap') is not None:
        log('item %s: retained over-cap count consumed; no call' % item['item_id'])
    # the round in flight and its wall start, for the clock on an exception path (stage: 'count' or 'chat')
    flight = dict(round=None, stage=None, started=None)
    try:
        for round_number in (range(int(state['rounds_completed']) + 1, int(params['max_coordinator_turns_per_item']) + 1)
                             if outcome is None and state.get('over_cap') is None else ()):
            flight.update(round=round_number, stage='count', started=time.time())
            counted = server.count_tokens(transcript, label='%s-r%d' % (label, round_number))
            if counted > cap:
                state['over_cap'] = dict(round=round_number, input_tokens=counted, cap=cap)
                stamp(round_number, 'refused_over_cap', flight['started'], time.time(), input_tokens=counted, cap=cap,
                      reason='round input counted with the server tokenizer over the per-call cap; no call, nothing trimmed')
                if progress is not None:
                    progress.save(state)       # the over-cap fact is retained before anything else happens
                break
            # the only non-idempotent request: marked pending BEFORE it is sent (finding 2)
            state['pending_call'] = dict(round=round_number, kind='chat', started_at=time.time(),
                                         transcript_sha256=sha256_bytes(json.dumps(transcript, sort_keys=True).encode()))
            if progress is not None:
                progress.save(state)
            flight.update(stage='chat', started=state['pending_call']['started_at'])
            raw, reply_bytes = server.chat(transcript, ACTION_SCHEMA, label='%s-r%d' % (label, round_number))
            # stamped BEFORE the round's progress write: a crash between the two leaves an answered stamp and a pending
            # intent; the restart then appends unknown_completion beside it (both kept, never one silently)
            stamp(round_number, 'answered', flight['started'], time.time(), reply_sha256=sha256_bytes(reply_bytes),
                  input_tokens_counted=counted,
                  prompt_tokens_used=(getattr(server, 'last_usage', None) or {}).get('prompt_tokens'),
                  attempt=server.attempt, transcript_sha256=state['pending_call']['transcript_sha256'])
            flight.update(stage=None)
            state['token_counts'].append(dict(round=round_number, counted_before_call=counted,
                                              prompt_tokens_used=(getattr(server, 'last_usage', None) or {}).get('prompt_tokens'),
                                              reply=server.retain('%s-r%d-reply' % (label, round_number), reply_bytes),
                                              attempt=server.attempt))
            try:
                value = json.loads(raw)
            except ValueError as error:
                evidence = server.retain('%s-r%d-not-one-json-object' % (label, round_number), raw.encode())
                state['refused'].append(dict(round=round_number, raw=raw, evidence=evidence,
                                             reason='not one JSON object (%s)' % error))
                transcript.append(dict(role='assistant', content=raw))
                transcript.append(dict(role='user', content='Refused by code: not one JSON object. Reply again with one object.'))
                state['pending_call'], state['rounds_completed'] = None, round_number
                if progress is not None:
                    progress.save(state)
                continue
            action, why = validate_action(value, item, turns_by_seat)
            transcript.append(dict(role='assistant', content=raw))
            if action is None:
                state['refused'].append(dict(round=round_number, turn=value, raw=raw, reason=why))
                transcript.append(dict(role='user', content='Refused by code: %s. Reply again within the contract.' % why))
                state['pending_call'], state['rounds_completed'] = None, round_number
                if progress is not None:
                    progress.save(state)
                continue
            action['round'] = round_number
            state['coordinator'].append(action)
            if action['action'] == 'ASK':
                answer = seat_answer(action['seat'], item)
                answer['round'] = round_number
                state['answers'].append(answer)
                transcript.append(dict(role='user', content=message_text(
                    dict(code_seat_answer=answer), 'item %s round %d code seat answer' % (item['item_id'], round_number), stacked)[0]))
            elif action['action'] == 'REQUEST_TEST':
                request = dict(schema=REQUEST_SCHEMA, item_id=item['item_id'], round=round_number, seat='scientific_teacher',
                               binds_to=action['binds_to'], text=action['text'], status='requested_not_run',
                               rule='executed only by the proper code stage; Granite never fabricates the answer')
                state['requests'].append(request)
                transcript.append(dict(role='user', content=message_text(
                    dict(recorded=request), 'item %s round %d recorded request' % (item['item_id'], round_number), stacked)[0]))
            elif action['action'].startswith('NOTE_'):
                state['notes'].append(dict(round=round_number, kind=action['action'], text=action['text'], cites=action['cites']))
                transcript.append(dict(role='user', content='Recorded (coordination only, never evidence). Continue.'))
            else:
                outcome = action['action']
            state['pending_call'], state['rounds_completed'] = None, round_number
            if outcome is not None:
                # 6R1: the terminal disposition is saved IN THE SAME WRITE as its completed round, with the result,
                # so an interruption after this round can only resume into the retained result, never into another chat
                result = _close_item(item, state, outcome, None)
                state = dict(state, status='complete', outcome=outcome, result=result)
                if progress is not None:
                    progress.save(state)
                return result
            if progress is not None:
                progress.save(state)
    except MeetingBudgetExpired as error:
        # the item keeps its completed rounds; the pending marker stays only when the request may have reached the
        # server (completion unknown); a request that provably never left this process is no pending call
        if getattr(error, 'sent', None) is False:
            state['pending_call'] = None
        if flight['stage'] is not None:
            sent = getattr(error, 'sent', None) if flight['stage'] == 'chat' else False
            stamp(flight['round'], 'unknown_completion' if sent is not False and flight['stage'] == 'chat' else 'not_called',
                  flight['started'], None if sent is not False and flight['stage'] == 'chat' else time.time(),
                  reason='the meeting time budget was spent during the %s of this round (%s)' % (
                      'chat call' if flight['stage'] == 'chat' else 'token count before any call', str(error)[:300]),
                  sent=sent)
        outcome = 'LEFT_OPEN_BY_CODE'
        open_item = dict(kind='time_budget', seat=None, binds_to=None, rounds_completed=int(state['rounds_completed']),
                         text='the meeting time budget of %s s was spent on this item after %d completed rounds (%s); the '
                              'completed work is kept and the item stays open by code' % (
                                  params['max_meeting_seconds'], int(state['rounds_completed']), error))
    except MeetingCallFailed as error:
        if getattr(error, 'sent', None) is False:
            state['pending_call'] = None      # never reached the socket: nothing to duplicate, not an unknown completion
        if flight['stage'] is not None:
            stamp(flight['round'], 'failed', flight['started'], time.time(),
                  reason='%s failed: %s' % ('the chat call' if flight['stage'] == 'chat' else
                                            'the token count (no call was sent)', str(error)[:300]),
                  sent=(getattr(error, 'sent', None) if flight['stage'] == 'chat' else False),
                  stage=flight['stage'], evidence=getattr(error, 'evidence', None))
        outcome = 'LEFT_OPEN_BY_CODE'
        open_item = dict(kind='call_failed', seat=None, binds_to=None, rounds_completed=int(state['rounds_completed']),
                         evidence=error.evidence, text='a request to the coordinator runtime failed after %d completed rounds: %s; '
                                                       'the whole evidence is retained by file, nothing is invented and the item '
                                                       'stays open by code' % (int(state['rounds_completed']), error))
    if outcome is None and state.get('over_cap') is not None:
        outcome = 'LEFT_OPEN_BY_CODE'
        over_cap = state['over_cap']
        open_item = dict(kind='input_cap', seat=None, binds_to=None,
                         text='round %d input of %d tokens exceeds the per-call cap of %d; nothing was truncated and '
                              'no call was made for it; the item stays open by code' % (
                                  over_cap['round'], over_cap['input_tokens'], over_cap['cap']))
    elif outcome is None:
        outcome = 'LEFT_OPEN_BY_CODE'
        open_item = dict(kind='turn_budget', seat=None, binds_to=None,
                         text='the coordinator turn budget of %d was spent without LEAVE_OPEN/RESOLVED; the item stays '
                              'open by code' % int(params['max_coordinator_turns_per_item']))
    result = _close_item(item, state, outcome, open_item)
    if state.get('pending_call'):
        # a chat was sent and no reply was recorded (budget or failure): the fact stays in the progress file, so a later
        # restart of an incomplete meeting stamps it unknown_completion and re-does the round (never skipped)
        state = dict(state, status='interrupted', outcome=outcome, result=result)
    else:
        state = dict(state, status='complete', outcome=outcome, result=result)
    if progress is not None:
        progress.save(state)
    return result


def meeting_workflow_report(out_dir, given, record, *, status, params=None, refusals=None, context=None, route=None):
    """One-day review record (Greg, 2026-10-07): what the meeting received, how the prompt used it, what it
    produced, every refusal and wait, the local-route requirements, the server-counted size of the whole-picture
    system prompt against the cap, and the all-99 coverage list with this piece's consumer rows. Recorded facts
    only; the coordinator transcript's content is not copied here. `context` is the exchange's full shared market
    context when the caller has it (the per-entry all-99 rows live there); `given['shared_market']` is its reference."""
    import frankie_box_adviser_market as AM
    out_dir = Path(out_dir)
    items = (record or {}).get('items') or []
    over_cap = [i['item_id'] for i in items if any((o or {}).get('kind') == 'input_cap' for o in i.get('open_items') or [])]
    interrupted = [i['item_id'] for i in items if any((o or {}).get('kind') == 'interrupted_call' for o in i.get('open_items') or [])]
    runtime = (record or {}).get('runtime') or {}
    shared = (given or {}).get('shared_market')
    picture = (given or {}).get('shared_market_picture')
    system_count = (record or {}).get('system_prompt_tokens')
    not_discussed = (record or {}).get('not_discussed') or []
    return AM.workflow_report('meeting', context=(context if context is not None else shared),
        consumer=dict(knowledge=('knowledge_index: %d documents by label and hash' % len((given or {}).get('knowledge_index') or []))
                                if (given or {}).get('knowledge_index') else None,
                      lessons=('teachers_findings: %d' % len((given or {}).get('teachers_findings') or []))
                              if (given or {}).get('teachers_findings') else None,
                      directive=(given or {}).get('charter'), brain=(record or {}).get('brain'),
                      carry=None,
                      walls='Jev raw items withheld (the lessons wall); seat private process and grades never given (R09/R10); '
                            'numbers only from seat turns (validate_action)',
                      outputs=dict(record='meeting.json', categories=['seat_statements', 'coordinator_turns',
                                                                        'code_seat_answers', 'open_items/requested_tests'])),
        inputs=dict(exchange=(record or {}).get('exchange'), charter=(given or {}).get('charter'),
                    meeting_input=witness_file(out_dir / 'meeting-input.json') if (out_dir / 'meeting-input.json').is_file() else None,
                    items=len((given or {}).get('items') or []), knowledge_index=len((given or {}).get('knowledge_index') or []),
                    teachers_findings=len((given or {}).get('teachers_findings') or []),
                    shared_market_context=('absent: the exchange carries no shared market context (legacy teacher)'
                                           if shared is None else 'present: the exact reference and the WHOLE picture text in the meeting input'),
                    shared_market_picture_text=(None if picture is None else
                                                dict(chars=picture['chars'], sha256=picture['sha256'], render=picture.get('render'))),
                    route=route or (record or {}).get('route')),
        use=dict(prompt=dict(system='charter, output contract, retained meeting context (knowledge_index, teachers_findings'
                                    + (', shared_market reference) and the section SHARED MARKET PICTURE (the whole picture text)'
                                       if picture is not None else ')'),
                             system_prompt_tokens=system_count,
                             per_item='item_id, author, claim, voiced seat turns, retained seat records, code-seeded open items'),
                 placement=dict(server=(runtime.get('effective') or {}).get('placement'),
                                rule='the llama-server process pinned to its threads\' CPUs of the claimed slot; placement only'),
                 material_stacks=_material_report(given, record),
                 picture_delivery=(None if picture is None else dict(
                     delivered=picture['delivery'], chars=picture['chars'],
                     tokens=dict(system_prompt_counted=system_count, cap=(params or {}).get('input_token_cap_per_call'),
                                 rule='counted once with the server tokenizer before any call; the whole picture is in that count; '
                                      'an over-cap system prompt leaves EVERY item open by code (input_cap_system_prompt), no call, nothing trimmed'),
                     canary=dict(source_chars=((picture.get('render') or {}).get('source_chars')),
                                 stacked_chars=picture['chars'], stacked_tokens=system_count,
                                 rule='the token stacks\' effect is this count against the exact typed text; measured at the one-day run'))),
                 withheld=['Jev raw items (the lessons wall)', 'seat private process and grades (R09/R10)',
                           'nothing of the shared market picture is withheld (Greg, 2026-10-07); the cap refuses visibly instead'],
                 caps=dict(input_token_cap_per_call=(params or {}).get('input_token_cap_per_call'),
                           context_size=(params or {}).get('context_size'),
                           max_output_tokens_per_turn=(params or {}).get('max_output_tokens_per_turn'),
                           max_coordinator_turns_per_item=(params or {}).get('max_coordinator_turns_per_item'),
                           max_meeting_seconds=(params or {}).get('max_meeting_seconds'),
                           call_ceiling_seconds=(params or {}).get('call_ceiling_seconds') or CALL_CEILING_SECONDS,
                           refused_over_cap_items=over_cap,
                           refused_over_cap_system_prompt=[n.get('item_id') for n in not_discussed
                                                           if n.get('kind') == 'input_cap_system_prompt'],
                           refused_turns=sum(len(i.get('refused') or []) for i in items),
                           rule='an over-cap input makes no call and leaves the item open; nothing is truncated'),
                 model_calls=(record or {}).get('model_calls', 0), calls=(record or {}).get('calls'),
                 refused_to_run=refusals or [], interrupted_call_items=interrupted,
                 local_route=(record or {}).get('local_route'),
                 host_cpu=(runtime.get('effective') or {}).get('host_cpu'),
                 budget=dict(seconds=runtime.get('budget_seconds'), left=runtime.get('budget_left_seconds'),
                             phases=(record or {}).get('timings'))),
        outputs=dict(status=status, record=witness_file(out_dir / 'meeting.json') if (out_dir / 'meeting.json').is_file() else None,
                     binding=(record or {}).get('binding'), counts=(record or {}).get('counts'),
                     not_discussed=[n.get('item_id') for n in not_discussed],
                     publication=(record or {}).get('publication'),
                     waits=[n.get('reason') for n in not_discussed],
                     # FRANKIE_MODEL_EVALUATION_CLOCK_V1 (frankie_box_model_clock): the day clock file this meeting
                     # stamped, the cutoff its input was cut at, every record of this attempt and any not recorded
                     model_clock=(record or {}).get('model_clock'),
                     threads=((runtime.get('effective') or {}).get('threads_resolution'))))


def _material_report(given, record):
    """The one-day review's view of the material stacks: what was stacked, the sizes before and after every layer, the
    server token counts before and after each layer, and what was refused and why (recorded facts only)."""
    material = (record or {}).get('material')
    if material is None:
        stacks = (given or {}).get('material_stacks')
        return dict(encoding=(stacks or {}).get('encoding') or 'legacy_json', recorded=False,
                    reason='the meeting record carries no material block (an earlier record format)')
    def sizes(summary):
        if not summary:
            return None
        return dict(encoding=summary.get('encoding'), legacy_chars=(summary.get('legacy') or {}).get('chars'),
                    delivered_chars=summary.get('chars'), source=summary.get('source'),
                    layers=[{k: r.get(k) for k in ('layer', 'chars', 'adopted', 'reason')} for r in summary.get('layers') or []],
                    refused=summary.get('refused'), counts=summary.get('counts'))
    return dict(encoding=material.get('encoding'), basis=material.get('basis'), context=sizes(material.get('context')),
                items={k: sizes(v) for k, v in (material.get('items') or {}).items()},
                tokens=material.get('tokens'), legend=material.get('legend'), rule=material.get('rule'))


def publish_meeting_record(exchange_path, out_dir, brain=None, *, include_inputs=True):
    """Finish publication from retained complete bytes, including after an interrupted receipt write."""
    import frankie_box_brain as BR
    from frankie_box_durable import write_json
    out_dir = Path(out_dir)
    record_path = out_dir / 'meeting.json'
    pin = witness_file(record_path)
    receipt_path = out_dir / 'receipt.json'
    if receipt_path.is_file():
        previous = json.loads(receipt_path.read_bytes())
        if previous.get('status') == 'complete':
            old_pin = previous.get('record') or {}
            if any(old_pin.get(k) != pin[k] for k in ('bytes', 'sha256')):
                raise ValueError('completed meeting differs from its retained receipt; never re-pinned')
    record = BR.read_meeting_record(record_path, exchange_path=exchange_path, expected_sha256=pin['sha256'])
    publication = 'retained; awaiting return to the owning lane brain'
    brain_entry = None
    if brain:
        manifest, _ = BR.write_meeting_entry(brain, record['day'], record_path, exchange_path=exchange_path)
        entry = Path(brain) / manifest.get('entry_name', '%s-meeting' % record['day'])
        brain_entry = dict(path=str(entry), manifest=witness_file(entry / 'MANIFEST.json'))
        publication = 'published immediately to the owning lane brain'
    receipt = dict(schema=RECEIPT_SCHEMA, day=record['day'], status='complete',
                   record=pin, counts=record.get('counts'),
                   model_calls=record['model_calls'], tokens=record.get('tokens'),
                   publication=publication, brain_entry=brain_entry, seconds=record.get('seconds'),
                   # the thread resolution (null = the claimed slot, 1) and the model clock of this meeting, as recorded
                   threads=((record.get('runtime') or {}).get('effective') or {}).get('threads_resolution'),
                   model_clock=record.get('model_clock'),
                   # the material stacks: encoding, per-message sizes before/after each layer, server token counts
                   material=record.get('material'))
    inputs = out_dir / 'meeting-input.json'
    if include_inputs and inputs.is_file():
        receipt['inputs'] = witness_file(inputs)
    given = json.loads(inputs.read_bytes()) if inputs.is_file() else None
    try:
        exchange_sources = json.loads(Path(exchange_path).read_bytes()).get('sources') or {}
        context = exchange_sources.get('shared_market_context') if isinstance(exchange_sources, dict) else None
    except (OSError, ValueError):
        context = None
    receipt['workflow_report'] = meeting_workflow_report(out_dir, given, record, status='complete',
                                                         params=(record.get('runtime') or {}).get('parameters'),
                                                         context=context, route=record.get('route'))
    write_json(out_dir / 'receipt.json', receipt)
    return receipt


def meeting(exchange_path, out_dir, **kwargs):
    """Serialize a day's meeting and publication repair without replaying a completed model call."""
    import fcntl
    out_dir = Path(out_dir)
    if any(p.is_symlink() for p in (out_dir, *out_dir.parents)):
        raise ValueError('meeting output traverses a symbolic link')
    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path = out_dir / '.meeting.lock'
    if lock_path.is_symlink():
        raise ValueError('meeting lock is a symbolic link')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _meeting(exchange_path, out_dir, **kwargs)


def _meeting(exchange_path, out_dir, *, config_path=CONFIG, binary=None, model=None, brain=None, inputs_only=False,
            log=print, route=DEFAULT_VOICE_ROUTE, threads=None):
    import frankie_box_classroom_code as K
    from frankie_box_durable import write_json
    exchange_path, out_dir = Path(exchange_path), Path(out_dir)
    if route not in VOICE_ROUTES:
        raise ValueError('unknown voice route %r (routes: %s)' % (route, ', '.join(VOICE_ROUTES)))
    timings = {}            # where the meeting's time went, per phase (Greg, 2026-10-07: show where a run spends its time)
    phase_started = time.time()
    def phase(name):
        nonlocal phase_started
        now = time.time()
        timings[name] = round(now - phase_started, 3)
        phase_started = now
        try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
            import frankie_box_stage_progress as _SP
            _SP.report_phase('meeting: %s done' % name, units_done=len(timings), unit='phases')
        except Exception:  # noqa: BLE001
            pass
    raw = exchange_path.read_bytes()
    exchange = json.loads(raw)
    if exchange.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or exchange.get('view') != 'frankie':
        raise SystemExit('the meeting is given Frankie\'s view of the exchange only (view frankie)')
    shared_context = (exchange.get('sources') or {}).get('shared_market_context') if isinstance(exchange.get('sources'), dict) else None
    retained = out_dir / 'meeting.json'
    if retained.is_file():
        import frankie_box_brain as BR
        previous = BR.read_meeting_record(retained, exchange_path=exchange_path, complete=False)
        if previous['status'] == 'complete':
            return publish_meeting_record(exchange_path, out_dir, brain)
    config, config_witness = load_config(config_path)
    # The one shared runtime definition (local route): the canonical paths stand in for absent --binary/--model so
    # the gate names exactly what the box lacks instead of a silent inputs-only run.
    shared_runtime = local_runtime(config, binary=binary, model=model)
    if route == 'local' and not inputs_only:
        binary, model = shared_runtime['binary'], shared_runtime['model']
    _, rules = K.rules()
    rules_witness = dict(file=Path(rules['path']).name, sha256=rules['sha256'], bytes=rules['bytes'], rules=rules['rules'])
    knowledge_index, knowledge_listed = [], []
    if brain:
        import frankie_box_lane_state as LS
        selected = LS.learner_knowledge(str(exchange['day']), 'voice', brain=brain)
        knowledge_index = [{k: d[k] for k in ('label', 'day', 'kind', 'path', 'sha256')} for d in selected['documents']]
        # what the selection left out and why (excluded by the source manifest, unreadable, ...): recorded on the
        # meeting record, never silently dropped; not part of the meeting input (its identity is unchanged)
        knowledge_listed = list(selected.get('listed') or [])
    given = meeting_input(exchange, knowledge_index)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 6R2: the input bytes are computed first (the durable writer's own encoding) and the retained binding is validated
    # against them BEFORE meeting-input.json is touched: a changed-input retry refuses without mutating the file the old
    # binding names; equal bytes are written (or found) once
    input_bytes = _durable_json_bytes(given)
    input_path = out_dir / 'meeting-input.json'
    binding_path = out_dir / 'meeting-binding.json'
    material_basis = 'the proven material stacks (meeting input names material_stacks)'
    if binding_path.is_file() and json.loads(binding_path.read_bytes()).get('input', {}).get('sha256') != sha256_bytes(input_bytes):
        # a meeting bound BEFORE the material stacks keeps its exact input, prompts and request identities: when the
        # retained binding names the legacy input of this same exchange, that input is used unchanged
        legacy = meeting_input(exchange, knowledge_index, stacks=False)
        legacy_bytes = _durable_json_bytes(legacy)
        if json.loads(binding_path.read_bytes()).get('input', {}).get('sha256') == sha256_bytes(legacy_bytes):
            given, input_bytes = legacy, legacy_bytes
            material_basis = ('legacy: the retained binding names the input written before the material stacks; its '
                              'prompts and request identities are kept unchanged')
    phase('inputs')
    if binding_path.is_file() and json.loads(binding_path.read_bytes()).get('input', {}).get('sha256') != sha256_bytes(input_bytes):
        raise ValueError('retained meeting progress under %s belongs to other inputs (the binding names another input); move it '
                         'aside, nothing is reused across inputs and nothing retained is changed' % out_dir)
    if input_path.is_file() and input_path.read_bytes() != input_bytes:
        if binding_path.is_file():
            raise ValueError('retained meeting-input.json under %s differs from this input while a binding is retained; move it '
                             'aside, nothing retained is changed' % out_dir)
        from frankie_box_durable import write_bytes
        write_bytes(input_path, input_bytes)      # an inputs-only or refused run's file, no binding: replaced durably (old bytes retained beside)
    elif not input_path.is_file():
        from frankie_box_durable import write_bytes
        write_bytes(input_path, input_bytes)
    started = time.time()
    local_route = dict(shared_runtime, requested_route=route,
                       github_route='listed fallback (frankie_granite_meeting.yml), unused on the local route')
    base = dict(schema=SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                exchange=dict(path=str(exchange_path), sha256=sha256_bytes(raw), exchange_hash=exchange.get('exchange_hash')),
                charter=given['charter'], rules=rules_witness, runtime_config=config_witness,
                coordinator=dict(label=COORDINATOR_LABEL, model_identity=config['settled']['model_identity'],
                                 quantization=config['settled']['quantization'], runtime=config['settled']['runtime']),
                knowledge_index=knowledge_index, knowledge_listed=knowledge_listed, route=route, local_route=local_route,
                brain=brain, material=material_record(given, material_basis, None),
                shared_market_picture=(None if 'shared_market_picture' not in given else
                                       {k: given['shared_market_picture'][k] for k in ('sha256', 'chars', 'picture_sha256', 'delivery')}))
    # The model-evaluation clock (FRANKIE_MODEL_EVALUATION_CLOCK_V1, frankie_box_model_clock; Greg, 2026-10-07): one
    # record per real (or refused / not-made) coordinator call into <run-dir>/days/<day>/model-clock.jsonl, with the
    # exact market cutoff of the meeting input (the shared market context's original scope and cutoff clocks), the
    # shared runtime pins and the lane. Written after the day's classroom; never read by that day's classroom.
    import frankie_box_model_clock as MC
    clock_state = dict(prefix='meeting:x%s' % sha256_bytes(raw)[:16], attempt=None,
                       model=dict(definition=SHARED_RUNTIME_SCHEMA, release=shared_runtime['release'],
                                  pins_sha256=shared_runtime['pins_sha256'], model_identity=shared_runtime['model_identity'],
                                  quantization=shared_runtime['quantization'], config=config_witness, threads=None,
                                  cpus=(sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None)))
    clock_run_dir = MC.run_dir_of(out_dir, exchange.get('run'), exchange.get('day'))
    clock_cutoff = MC.cutoff_of(given.get('shared_market'))
    clock_results = []

    def clock(call_key, outcome, wall_start, wall_end, **fields):
        try:
            record = dict(schema=MC.SCHEMA, piece='meeting', run=exchange.get('run'), day=str(exchange.get('day')),
                          lane=dict(host=socket.gethostname(), booking=os.environ.get('FRANKIE_CPU_BOOKING'),
                                    booked_cpus=os.environ.get('FRANKIE_BOOKED_CPUS'),
                                    lane_cpus=os.environ.get('FRANKIE_LANE_CPUS'), attempt=clock_state['attempt']),
                          call_id='%s:%s' % (clock_state['prefix'], call_key), model=clock_state['model'],
                          cutoff=clock_cutoff, wall_start=wall_start, wall_end=wall_end, outcome=outcome, **fields)
            result = MC.record_or_list(clock_run_dir, str(exchange.get('day')), record, out_dir)
        except Exception as error:      # noqa: BLE001 - the clock is accounting; its failure is listed on the record
            result = dict(recorded=False, call_id=call_key, reason='%s: %s' % (type(error).__name__, str(error)[:300]))
        clock_results.append(dict(result, outcome=outcome))
        if not result.get('recorded'):
            log('meeting %s: model clock record for %s not recorded in the day clock (%s)' % (
                exchange.get('day'), call_key, result.get('reason')))
        return result

    def clock_summary():
        return dict(path=None if clock_run_dir is None else str(MC.clock_path(clock_run_dir, exchange.get('day'))),
                    run_dir=None if clock_run_dir is None else str(clock_run_dir), cutoff=clock_cutoff,
                    stamped_this_attempt=list(clock_results),
                    unrecorded=[r for r in clock_results if not r.get('recorded')],
                    rule='one FRANKIE_MODEL_EVALUATION_CLOCK_V1 record per coordinator call or refused/not-made call of '
                         'this attempt; reused rounds and items make no call and no record; ' + MC.CAUSALITY)
    refusals = gate(config, binary, model) if not inputs_only else []
    if inputs_only or refusals:
        if inputs_only and local_route['reasons']:
            # the local route's requirements are named on an inputs-only receipt too (what the box still needs)
            refusals = ['inputs only; the local runtime would refuse: ' + r for r in local_route['reasons']]
        now = time.time()
        clock('gate', 'not_called', now, now,
              reason=('inputs only: zero model calls by request' if inputs_only else
                      'the runtime gate refused the meeting: ' + '; '.join(refusals)[:900]))
        record = dict(base, status='inputs_only' if inputs_only else 'refused', refused_to_run=refusals,
                      items=[], model_calls=0, publication='none', timings=timings, model_clock=clock_summary())
        write_json(out_dir / 'meeting.json', record)
        receipt = dict(schema=RECEIPT_SCHEMA, day=exchange.get('day'), status=record['status'], refused_to_run=refusals,
                       inputs=witness_file(out_dir / 'meeting-input.json'), record=witness_file(out_dir / 'meeting.json'),
                       model_calls=0, seconds=round(time.time() - started, 1), route=route, local_route=local_route,
                       model_clock=record['model_clock'], material=record.get('material'),
                       workflow_report=meeting_workflow_report(out_dir, given, record, status=record['status'],
                                                              params=config.get('proposed_runtime_parameters'),
                                                              refusals=refusals, context=shared_context, route=route))
        write_json(out_dir / 'receipt.json', receipt)
        log('meeting %s: %s (%s)' % (exchange.get('day'), record['status'], '; '.join(refusals) or 'inputs written'))
        return receipt
    params = config['proposed_runtime_parameters']
    if threads is not None:
        # the caller's lane placement (Greg, 2026-10-07: the meeting and Jev share ONE worker CPU of the day's held lane
        # at threads=1): every other row stays the definition's; the value is bound into the binding and the record
        # The source text is part of the binding: the one-CPU slot keeps its original words (a retained binding of that
        # placement keeps its bytes and call identities); a lane placement (Greg, 2026-10-07 night: the meeting on the
        # whole held lane, MEETING_THREADS defaulting to the lane size) says what it is.
        # (the affinity size stays out of the text: it is recorded in runtime.effective, and a resume on the same threads
        # keeps the same binding)
        source = ('caller: the day lane\'s shared adviser CPU slot' if int(threads) == 1 else
                  'caller: %d llama-server threads on the day\'s held lane (MEETING_THREADS), clamped to the owning '
                  'affinity and pinned in physical-core order' % int(threads))
        params = dict(params, threads=int(threads), threads_source=source)
    # finding 2: the exact inputs every call of this meeting is bound to, written ONCE; retained progress of other
    # inputs is refused (never reused across inputs); the binding sha256 travels in every progress file
    binding = dict(schema=BINDING_SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                   exchange=base['exchange'], input=witness_file(out_dir / 'meeting-input.json'),
                   charter=given['charter'], rules=rules_witness, runtime_config=config_witness,
                   pins_sha256=sha256_bytes(json.dumps(config.get('pins') or {}, sort_keys=True).encode()),
                   parameters=params, binary=witness_file(binary), model=witness_file(model),
                   rule='every model call of this meeting is bound to these inputs; progress files name this binding')
    binding_bytes = (json.dumps(binding, indent=1, sort_keys=True) + '\n').encode()
    if binding_path.is_file():
        if binding_path.read_bytes() != binding_bytes:
            raise ValueError('retained meeting progress under %s belongs to other inputs (binding differs); move it aside, '
                             'nothing is reused across inputs' % out_dir)
    else:
        from frankie_box_durable import write_bytes
        write_bytes(binding_path, binding_bytes)
    binding_sha = sha256_bytes(binding_bytes)
    evidence_dir = out_dir / 'evidence'
    # finding 1: the settled budget bounds EVERY request of the meeting, the server start included
    server = LlamaServer(binary, model, dict(params, cpu_only=True), log=log,
                         deadline=time.monotonic() + float(params['max_meeting_seconds']),
                         evidence_dir=evidence_dir)
    # call ids are stable per intent: the binding (inputs, runtime, parameters) + item + round, never per attempt
    clock_state.update(prefix='meeting:%s' % binding_sha[:16], attempt=server.attempt,
                       model=dict(clock_state['model'], threads=server.threads,
                                  threads_resolution=server.threads_resolution))
    items, not_discussed, reused = [], [], []
    runtime_failure = None
    start_wall = time.time()
    try:
        server.start()
    except (MeetingCallFailed, MeetingBudgetExpired) as error:
        # finding 3: the process is already released by start(); the partial state (inputs, binding) stays; the receipt
        # says what happened with the whole stderr witnessed; no meeting.json (nothing was discussed)
        clock('start:%s' % server.attempt, 'not_called', start_wall, time.time(),
              reason='the coordinator runtime did not start: %s' % str(error)[:600])
        attempt = server.attempt_record('end', 'runtime_failed', error=str(error), seconds=round(time.time() - started, 1))
        receipt = dict(schema=RECEIPT_SCHEMA, day=exchange.get('day'), status='runtime_failed',
                       threads=server.threads_resolution, model_clock=clock_summary(),
                       refused_to_run=['the coordinator runtime did not start: %s' % error],
                       evidence=dict(server_stderr=server.stderr_witness(), retained=server.evidence, attempt=attempt,
                                     attempts=LlamaServer.retained_attempts(evidence_dir)),
                       inputs=witness_file(out_dir / 'meeting-input.json'), binding=witness_file(binding_path),
                       model_calls=0, seconds=round(time.time() - started, 1), route=route, local_route=local_route,
                       workflow_report=meeting_workflow_report(out_dir, given, dict(base, timings=timings, model_clock=clock_summary()),
                                                              status='runtime_failed',
                                                              params=params, context=shared_context, route=route,
                                                              refusals=['the coordinator runtime did not start: %s' % error]))
        write_json(out_dir / 'receipt.json', receipt)
        log('meeting %s: runtime failed to start (%s)' % (exchange.get('day'), error))
        raise
    phase('server_start')
    system_tokens, system_over_cap = None, None
    material_tokens = dict(items={}, rule='server tokenizer counts (/apply-template + /tokenize) of the legacy and stacked '
                                          'system prompt and of every material layer\'s text alone (one message, its chat '
                                          'template included); a count never changes what a prompt carries')
    try:
        system, system_legacy = system_prompts(given, rules_witness['rules'])
        # The cap is counted ONCE on the system prompt with the server's own tokenizer, before any call (the picture
        # is the bulk of it). Over the cap: every item is left open by code with the count; no call; nothing trimmed.
        system_tokens = server.count_tokens([dict(role='system', content=system)], label='system-prompt')
        cap = int(params['input_token_cap_per_call'])
        system_over_cap = system_tokens > cap
        phase('system_prompt_count')
        # the stacks' measurement (Greg, 2026-10-07: token counts before and after, after each layer): the legacy system
        # prompt and every layer of the context section, counted with the server tokenizer; side-effect free requests
        # that never change what the prompt carries; a failed count is recorded, never guessed
        material_tokens['system_prompt'] = dict(stacked=dict(tokens=system_tokens),
                                                encoding=('stacked' if system != system_legacy else 'legacy'))
        if 'material_stacks' in given:
            material_tokens['system_prompt']['legacy'] = _measure(server, [dict(role='system', content=system_legacy)], 'system-legacy')
            material_tokens['context_layers'] = _layer_counts(server, context_text(given, keep_texts=True)[2], 'context')
        phase('material_token_counts')
        log('meeting %s: system prompt %d tokens against the per-call cap %d%s' % (
            exchange.get('day'), system_tokens, cap, ' (OVER: every item left open by code, no call)' if system_over_cap else ''))
        for item in given['items']:
            progress = ItemProgress(out_dir, item['item_id'], binding_sha)
            retained = progress.load()
            if system_over_cap and (retained is None or retained.get('status') != 'complete'):
                now = time.time()
                clock('%s:r%d' % (_safe_name(item['item_id']), int((retained or {}).get('rounds_completed') or 0) + 1),
                      'refused_over_cap', now, now, input_tokens=system_tokens, cap=cap,
                      reason='the system prompt (charter, context and the whole shared market picture) alone is over the '
                             'per-call cap; no call for this item, nothing trimmed')
                not_discussed.append(dict(item_id=item['item_id'], kind='input_cap_system_prompt',
                                          reason='the system prompt (charter, context and the whole shared market picture) is %d '
                                                 'tokens, over the per-call cap of %d; no call was made and nothing was trimmed; '
                                                 'the item keeps its code-seeded open items (the cap is the only accepted reason '
                                                 'Granite does not see the whole picture, and it refuses visibly)' % (system_tokens, cap),
                                          open_items=item['open_items']))
                continue
            if (retained is None or retained.get('status') != 'complete') and 'message_render' in item:
                # the item's first message, every layer, counted before its rounds (recorded, never gating)
                material_tokens['items'][item['item_id']] = _layer_counts(server, item_message(item, keep_texts=True)[2],
                                                                          'item-%s' % _safe_name(item['item_id']))
            if retained is None or retained.get('status') != 'complete':
                remaining = server.remaining()
                next_call = '%s:r%d' % (_safe_name(item['item_id']), int((retained or {}).get('rounds_completed') or 0) + 1)
                if remaining is not None and remaining <= 0:
                    now = time.time()
                    clock(next_call, 'not_called', now, now, reason='the meeting time budget of %s s was spent before '
                          'this item was reached' % params['max_meeting_seconds'])
                    not_discussed.append(dict(item_id=item['item_id'], reason='meeting time budget of %s s spent; the item '
                                              'keeps its code-seeded open items' % params['max_meeting_seconds'],
                                              open_items=item['open_items']))
                    continue
                if not server.alive():
                    now = time.time()
                    clock(next_call, 'not_called', now, now, reason='the coordinator runtime exited before this item '
                          'was reached (its whole stderr is retained)')
                    not_discussed.append(dict(item_id=item['item_id'], reason='the coordinator runtime exited (its whole stderr '
                                              'is retained: %s); the item keeps its code-seeded open items'
                                              % json.dumps(server.stderr_witness(), sort_keys=True),
                                              open_items=item['open_items']))
                    continue
            result = discuss_item(server, item, system, params, log, progress=progress, clock=clock)
            if result.get('reused_from_progress'):
                reused.append(item['item_id'])
            items.append(result)
            try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
                import frankie_box_stage_progress as _SP
                _SP.report_phase('meeting: items discussed', units_done=len(items) + len(not_discussed), units_total=len(given['items']), unit='items', rounds=result.get('rounds_completed'))
            except Exception:  # noqa: BLE001
                pass

    except BaseException as error:
        # 6R2-F: an attempt that dies in discussion leaves a terminal record naming the failure; its stderr, evidence
        # and progress files (pending calls marked) stay as they are for the next attempt to carry forward; neither the
        # process release nor the record write may replace the original error
        try:
            server.stop()
        except Exception as inner:
            log('server release after a discussion failure raised %r' % inner)
        server._record_quietly('end', 'failed_in_discussion', error=repr(error), items_completed_this_attempt=len(items),
                               seconds=round(time.time() - started, 1))
        now = time.time()
        clock('attempt-failed:%s' % server.attempt, 'not_called', now, now,
              reason='the meeting attempt failed in discussion (%s) after %d item(s); no further coordinator call was made '
                     'by this attempt; a call already sent is stamped by its round or, on restart, as unknown_completion'
                     % (repr(error)[:300], len(items)))
        raise
    finally:
        server.stop()
    phase('discussion')
    attempt = server.attempt_record('end', 'complete', seconds=round(time.time() - started, 1),
                                    items_discussed_this_attempt=len(items) - len(reused), items_reused=list(reused))
    attempts = LlamaServer.retained_attempts(evidence_dir)
    record = dict(base, status='complete', items=items, not_discussed=not_discussed, timings=timings,
                  system_prompt_tokens=system_tokens, system_prompt_over_cap=system_over_cap,
                  material=material_record(given, material_basis, material_tokens),
                  runtime=dict(binary=witness_file(binary), model=witness_file(model), parameters=params,
                               provenance=runtime_provenance(config.get('pins') or {}, binary),
                               effective=dict(threads=server.threads, host_cpus=server.host_cpus, host_cpu=host_cpu(),
                                              threads_resolution=server.threads_resolution, placement=server.placement,
                                              call_ceiling_seconds=float(params.get('call_ceiling_seconds') or CALL_CEILING_SECONDS)),
                               budget_seconds=params['max_meeting_seconds'],
                               budget_left_seconds=None if server.remaining() is None else round(server.remaining(), 1),
                               server_stderr=server.stderr_witness(), evidence=server.evidence,
                               attempt=attempt['attempt'],
                               attempts=attempts,
                               unfinished_attempts=[a['attempt'] for a in attempts if not a['finished']],
                               attempts_rule='every attempt of this meeting, finished or not, with its own stderr and evidence '
                                             'witnesses, oldest first; nothing an earlier attempt pinned is renamed, appended to '
                                             'or dropped; an unfinished attempt is carried with what it left'),
                  binding=dict(path=str(binding_path), sha256=binding_sha),
                  progress=dict(directory=str(out_dir / 'progress'), reused_items=reused),
                  # 6R3: counts of the COMPLETE meeting are derived from the retained rounds (every completed chat across all
                  # attempts), apart from this attempt's own counters; zero calls in this attempt never means no model work
                  model_calls=sum(len(i.get('token_counts') or []) for i in items),
                  calls=dict(completed_chat_calls_all_attempts=sum(len(i.get('token_counts') or []) for i in items),
                             this_attempt=server.calls, attempt=server.attempt,
                             pre_send_intents_unresolved=sum(1 for i in items if i.get('pending_call_intent')),
                             interrupted_call_items=sum(1 for i in items for o in i.get('open_items') or []
                                                        if o.get('kind') == 'interrupted_call'),
                             rule='model_calls counts completed coordinator calls of the whole meeting (all attempts, from the '
                                  'retained rounds); this_attempt is this process alone; pre_send_intents_unresolved counts items '
                                  'whose durable pre-send intent never got a recorded reply (any attempt, any closing kind): an '
                                  'intent recorded before sending is not proof the request reached the server'),
                  tokens=dict(server.tokens, scope='this attempt only; per-round prompt_tokens_used across attempts are in items[].token_counts'),
                  seconds=round(time.time() - started, 1),
                  counts=dict(items=len(items), coordinator_turns=sum(len(i['coordinator_turns']) for i in items),
                              code_seat_answers=sum(len(i['code_seat_answers']) for i in items),
                              requested_tests=sum(len(i['requested_tests']) for i in items),
                              open_items=sum(len(i['open_items']) for i in items),
                              refused=sum(len(i['refused']) for i in items), not_discussed=len(not_discussed),
                              reused_items=len(reused)),
                  publication='retained; publication disposition is recorded in the receipt',
                  model_clock=clock_summary(),
                  rule='coordination only; the seats\' records are the evidence; nothing open is dropped (role V2)')
    write_json(out_dir / 'meeting.json', record)
    receipt = publish_meeting_record(exchange_path, out_dir, brain)
    log('meeting %s: %d items, %d coordinator turns, %d requested tests, %d model calls' % (
        exchange.get('day'), len(items), record['counts']['coordinator_turns'], record['counts']['requested_tests'],
        record['model_calls']))
    return receipt


def return_witness(out_dir):
    """What a runner hands back (finding 4): the record's path, bytes and sha256 by name, the receipt's, and the exact
    owner-side import the lane runs with that hash. Written beside the record; it moves nothing and dispatches nothing."""
    from frankie_box_durable import write_json
    out_dir = Path(out_dir)
    record_path, receipt_path = out_dir / 'meeting.json', out_dir / 'receipt.json'
    doc = dict(schema=RETURN_SCHEMA, record=witness_file(record_path) if record_path.is_file() else None,
               receipt=witness_file(receipt_path) if receipt_path.is_file() else None,
               progress=sorted(str(p) for p in (out_dir / 'progress').glob('*.json')) if (out_dir / 'progress').is_dir() else [],
               evidence=sorted(str(p) for p in (out_dir / 'evidence').rglob('*') if p.is_file()) if (out_dir / 'evidence').is_dir() else [],
               owner_import=('python deploy/aws/box/frankie_box_lane_state.py --import-meeting <meeting.json as returned> '
                             '--record-sha256 <record.sha256 above> --exchange /opt/frankie-box/work/experiment/<run>/exchange/'
                             '<day>/exchange-frankie.json  (run by hand on the owning lane; nothing here dispatches it)'),
               rule='the record bytes are the return; the hash is what the owner import verifies; the artifact and the optional '
                    'presigned PUT are transports, not publication')
    write_json(out_dir / 'return.json', doc)
    return doc


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--exchange', required=True, help='exchange-frankie.json of the day (FRANKIE_EXPERIMENT_EXCHANGE_V1, view frankie)')
    p.add_argument('--out-dir', required=True)
    p.add_argument('--config', default=str(CONFIG))
    p.add_argument('--binary', help='llama-server binary (pinned by sha256 in the config); absent on the local route = the '
                                    'canonical install path under /opt/frankie-box/granite, refused visibly by the gate when missing')
    p.add_argument('--model', help='the Granite GGUF file (pinned by sha256 in the config); absent = the canonical path, as --binary')
    p.add_argument('--brain', help='the plan brain: accumulated knowledge is listed by label and hash for the coordinator')
    p.add_argument('--route', choices=list(VOICE_ROUTES), default=DEFAULT_VOICE_ROUTE,
                   help='local (default): a child on the owning box\'s lane under the shared runtime definition; github: the listed '
                        'fallback (dispatched by the Run, never from here)')
    p.add_argument('--inputs-only', action='store_true', help='write what Granite would be given; zero model calls')
    p.add_argument('--threads', type=int, help='the caller\'s lane placement: llama-server threads for this meeting (the day '
                                              'lane\'s shared adviser CPU gives 1); absent = the definition\'s threads rule')
    p.add_argument('--return-witness', action='store_true',
                   help='write return.json beside the record (its bytes and sha256 by name, the owner import to run); no meeting')
    p.add_argument('--local-runtime', action='store_true',
                   help='print the shared local runtime definition (paths, pins, requirements, gate reasons) and exit; nothing runs')
    a = p.parse_args()
    if a.return_witness:
        print(json.dumps(return_witness(a.out_dir), sort_keys=True), flush=True)
        return 0
    if a.local_runtime:
        config, _ = load_config(a.config)
        print(json.dumps(local_runtime(config, binary=a.binary, model=a.model), sort_keys=True, indent=1), flush=True)
        return 0
    if a.route == 'github' and not a.inputs_only:
        p.error('the github route is dispatched by the Run (voice_remote); here it is inputs-only')
    if a.threads is not None and a.threads < 1:
        p.error('--threads must be a positive integer')
    receipt = meeting(a.exchange, a.out_dir, config_path=a.config, binary=a.binary, model=a.model, brain=a.brain,
                      inputs_only=a.inputs_only, route=a.route, threads=a.threads)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
