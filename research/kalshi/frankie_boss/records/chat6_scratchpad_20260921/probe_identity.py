import importlib.util, json, sys, threading, types, tempfile
from pathlib import Path
sys.path.insert(0, 'tests')
from test_frankie_box_classroom import COLUMNS, boss_component_answer, boss_summary_answer, build_visible, C
SESSION = Path('deploy/aws/box/frankie_box_boss_session.py').resolve()
spec = importlib.util.spec_from_file_location('sess', SESSION); session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)
A, B = session.classroom_module(), session.classroom_module()
print('same module object:', A is B, '| same ClassroomOutput class:', A.ClassroomOutput is B.ClassroomOutput)
tmp = Path(tempfile.mkdtemp())
visible = build_visible()
notes, calls = [], []
s = types.SimpleNamespace(work=tmp/'work', out=tmp/'out', cycle='00', day='20211003', pod_id='p', serverless=None,
    request=dict(request_id='run-cycle-00', attachment=dict(dipole_classroom=visible)), _lock=threading.Lock(), _estimate_kind='byte estimate')
s.work.mkdir(); s.out.mkdir(); s.note = notes.append; s._input_tokens = lambda t: 1000
class Refused(SystemExit): pass
def refuse(why): notes.append('REFUSED ' + why); raise Refused(why)
s.refuse = refuse
s._fan_out = lambda label, items, work: [work(i) for i in items]
s._classroom_dir = lambda: session.Session._classroom_dir(s)
s._classroom_call = lambda n, t, p, l: session.Session._classroom_call(s, n, t, p, l)
by = {c['name']: c for c in C.components(visible)}
def reader(name, text):
    calls.append(name)
    cname = name.split('-', 2)[2].removesuffix('-retry')
    if cname == COLUMNS[2] and not name.endswith('-retry'):
        return dict(text='{"explanation": "only one key, the rest missing"}', incomplete=False, job_id='j')   # parses as JSON, fails parse_component
    return dict(text=boss_component_answer(by[cname], [p['right'] for p in C.pairs_of(visible, cname)]), incomplete=False, job_id='j')
s.reader = reader; s.boss = lambda n, t: dict(text=boss_summary_answer(), incomplete=False, job_id='j')
try:
    session.Session.classroom(s); print('classroom completed (retry worked)')
except Refused as e: print('Refused as designed:', str(e)[:80])
except Exception as e: print('UNCAUGHT', type(e).__name__, str(e)[:100], '| retry attempted:', any(c.endswith('-retry') for c in calls))
