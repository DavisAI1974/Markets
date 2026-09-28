"""The joined teacher sources (SPEC-joined-teachers.md; Greg, 2026-09-28: the bedrock goes to the teachers, not Frankie).

deploy/aws/box/frankie_box_joined_teacher.py builds them on the box from the Monday calculation layers (read in place,
joined per F_LAST group, per-cell couplings with their null) and writes MANIFEST.json. This module turns a completed
build into the descriptor the host binds into the scientific request, and hands the box the exact bytes. Both teachers
(the classroom scientific teacher and the original BOSS teacher) read every joined source whole, beside the shared
research. Frankie's pre-message and model-visible binding do not carry it: rule 1 of the spec withholds his decision
process from the teachers, and the bedrock read itself stays with the teachers.
"""
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'FRANKIE_JOINED_TEACHER_V1'
DESCRIPTOR_SCHEMA = 'FRANKIE_JOINED_TEACHER_DESCRIPTOR_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'joined-teacher:[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
_FILE = re.compile(r'sources/[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_descriptor(value):
    if type(value) is not dict or value.get('schema') != DESCRIPTOR_SCHEMA:
        raise ValueError('joined teacher descriptor schema differs')
    if set(value) != {'schema', 'directory', 'manifest_sha256', 'sources'}:
        raise ValueError('joined teacher descriptor fields differ')
    if type(value['directory']) is not str or not value['directory'].startswith('/'):
        raise ValueError('joined teacher directory must be absolute')
    if type(value['manifest_sha256']) is not str or not _SHA.fullmatch(value['manifest_sha256']):
        raise ValueError('joined teacher manifest sha256 required')
    sources = value['sources']
    if type(sources) is not list or not sources:
        raise ValueError('joined teacher sources required')
    ids = set()
    for s in sources:
        if (type(s) is not dict or set(s) != {'source_id', 'file', 'sha256', 'bytes'}
                or type(s['source_id']) is not str or not _ID.fullmatch(s['source_id']) or s['source_id'] in ids
                or type(s['file']) is not str or not _FILE.fullmatch(s['file'])
                or type(s['sha256']) is not str or not _SHA.fullmatch(s['sha256'])
                or type(s['bytes']) is not int or s['bytes'] < 0):
            raise ValueError('joined teacher source entry differs')
        ids.add(s['source_id'])
    return json.loads(json.dumps(value))


def descriptor(configured):
    """{directory, manifest_sha256} (the host configuration) -> the checked descriptor: the manifest and every source
    file are re-hashed; a missing or changed file refuses."""
    if type(configured) is not dict or set(configured) != {'directory', 'manifest_sha256'}:
        raise ValueError('joined teacher requires an explicit directory and manifest sha256')
    directory = Path(configured['directory'])
    raw = (directory / 'MANIFEST.json').read_bytes()
    if _sha(raw) != configured['manifest_sha256']:
        raise ValueError('joined teacher manifest differs from its configured sha256')
    manifest = json.loads(raw)
    if manifest.get('schema') != SCHEMA:
        raise ValueError('joined teacher manifest schema differs')
    value = dict(schema=DESCRIPTOR_SCHEMA, directory=str(directory.resolve()), manifest_sha256=configured['manifest_sha256'],
                 sources=[{k: s[k] for k in ('source_id', 'file', 'sha256', 'bytes')} for s in manifest['sources']])
    value = validate_descriptor(value)
    for s in value['sources']:
        data = (directory / s['file']).read_bytes()
        if len(data) != s['bytes'] or _sha(data) != s['sha256']:
            raise ValueError('joined teacher source differs from its manifest: ' + s['source_id'])
    return value


def expected(value):
    """{source_id: {sha256, bytes}} for the reading receipts."""
    if value is None:
        return {}
    value = validate_descriptor(value)
    return {s['source_id']: dict(sha256=s['sha256'], bytes=s['bytes']) for s in value['sources']}


def sources(value):
    """The exact bytes of every joined source, for the box readings: [{source_id, content, sha256, bytes}]."""
    value = validate_descriptor(value)
    out = []
    for s in value['sources']:
        data = (Path(value['directory']) / s['file']).read_bytes()
        if len(data) != s['bytes'] or _sha(data) != s['sha256']:
            raise ValueError('joined teacher source differs from its descriptor: ' + s['source_id'])
        data.decode('utf-8', errors='strict')
        out.append(dict(source_id=s['source_id'], content=data, sha256=s['sha256'], bytes=s['bytes']))
    return out
