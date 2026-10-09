"""The teacher reads what Frankie ingests, once, while Frankie's context is built (Greg, 2026-09-28: "can't we just have
the teacher just read what Frankie is ingesting instead of building that data 2x?").

The pinned _prepare (context_session.py, unchanged) walks the journal for the native context, encodes it, and only then
calls the teacher, which walked the whole journal a second time. Now:
  1. the first walk decodes each block ONCE and saves both parts of it (parallel_journal saved blocks): the context rows
     Frankie's native context takes, and the full payloads the teacher takes;
  2. start() launches this teacher process at the moment that walk begins. It reads the saved teacher parts in order as
     they land (FRANKIE_WALK_FOLLOW: a block the first walk passed without saving, e.g. with the disk short, is decoded
     here instead, never skipped) and runs the teacher's row pass (parallel_teacher.row_pass: the raw streams, the long
     single-thread part) on its own CPU, concurrently with the walk and the context encode;
  3. when the pinned _prepare calls the teacher (parallel_teacher.parallel_attach), the context rows are handed over
     (cursor, 7-field hash) and this process finishes: the exact-row check against the rows it read, the normalizer,
     targets and receipts (parallel_teacher.finish). The journal is not walked a second time.
Any failure here is raised in the launch with its traceback; nothing is silently replaced.
"""
import multiprocessing
import os
import pickle
import time
import traceback
from pathlib import Path

_CURRENT = [None]


def _wake():
    """frankie_box_wake (event-driven waits, Greg 2026-10-09: no coded wait times): inotify on the hand-off directory,
    a pidfd on the teacher process; no poll interval."""
    try:
        import frankie_box_wake as W
    except ImportError:
        from deploy.aws.box import frankie_box_wake as W
    return W


def _atomic(path, data):
    temporary = path.with_name(path.name + '.tmp-%d' % os.getpid())
    temporary.write_bytes(data)
    os.replace(temporary, path)


class Handle:
    def __init__(self, process, directory, as_of, source_manifest_hash):
        self.process, self.directory = process, Path(directory)
        self.as_of, self.source_manifest_hash = as_of, source_manifest_hash

    def result(self, spec):
        """Hand the context over and wait for the finished attachment."""
        _atomic(self.directory / 'context.pkl', pickle.dumps(spec, protocol=pickle.HIGHEST_PROTOCOL))
        result, error = self.directory / 'result.pkl', self.directory / 'error.txt'
        # armed before the first check: the result/error landing (atomic rename) or the process exiting wakes it
        with _wake().Waiter([self.directory], pids=[self.process.pid]) as waiter:
            while True:
                if error.exists():
                    raise RuntimeError('concurrent teacher failed:\n' + error.read_text())
                if result.exists():
                    return pickle.loads(result.read_bytes())
                if not self.process.is_alive():
                    raise RuntimeError('concurrent teacher exited (code %s) without a result' % self.process.exitcode)
                waiter.fired.clear()
                waiter.wait()

    def stop(self):
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(30)
            if self.process.is_alive():
                self.process.kill()


def current(*, as_of, source_manifest_hash):
    handle = _CURRENT[0]
    if handle is not None and handle.as_of == as_of and handle.source_manifest_hash == source_manifest_hash:
        return handle
    return None


def start(context, as_of, through_cursor):
    """Launch the teacher beside the first walk of one preparation; None when this preparation has no R3 teacher over a
    compact journal (the teacher then runs in the preparation itself, as before)."""
    from .frankie_journal_reader import FrankieCompactReader
    from . import c15_teacher_r3 as T
    from .parallel_journal import _cache_dir
    teacher, journal = getattr(context, 'teacher', None), context.builder.journal
    if not isinstance(teacher, T.JournalTeacherR3) or not isinstance(journal, FrankieCompactReader):
        return None
    try:
        blob = pickle.dumps(teacher, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as error:          # noqa: BLE001  -- the teacher then runs in the preparation itself, as before
        print('concurrent teacher not started (%s: %s); the teacher runs in the preparation' % (type(error).__name__, error),
              flush=True)
        return None
    directory = _cache_dir(journal.path) / ('teacher-%d-%d' % (os.getpid(), time.time_ns()))
    directory.mkdir(parents=True, exist_ok=True)
    spec = dict(teacher=blob, path=str(journal.path),
                count=journal.count, head=journal.head_hash, workers=max(1, len(journal.worker_cpus) // 4),
                next_cursor=context.builder.chain.next_cursor, through_cursor=through_cursor, as_of=as_of,
                source=context.builder.scope.scope_id, entity=tuple(context.entity),
                changes=os.environ.get('FRANKIE_TEACHER_CHANGES', '1') != '0', directory=str(directory))
    process = multiprocessing.get_context('spawn').Process(target=_run, args=(pickle.dumps(spec),), name='concurrent-teacher')
    process.start()
    print('concurrent teacher started (pid %d, %s): reads the first walk\'s saved blocks as they land' % (
        process.pid, directory), flush=True)
    _CURRENT[0] = Handle(process, directory, as_of, spec['source'])
    return _CURRENT[0]


def stop():
    handle, _CURRENT[0] = _CURRENT[0], None
    if handle is not None:
        handle.stop()


def _run(spec_blob):
    spec = pickle.loads(spec_blob)
    directory = Path(spec['directory'])
    try:
        os.environ['FRANKIE_WALK_FOLLOW'] = '1'          # the walk workers wait for the first walk's saved blocks
        from types import SimpleNamespace
        from . import parallel_journal as PJ
        from . import context_session as CS
        from . import c15_teacher_r3 as T
        from . import parallel_teacher as PT
        from .frankie_journal_reader import FrankieCompactReader
        teacher = pickle.loads(spec['teacher'])
        reader = FrankieCompactReader(spec['path'], expected_count=spec['count'], expected_head_hash=spec['head'],
                                      workers=spec['workers'])
        builder = SimpleNamespace(journal=reader, _failed=False, chain=SimpleNamespace(next_cursor=spec['next_cursor']))
        PJ._SERIAL = CS.journal_prefix
        PJ._ENTITY[0] = spec['entity']
        T.evidence_hash = PJ._chain_hash_factory(T.evidence_hash)
        if spec['changes']:
            from . import teacher_changes
            teacher_changes.apply()
        started = time.time()
        evidence = PJ.parallel_journal_prefix(builder, spec['through_cursor'], None)
        rows, processed, hashes = PT.row_pass(teacher, evidence, as_of=spec['as_of'], source_manifest_hash=spec['source'])
        (directory / 'rows-done.txt').write_text('%d rows in %.1f s\n' % (processed, time.time() - started))
        print('concurrent teacher: row pass done, %d rows in %.1f s; waiting for the context' % (
            processed, time.time() - started), flush=True)
        path = directory / 'context.pkl'
        with _wake().Waiter([directory]) as waiter:      # the hand-over's atomic rename wakes it; no poll
            while not path.exists():
                waiter.fired.clear()
                waiter.wait()
        context = pickle.loads(path.read_bytes())
        result = PT.finish(teacher, rows, processed, hashes, context, source_manifest_hash=spec['source'])
        _atomic(directory / 'result.pkl', pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))
    except BaseException:
        _atomic(directory / 'error.txt', traceback.format_exc().encode())
        raise
