"""Explicit opt-in local Python observer. Not used by static scanning.

The parent process owns signing keys; this process never receives them. Only
built-in bounded values are digested, never repr(), pickle or arbitrary hooks.
"""
import ast
import builtins
import datetime
import hashlib
import inspect
import json
import math
import os
try:
    import resource
except ImportError:
    resource = None
import socket
import runpy
import signal
import stat
import struct
import sys
import threading
import time

if sys.version_info < (3, 11):
    raise SystemExit('BuildMap observation requires Python 3.11 or newer; the target was not started.')

config = json.load(sys.stdin)
root = os.path.realpath(config['root'])
manifest = config['sourceHashes']
entry = os.path.join(root, config['entry'])
limit = 10000
calculations, edges, operations, stacks, declarations, resolved_codes, input_files = {}, {}, {}, {}, {}, {}, {}
audit_busy = threading.local()
input_bytes = 0
collector_file = os.path.realpath(__file__)
coverage = {'mode': 'current-python-process-and-observed-python-threads', 'omittedCalculations': 0,
            'omittedEdges': 0, 'omittedOperations': 0, 'omittedValueGroups': 0,
            'unsupportedValues': 0, 'collectorErrors': 0, 'childProcesses': 'not-profiled',
            'externalOpenAttempts': 0, 'descriptorOpenAttempts': 0,
            'ioMeaning': 'audit open attempts, not successful reads or bytes',
            'values': 'digests of bounded exact built-in values; no raw arguments/results'}
start_wall = time.perf_counter_ns()
start_cpu = time.process_time_ns()
threads = set()
finalized = False
exit_code = 0
interrupted = False


def digest_value(value, budget, depth=0):
    if depth > 8 or budget[0] <= 0:
        raise ValueError('value budget')
    budget[0] -= 1
    kind = type(value)
    if kind in (str, bytes):
        if len(value) > 65536:
            raise ValueError('value size')
        data = value.encode('utf8', 'surrogatepass') if kind is str else value
        return [kind.__name__, hashlib.sha256(data).hexdigest()]
    if value is None or kind is bool:
        return [kind.__name__, value]
    if kind is int:
        if value.bit_length() > 4096:
            raise ValueError('integer size')
        return ['int', str(value)]
    if kind is float:
        return ['float64-bits', struct.pack('>d', value).hex()]  # Retains signed zero and NaN payload bits.
    numpy = sys.modules.get('numpy')
    if numpy is not None and kind is getattr(numpy, 'ndarray', None):
        if value.nbytes > 65536 or value.dtype.hasobject or value.dtype.fields is not None or value.dtype.metadata:
            raise ValueError('array size/object/structured semantics require explicit review')
        return ['numpy-array-exact', value.dtype.str, list(value.shape), list(value.strides),
                hashlib.sha256(value.tobytes(order='C')).hexdigest()]
    if kind in (list, tuple):
        if len(value) > 256:
            raise ValueError('collection size')
        return [kind.__name__, [digest_value(v, budget, depth+1) for v in value]]
    if kind is dict:
        if len(value) > 256:
            raise ValueError('mapping size')
        return ['dict', [[digest_value(k, budget, depth+1), digest_value(v, budget, depth+1)] for k, v in value.items()]]
    raise ValueError('custom or unsupported value')


def value_identity(value):
    try:
        return hashlib.sha256(json.dumps(digest_value(value, [1024]), separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    except (ValueError, RecursionError, RuntimeError):
        coverage['unsupportedValues'] += 1
        return None


def resolve(frame):
    if frame.f_code in resolved_codes:
        return resolved_codes[frame.f_code]
    filename = frame.f_code.co_filename
    if not os.path.isabs(filename):
        return None
    full = os.path.realpath(filename)
    if full == collector_file:
        return None
    relative = os.path.relpath(full, root).replace(os.sep, '/')
    if relative not in manifest:
        if len(resolved_codes) < 100000:
            resolved_codes[frame.f_code] = None
        return None
    name = frame.f_code.co_qualname.replace('.<locals>.', '.')
    line = frame.f_code.co_firstlineno
    candidates = declarations.get(relative, [])
    found = [d for d in candidates if d['name'] == name and d['codeLine'] == line]
    actual_line = found[0]['line'] if len(found) == 1 else line
    result = relative, name, actual_line
    if len(resolved_codes) < 100000:
        resolved_codes[frame.f_code] = result
    return result


def profile(frame, event, arg):
    if event not in ('call', 'return'):
        return
    try:
        target = resolve(frame)
        if target is None:
            return
        tid = threading.get_ident()
        threads.add(tid)
        key = json.dumps(target, separators=(',', ':'))
        if key not in calculations:
            if len(calculations) >= limit:
                coverage['omittedCalculations'] += 1
                return
            calculations[key] = {'id': key, 'path': target[0], 'name': target[1], 'line': target[2],
                                 'sourceHash': manifest[target[0]], 'calls': 0, 'returns': 0,
                                 'resumable': bool(frame.f_code.co_flags & (inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR)),
                                 'elapsedNanoseconds': 0, 'inputGroups': {}}
        record = calculations[key]
        stack = stacks.setdefault(tid, [])
        if event == 'call':
            record['calls'] += 1
            code = frame.f_code
            count = code.co_argcount + code.co_kwonlyargcount
            if code.co_flags & inspect.CO_VARARGS:
                count += 1
            if code.co_flags & inspect.CO_VARKEYWORDS:
                count += 1
            values = {name: frame.f_locals[name] for name in code.co_varnames[:count] if name in frame.f_locals}
            identity = value_identity(values)
            if identity is not None and identity not in record['inputGroups']:
                if len(record['inputGroups']) >= 256:
                    coverage['omittedValueGroups'] += 1
                    identity = None
                else:
                    record['inputGroups'][identity] = {'inputDigest': identity, 'calls': 0, 'returnDigests': {}, 'unavailableReturns': 0}
            if identity:
                record['inputGroups'][identity]['calls'] += 1
            if stack:
                edge_key = json.dumps([stack[-1]['key'], key], separators=(',', ':'))
                if edge_key in edges or len(edges) < limit:
                    edge = edges.setdefault(edge_key, {'from': stack[-1]['key'], 'to': key, 'calls': 0})
                    edge['calls'] += 1
                else:
                    coverage['omittedEdges'] += 1
            stack.append({'frame': frame, 'key': key, 'started': time.perf_counter_ns(), 'identity': identity})
        elif stack and stack[-1]['frame'] is frame:
            active = stack.pop()
            record['returns'] += 1
            record['elapsedNanoseconds'] += time.perf_counter_ns() - active['started']
            identity = active['identity']
            if identity:
                group = record['inputGroups'][identity]
                returned = value_identity(arg) if arg is not None else None
                if returned is None:
                    group['unavailableReturns'] += 1
                elif returned in group['returnDigests'] or len(group['returnDigests']) < 256:
                    group['returnDigests'][returned] = group['returnDigests'].get(returned, 0) + 1
                else:
                    group['unavailableReturns'] += 1
                    coverage['omittedValueGroups'] += 1
    except Exception:
        coverage['collectorErrors'] += 1


def audit(event, args):
    global input_bytes
    if event != 'open' or finalized or getattr(audit_busy, 'active', False):
        return
    try:
        filename, mode, flags = args
        if type(filename) not in (str, bytes):
            coverage['descriptorOpenAttempts'] += 1
            return  # Descriptor opens remain outside file-path attribution.
        full = os.path.realpath(os.fsdecode(filename))
        relative = os.path.relpath(full, root).replace(os.sep, '/')
        if relative in ('.', '..') or relative.startswith('../'):
            coverage['externalOpenAttempts'] += 1
            return
        tid = threading.get_ident()
        active = stacks.get(tid, [])
        owner = active[-1]['key'] if active else None
        key = json.dumps([relative, owner, str(mode)], separators=(',', ':'))
        if key not in operations and len(operations) >= limit:
            coverage['omittedOperations'] += 1
            return
        op = operations.setdefault(key, {'path': relative, 'calculationId': owner,
                                        'mode': mode if type(mode) is str else None, 'openAttempts': 0})
        op['openAttempts'] += 1
        if type(mode) is str and 'r' in mode and '+' not in mode and relative not in manifest and relative not in input_files:
            audit_busy.active = True
            try:
                info = os.stat(full, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_size > 1000000 or input_bytes + info.st_size > 4000000:
                    raise ValueError('Input identity limit or non-regular file')
                with builtins.open(full, 'rb') as data:
                    content = data.read(1000001)
                if len(content) > 1000000:
                    raise ValueError('Input grew beyond identity limit')
                input_bytes += len(content)
                input_files[relative] = {'path': relative, 'beforeHash': hashlib.sha256(content).hexdigest(), 'size': len(content)}
            except (OSError, ValueError):
                input_files[relative] = {'path': relative, 'beforeHash': None, 'size': None}
            finally:
                audit_busy.active = False
    except Exception:
        coverage['collectorErrors'] += 1


def finish():
    global finalized
    if finalized:
        return
    sys.setprofile(None)
    threading.setprofile(None)
    finalized = True
    elapsed = time.perf_counter_ns() - start_wall
    cpu = time.process_time_ns() - start_cpu
    changed = []
    for relative, expected in manifest.items():
        try:
            with builtins.open(os.path.join(root, relative), 'rb') as source:
                current = hashlib.sha256(source.read()).hexdigest()
            if current != expected:
                changed.append(relative)
        except OSError:
            changed.append(relative)
    for record in calculations.values():
        record['inputGroups'] = list(record['inputGroups'].values())
        for field in ('calls', 'returns', 'elapsedNanoseconds'):
            record[field] = str(record[field])
        for group in record['inputGroups']:
            group['calls'] = str(group['calls'])
            group['returnDigests'] = {k: str(v) for k, v in group['returnDigests'].items()}
    for relative, info in input_files.items():
        info['afterHash'] = None
        if info['beforeHash'] is not None:
            try:
                with builtins.open(os.path.join(root, relative), 'rb') as data:
                    content = data.read(1000001)
                if len(content) <= 1000000:
                    info['afterHash'] = hashlib.sha256(content).hexdigest()
            except OSError:
                pass
        info['status'] = 'current' if info['beforeHash'] is not None and info['beforeHash'] == info['afterHash'] else 'unavailable' if info['beforeHash'] is None else 'changed-during-run'
    cpu_count = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    active_threads = [t for t in threading.enumerate() if t is not threading.main_thread() and t.is_alive()]
    coverage['activeThreadsAtExit'] = len(active_threads)
    coverage['openFramesAtExit'] = sum(len(stack) for stack in stacks.values())
    complete = not interrupted and not changed and not active_threads and not any(coverage[k] for k in ('omittedCalculations','omittedEdges','omittedOperations','collectorErrors','openFramesAtExit'))
    packages = {}
    for module_name, module in list(sys.modules.items()):
        if '.' not in module_name and type(module) is type(sys):
            version = module.__dict__.get('__version__')
            if type(version) is str and len(version) < 200:
                if len(packages) < 100:
                    packages[module_name] = version
                else:
                    coverage['packageVersionsOmitted'] = coverage.get('packageVersionsOmitted', 0) + 1
    packet = {'version': 1, 'collector': 'python-profile-v1', 'entry': config['entry'], 'sourceHashes': manifest,
              'runId': config['runId'], 'argumentIdentity': value_identity(config['arguments']),
              'exitCode': exit_code, 'interrupted': interrupted, 'sourceChanges': changed,
              'completeWithinScope': complete, 'coverage': coverage,
              'metrics': {'elapsedSeconds': elapsed / 1e9, 'cpuSeconds': cpu / 1e9,
                          'cpuUtilizationPercent': min(100, cpu / max(elapsed, 1) / cpu_count * 100),
                          'cpuCount': cpu_count, 'threadsObserved': len(threads),
                          'peakMemoryBytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024) if resource else None},
              'environment': {'python': sys.version.split()[0], 'platform': sys.platform, 'cpuCount': cpu_count,
                              'hostIdentity': hashlib.sha256(socket.gethostname().encode()).hexdigest(), 'packageVersions': packages,
                              'packageScope': 'top-level loaded modules exposing a string version; not binary/transitive/environment attestation'},
              'calculations': list(calculations.values()), 'relationships': list(edges.values()), 'operations': list(operations.values()),
              'inputs': list(input_files.values()),
              'limitations': ['Observer overhead is included. Inclusive calculation times overlap and must not be summed as whole-run time.',
                             'Only this Python process and observed Python threads are profiled; subprocesses/native internals are not traced.',
                             'Open events are attempts, not successful reads or byte counts.',
                             'Input/output digest matches describe these finite observed built-in values, not general purity or equivalence.',
                             'A signature authenticates the configured collector identity, not correctness or hostile-code isolation.']}
    with os.fdopen(3, 'w', closefd=False) as output:
        json.dump(packet, output, separators=(',', ':'), allow_nan=False)
        output.flush()


def stop(signum, frame):
    global interrupted, exit_code
    interrupted, exit_code = True, 128 + signum
    finish()
    raise SystemExit(exit_code)


for relative in manifest:
    try:
        with builtins.open(os.path.join(root, relative), encoding='utf8') as source:
            tree = ast.parse(source.read())
        records = []
        def catalog(nodes, prefix=''):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = prefix + node.name
                    if not isinstance(node, ast.ClassDef):
                        records.append({'name': qualified, 'line': node.lineno,
                                        'codeLine': min([node.lineno] + [d.lineno for d in node.decorator_list])})
                    catalog(node.body, qualified + '.')
                else:
                    catalog(list(ast.iter_child_nodes(node)), prefix)
        catalog(tree.body)
        declarations[relative] = records
    except (OSError, SyntaxError, UnicodeError, RecursionError):
        declarations[relative] = []

os.chdir(root)
sys.path.insert(0, root)
sys.argv = [entry] + config['arguments']
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
sys.addaudithook(audit)
start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
sys.setprofile(profile)
threading.setprofile(profile)
try:
    runpy.run_path(entry, run_name='__main__')
except SystemExit as error:
    exit_code = error.code if type(error.code) is int else 0 if error.code is None else 1
except BaseException:
    exit_code = 1
    import traceback
    traceback.print_exc()
finally:
    finish()
raise SystemExit(exit_code)
