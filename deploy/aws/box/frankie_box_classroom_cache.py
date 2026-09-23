"""Request-bound classroom artifacts; interrupted publications retain their source answers."""
import hashlib
import json
import time
from pathlib import Path

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def witness(path):
    raw = Path(path).read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def read(path):
    return json.loads(Path(path).read_bytes())

def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=1, allow_nan=False) + '\n', encoding='utf-8')

def preserve(path, reason):
    path = Path(path)
    destination = path.with_name(path.name + '.superseded-' + str(time.time_ns()))
    receipt = dict(schema='FRANKIE_CLASSROOM_SUPERSEDE_V1', original=str(path),
                   retained=str(destination), reason=reason)
    if path.is_file():
        receipt['original_witness'] = witness(path)
    path.rename(destination)
    receipt_path = destination / 'superseded.json' if destination.is_dir() else destination.with_name(destination.name + '.receipt.json')
    write(receipt_path, receipt)
    return destination

def identity(session, visible, module):
    box = Path(module.__file__).parent
    repo = box.parents[2] / 'research' / 'kalshi' / 'frankie_boss'
    paths = [box / name for name in ('frankie_box_boss_session.py', 'frankie_box_classroom.py',
             'frankie_box_classroom_cache.py', 'frankie_box_docs.py')]
    paths.extend(sorted(repo.glob('dipole_classroom*.py')))
    paths.extend([repo / 'frankie_principal_adapter.py', repo / 'c15_journal.py'])
    engine = getattr(session, 'engine', None) or {}
    lane = getattr(session, 'serverless', None) or {}
    return dict(schema='FRANKIE_CLASSROOM_CACHE_IDENTITY_V1',
        request_hash=digest(session.request), teacher_message_hash=visible['pre_message']['teacher_message_hash'],
        classroom_binding_hash=visible['binding']['classroom_binding_hash'],
        code={str(p.relative_to(box.parents[2])): witness(p) for p in paths},
        engine={k: engine.get(k) for k in ('pod_id', 'served_model_name', 'config_hash')},
        declared_model=getattr(session, 'served_model', None), pod_id=session.pod_id,
        reader={k: lane.get(k) for k in ('endpoint_id', 'config_hash')},
        evidence={n: witness(session.work / n) for n in ('merged-notes.md', 'reading.json', 'derivation-digest-full.md')
                  if (session.work / n).is_file()})

class ClassroomCache:
    def __init__(self, directory, expected, writer=write):
        self.writer = writer
        self.directory = Path(directory)
        self.identity = expected
        manifest = self.directory / 'identity.json'
        if self.directory.exists() and any(self.directory.iterdir()):
            try:
                valid = read(manifest) == expected
            except (OSError, ValueError):
                valid = False
            if not valid:
                preserve(self.directory, 'classroom request, teaching, code or execution identity changed')
        self.directory.mkdir(parents=True, exist_ok=True)
        if not manifest.exists():
            write(manifest, expected)

    def load(self, name, prompt):
        path = self.directory / name
        if not path.exists():
            return None
        try:
            value = read(path)
            binding = value['cache_binding']
            payload = {k: v for k, v in value.items() if k != 'cache_binding'}
            if binding != dict(identity_hash=digest(self.identity), prompt_hash=digest(prompt), payload_hash=digest(payload)):
                raise ValueError('classroom answer binding differs')
            return value
        except (OSError, ValueError, KeyError, TypeError):
            preserve(path, 'classroom answer identity or content changed')
            return None

    def save(self, name, prompt, payload):
        value = dict(payload, cache_binding=dict(identity_hash=digest(self.identity),
                     prompt_hash=digest(prompt), payload_hash=digest(payload)))
        path = self.directory / name
        if path.exists():
            preserve(path, 'classroom answer replaced after validation')
        self.writer(path, value)
        return value

    def complete(self):
        try:
            receipt = read(self.directory / 'receipt.json')
            if receipt.get('identity') != self.identity:
                return None
            for name in ('ledgers.json', 'classroom.md'):
                if receipt['artifacts'][name] != witness(self.directory / name):
                    return None
            return read(self.directory / 'ledgers.json')
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def publish(self, ledgers, markdown, receipt):
        for name, value in (('ledgers.json', ledgers), ('classroom.md', markdown), ('receipt.json', receipt)):
            path = self.directory / name
            if path.exists():
                preserve(path, 'recovering incomplete classroom publication')
            if name == 'classroom.md':
                path.write_text(value, encoding='utf-8')
            elif name == 'receipt.json':
                self.writer(path, dict(value, identity=self.identity,
                    ledgers=witness(self.directory / 'ledgers.json'),
                    artifacts={n: witness(self.directory / n) for n in ('ledgers.json', 'classroom.md')}))
            else:
                self.writer(path, value)
