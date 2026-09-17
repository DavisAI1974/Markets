"""Launch pins for the NEXT retained run (audit findings 2 and 7). No result-bearing action here.

The 2026-09-15 configuration (sunday_20260915_package/FB/sunday-launch-20260915/actual-host-final-configuration.json)
is historical evidence: it pins BOSS 050c5056, receiver 342f5728 and the smoke-era completion ref, and is never edited.
A fresh configuration for the new run must satisfy validate() below; the reviewed BOSS commit is supplied by the
reviewer at validation time (it is the tip carrying these pins, which this file cannot name for itself).
"""
import re

NEXT_RUN = {
    'receiver_commit': '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134',           # ccode/frankie-receiver-feed-20260916: 32 output ledgers + output-bundle gate
    'completion_workflow_ref': None,       # the retired smoke completion ref must not be carried; a new ref is Greg's call
    'granite_context': 131072,             # the only Granite context (CLAUDE.md standing rule)
    'context_encoding': 'stacked_v1',
    'native_threads': 8,                   # declared numeric identity, fixed for the whole run
    'output_ledgers': 32,
    'science_byte_exceptions': {           # audit finding 7: pin these two blobs, never claim byte-identity with 050c5056
        'research/kalshi/frankie_boss/c15_journal.py': 'a2dd5e9be76c47a9738b28caa5f364ddaf8d4064',
        'research/kalshi/frankie_boss/prepared_context_cache.py': '8062f60200305567b1a0ef3394b7b5e58c6a5d22',
    },
}
RETIRED_COMPLETION_REF = 'codex/full-frankie-boss-connection-20260915'
ADMISSION_LITERALS = {'output_bundle': 'NOT_PRESENTED', 'sealed_proof': 'UNPROVEN'}


def validate(configuration, *, boss_commit):
    """Every pin the next run must carry; returns nothing, raises with EVERY violation named."""
    if not re.fullmatch('[0-9a-f]{40}', str(boss_commit)):
        raise ValueError('reviewed BOSS commit (40 hex) required')
    host = configuration.get('host_runtime') or {}
    problems = []
    def expect(name, actual, expected):
        if actual != expected:
            problems.append(f'{name}: {actual!r} != pinned {expected!r}')
    expect('host_runtime.boss_commit', host.get('boss_commit'), boss_commit)
    expect('receiver_commit', configuration.get('receiver_commit'), NEXT_RUN['receiver_commit'])
    expect('host_runtime.context_encoding', host.get('context_encoding'), NEXT_RUN['context_encoding'])
    expect('host_runtime.native_threads', host.get('native_threads'), NEXT_RUN['native_threads'])
    expect('host_runtime.science_byte_exceptions', host.get('science_byte_exceptions'), NEXT_RUN['science_byte_exceptions'])
    if host.get('completion_workflow_ref') == RETIRED_COMPLETION_REF:
        problems.append('host_runtime.completion_workflow_ref: the retired 2026-09-15 completion ref is carried')
    if 'granite_context' in host:
        expect('host_runtime.granite_context', host.get('granite_context'), NEXT_RUN['granite_context'])
    admission = configuration.get('principal_admission')
    if type(admission) is not dict or set(admission) != {'output_bundle', 'sealed_proof'}:
        problems.append('principal_admission: output_bundle and sealed_proof must be declared (audit finding 4)')
    else:
        for key, literal in ADMISSION_LITERALS.items():
            if admission[key] == literal:
                problems.append(f'principal_admission.{key}: the historical {literal} policy is not a pin for a new run')
    if any('E:' in str(value) or '\\\\' in str(value) for value in (host.get('repository'), configuration.get('receiver_root'))):
        problems.append('paths: a desktop path is carried (D34: nothing local)')
    if problems:
        raise ValueError('launch pins refused: ' + '; '.join(problems))


def historical_configuration_is_refused(path, *, boss_commit):
    """The retained 2026-09-15 configuration must never validate as the next run."""
    import json
    try:
        validate(json.loads(open(path, 'rb').read()), boss_commit=boss_commit)
    except ValueError as error:
        return str(error)
    raise AssertionError('historical configuration validated as the next run')
