import importlib.util, threading, types, tempfile
from pathlib import Path
SESSION = Path('deploy/aws/box/frankie_box_boss_session.py').resolve()
spec = importlib.util.spec_from_file_location('sess', SESSION); session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)
A, B = session.classroom_module(), session.classroom_module()
print('classroom_module() returns the same module twice:', A is B)
print('A.ClassroomOutput is B.ClassroomOutput:', A.ClassroomOutput is B.ClassroomOutput, '| issubclass either way:', issubclass(A.ClassroomOutput, B.ClassroomOutput) or issubclass(B.ClassroomOutput, A.ClassroomOutput))
# Simulate Session.classroom -> _classroom_call with a reader answer that is JSON but not the JSON asked for
notes = []; calls = []
s = types.SimpleNamespace(_estimate_kind='byte estimate', serverless=None, note=notes.append, _input_tokens=lambda t: 10)
class Refused(SystemExit): pass
def refuse(why): notes.append('REFUSED ' + why); raise Refused(why)
s.refuse = refuse
def reader(name, text):
    calls.append(name); return dict(text='{"explanation": "' + 'x' * 300 + '"}', incomplete=False, job_id='j')   # long enough to pass note_verdict, wrong shape
s.reader = reader
C = session.classroom_module()                       # as Session.classroom() does: its own load
parse = lambda body: C.parse_component(body, dict(name='c', observations=[dict(cursor=1, state='PRESENT', value=1.0)]), ['d'])
try:
    session.Session._classroom_call(s, 'classroom-00-c', 'prompt', parse, 'reader'); print('returned')
except Refused as e: print('REFUSED as designed after', len(calls), 'attempts')
except Exception as e: print('UNCAUGHT', type(e).__name__ + ':', str(e)[:60], '| attempts made:', calls)
