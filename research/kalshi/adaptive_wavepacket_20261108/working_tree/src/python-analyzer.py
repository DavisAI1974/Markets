"""BuildMap's trusted, isolated syntax reader. Never imports the mapped project."""
import ast
from collections import Counter
import json
import math
import re
import sys


def location(node):
    return {"line": node.lineno, "column": node.col_offset + 1}


def expr(node):
    if node is None:
        return "no explicit value"
    value = ast.unparse(node)
    return value if len(value) <= 240 else value[:237] + "..."


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = name(node.value)
        return base + "." + node.attr if base else ""
    return ""


def literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def path_operand(node):
    if isinstance(node, ast.Name):
        return {"kind": "name", "name": node.id}
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))) and not (isinstance(node.value, float) and not math.isfinite(node.value)):
        return {"kind": "literal", "value": node.value}
    if isinstance(node, ast.Call):
        return {"kind": "call", "target": name(node.func), "arguments": [path_operand(a) for a in node.args]}
    return {"kind": "unknown", "text": expr(node)}


def sql_references(query):
    # Literal source only. Remove comments/values before recognizing a small
    # identifier grammar; never resolve dynamic SQL, aliases, CTEs or a database.
    cleaned = re.sub(r"'(?:''|[^'])*'|--[^\n]*|/\*[\s\S]*?\*/", ' ', query)
    identifier = r'(?:[A-Za-z_][A-Za-z0-9_$]*|"(?:""|[^"])+")(?:\.(?:[A-Za-z_][A-Za-z0-9_$]*|"(?:""|[^"])+"))*'
    return [{"operation": 'write' if match.group(1).upper().startswith(('INSERT', 'UPDATE', 'CREATE')) else 'read',
             "tableExpression": match.group(2), "basis": 'SQL literal syntax; connection/schema identity unresolved'}
            for match in re.finditer(r'\b(FROM|JOIN|INSERT\s+INTO|UPDATE|CREATE\s+TABLE)\s+(' + identifier + ')', cleaned, re.I)]


def range_count(node):
    # Written literal range bounds only. Never evaluate an expression or a target call.
    if not isinstance(node, ast.Call) or name(node.func) != "range" or node.keywords:
        return None
    def integer(n):
        if isinstance(n, ast.Constant) and type(n.value) is int:
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant) and type(n.operand.value) is int:
            return -n.operand.value
        return None
    values = [integer(n) for n in node.args]
    if not 1 <= len(values) <= 3 or any(v is None for v in values):
        return None
    start, stop, step = (0, values[0], 1) if len(values) == 1 else (values[0], values[1], values[2] if len(values) == 3 else 1)
    if step == 0:
        return None
    count = max(0, (stop - start + step - (1 if step > 0 else -1)) // step)
    return str(count)


def analyze(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as error:
        return {"status": "parse-error", "reason": "Python source could not be parsed: " + type(error).__name__, "functions": []}
    definitions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append((node.name, node, 'function'))
        elif isinstance(node, ast.ClassDef):
            definitions.extend((node.name + '.' + method.name, method, 'method') for method in node.body
                               if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)))
    # Catalog nested function bodies separately. Their calls are never folded
    # into the enclosing calculation or treated as observed execution.
    def nested(body, prefix):
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = prefix + '.' + statement.name
                definitions.append((qualified, statement, 'nested-function'))
                nested(statement.body, qualified)
            elif not isinstance(statement, ast.ClassDef):
                nested(list(ast.iter_child_nodes(statement)), prefix)
    for qualified, node, _ in list(definitions):
        nested(node.body, qualified)
    bindings = Counter()
    mutated_roots = set()
    star_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings[node.id] += 1
        elif isinstance(node, ast.arg):
            bindings[node.arg] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                star_import |= alias.name == '*'
                bindings[alias.asname or (alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name)] += 1
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bindings[node.name] += 1
        elif type(node).__name__ in ('MatchAs', 'MatchStar') and node.name:
            bindings[node.name] += 1
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            root = name(node).split('.')[0]
            if root:
                mutated_roots.add(root)
    linkable = {qualified for qualified, node, kind in definitions
                if kind == 'function' and bindings[qualified] == 1 and not node.decorator_list and not star_import}
    import_bindings = {}
    imports = {}
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                local = a.asname or a.name.split('.')[0]
                imports[local] = a.name
                import_bindings[local] = {"module": a.name, "level": 0, "symbol": None,
                                          "prefix": [] if a.asname else a.name.split('.')[1:], **location(n)}
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                local = a.asname or a.name
                if not n.level:
                    imports[local] = n.module + "." + a.name
                import_bindings[local] = {"module": n.module, "level": n.level, "symbol": a.name, "prefix": [], **location(n)}
    import_bindings = {k: v for k, v in import_bindings.items()
                       if bindings[k] == 1 and k not in mutated_roots and not star_import and k != '*'}
    # Conservatively suppress library recognition for any binding/reassignment,
    # including one in another scope. This avoids claiming a shadowed call is I/O.
    bound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
    bound.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
    bound.update(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    imports = {k: v for k, v in imports.items() if k not in bound and bindings[k] == 1 and k not in mutated_roots and not star_import}

    def canonical(target):
        root, *rest = target.split('.')
        return '.'.join([imports.get(root, root), *rest])

    class Reader(ast.NodeVisitor):
        def __init__(self):
            self.calls, self.returns, self.io, self.loop_paths, self.cues, self.stack, self.transformations = [], [], [], [], [], [], []
            self.conditions = self.loops = self.throws = 0
            self.yields = 0
            self.comprehensions = []
            self.facts = []
            self.guards = []
            self.collections = {}
            self.steps = []
            self.constants = {}
            self.result_targets = {}
            self.field_accesses, self.sql = [], []

        def explain(self, node):
            if node is None:
                return 'No explicit value is supplied.'
            if isinstance(node, ast.Name):
                return 'Uses the value named ' + node.id + '.'
            if isinstance(node, ast.BinOp):
                operators = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.FloorDiv: '//', ast.Mod: '%', ast.Pow: '**', ast.MatMult: '@'}
                return 'Combines ' + expr(node.left) + ' and ' + expr(node.right) + ' with the ' + operators.get(type(node.op), type(node.op).__name__) + ' operator. Actual types and values are not inferred.'
            if isinstance(node, ast.Call):
                target = name(node.func)
                resolved = canonical(target)
                if resolved in ('pandas.read_csv', 'pandas.read_parquet', 'pandas.read_pickle'):
                    return 'Reads a table from ' + (expr(node.args[0]) if node.args else 'the supplied path') + ' using ' + target + ', if this call is reached.'
                if target in ('sum', 'len', 'min', 'max', 'sorted') and target not in bound and target not in imports:
                    descriptions = {'sum': 'Sums the supplied values', 'len': 'Counts the supplied items', 'min': 'Selects the smallest supplied value', 'max': 'Selects the largest supplied value', 'sorted': 'Builds a sorted result'}
                    return descriptions[target] + ': ' + (expr(node.args[0]) if node.args else 'no positional input') + '.'
                return 'Calls ' + (target or 'a computed callable') + ' with ' + ', '.join(expr(a) for a in node.args) + '. Read its linked source or runtime observation to follow the result.'
            if isinstance(node, ast.Subscript):
                return 'Selects ' + expr(node.slice) + ' from ' + expr(node.value) + '. Whether this is a row, column, key or position depends on the runtime value.'
            if isinstance(node, ast.Dict):
                return 'Builds a mapping with written keys: ' + ', '.join(expr(k) for k in node.keys if k is not None) + '.'
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                return 'Builds ' + ('a deferred generator' if isinstance(node, ast.GeneratorExp) else 'a collection') + ' over ' + ' then '.join(expr(g.iter) for g in node.generators) + '; filters and callers determine what is evaluated.'
            return 'Uses the written expression ' + expr(node) + '; actual behavior and values require observation.'

        def fact(self, node, kind, **details):
            self.facts.append({"kind": kind, "expression": expr(node), "loopDepth": len(self.stack),
                               "loops": list(self.stack), "guards": list(self.guards), **details, **location(node)})

        def path_value(self, node):
            if literal(node) is not None:
                return literal(node)
            if isinstance(node, ast.Name):
                return self.constants.get(node.id)
            if isinstance(node, ast.Call) and canonical(name(node.func)) == 'pathlib.Path' and node.args:
                return self.path_value(node.args[0])
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                left, right = self.path_value(node.left), self.path_value(node.right)
                if left is not None and right is not None:
                    return left.rstrip('/') + '/' + right
            return None

        def visit_FunctionDef(self, node):
            pass  # Nested bodies/defaults/decorators belong to a different scope.
        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef
        def visit_ListComp(self, node):
            axes = []
            for generator in node.generators:
                axes.append({"target": expr(generator.target), "iterable": expr(generator.iter),
                             "filters": [expr(test) for test in generator.ifs], "async": bool(generator.is_async),
                             "literalRangeCount": range_count(generator.iter) if 'range' not in bound and 'range' not in imports else None,
                             **location(generator.target)})
            self.comprehensions.append({"kind": type(node).__name__, "evaluation": 'deferred-expression' if isinstance(node, ast.GeneratorExp) else 'eager-container',
                                        "axes": axes, **location(node)})
            # A generator's first iterable is evaluated at construction. Its
            # body/filters/inner iterables may never be consumed: do not turn
            # their call sites into observed or repeated file-read findings.
            if isinstance(node, ast.GeneratorExp):
                self.visit(node.generators[0].iter)
            else:
                for generator in node.generators:
                    self.visit(generator.iter)
                    self.stack.append({"target": expr(generator.target), "iterable": expr(generator.iter), **location(generator.target)})
                    for condition in generator.ifs:
                        self.visit(condition)
                if isinstance(node, ast.DictComp):
                    self.visit(node.key)
                    self.visit(node.value)
                else:
                    self.visit(node.elt)
                del self.stack[-len(node.generators):]
        visit_SetComp = visit_ListComp
        visit_DictComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_For(self, node):
            self.loops += 1
            axis = {"target": expr(node.target), "iterable": expr(node.iter), "literalRangeCount": range_count(node.iter) if 'range' not in bound and 'range' not in imports else None, **location(node)}
            self.visit(node.iter)  # Iterator expression runs before this loop.
            self.stack.append(axis)
            self.steps.append({"kind": "loop", "expression": expr(node.iter), "explanation": 'For each ' + expr(node.target) + ' from ' + expr(node.iter) + ', follows the loop body if reached.', "guards": list(self.guards), **location(node)})
            if len(self.stack) >= 2:
                self.loop_paths.append(list(self.stack))
            for statement in node.body:
                self.visit(statement)
            self.stack.pop()
            for statement in node.orelse:
                self.visit(statement)
        visit_AsyncFor = visit_For

        def visit_While(self, node):
            self.loops += 1
            self.stack.append({"target": "while condition", "iterable": expr(node.test), "literalRangeCount": None, **location(node)})
            if len(self.stack) >= 2:
                self.loop_paths.append(list(self.stack))
            self.visit(node.test)
            for statement in node.body:
                self.visit(statement)
            self.stack.pop()
            for statement in node.orelse:
                self.visit(statement)

        def visit_If(self, node):
            self.conditions += 1
            self.visit(node.test)
            guard = {"test": expr(node.test), **location(node)}
            self.guards.append({**guard, "branch": 'then'})
            for statement in node.body:
                self.visit(statement)
            self.guards.pop()
            self.guards.append({**guard, "branch": 'else'})
            for statement in node.orelse:
                self.visit(statement)
            self.guards.pop()

        def visit_IfExp(self, node):
            self.conditions += 1
            self.generic_visit(node)

        def visit_Compare(self, node):
            if any(part in expr(node).lower() for part in ('identity', 'sha256', 'source_hash', 'schema', 'fingerprint', 'version')):
                self.fact(node, 'identity-comparison', basis='comparison syntax; compatibility policy unverified')
            self.generic_visit(node)

        def visit_Raise(self, node):
            self.throws += 1
            self.generic_visit(node)

        def visit_Return(self, node):
            self.returns.append({"summary": expr(node.value), "kind": type(node.value).__name__, **location(node)})
            self.steps.append({"kind": "return", "expression": expr(node.value), "explanation": self.explain(node.value), "guards": list(self.guards), **location(node)})
            self.generic_visit(node)

        def visit_Yield(self, node):
            self.yields += 1
            self.generic_visit(node)
        visit_YieldFrom = visit_Yield

        def visit_Assign(self, node):
            self.transformations.append({"summary": expr(node), "kind": type(node).__name__, **location(node)})
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            self.steps.append({"kind": "assign", "targets": [expr(t) for t in targets], "expression": expr(value), "explanation": self.explain(value),
                               "references": sorted({n.id for n in ast.walk(value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}) if value else [],
                               "guards": list(self.guards), **location(node)})
            if isinstance(value, ast.Call):
                self.result_targets[id(value)] = [expr(t) for t in targets]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                container = type(value).__name__ if isinstance(value, (ast.List, ast.Dict, ast.Set)) else None
                bounded = False
                if isinstance(value, ast.Call) and canonical(name(value.func)) == 'collections.deque':
                    container = 'deque'
                    bounded = any(k.arg == 'maxlen' and isinstance(k.value, ast.Constant) and type(k.value.value) is int and k.value.value > 0 for k in value.keywords)
                if container:
                    self.collections[target.id] = {"container": container, "bounded": bounded, "initializationLoopDepth": len(self.stack)}
                    self.fact(node, 'collection-initialization', receiver=target.id, **self.collections[target.id])
                elif target.id in self.collections:
                    del self.collections[target.id]
            self.generic_visit(node)
        visit_AnnAssign = visit_Assign
        visit_AugAssign = visit_Assign

        def visit_Subscript(self, node):
            self.field_accesses.append({"container": expr(node.value), "selector": expr(node.slice), "access": 'write' if isinstance(node.ctx, ast.Store) else 'read', **location(node)})
            self.generic_visit(node)

        def visit_Call(self, node):
            target = name(node.func) or "computed callable"
            resolved = canonical(target)
            call = {"target": target, "kind": "call", "argumentCount": len(node.args) + len(node.keywords),
                               "arguments": [expr(a) for a in node.args] + [(k.arg or '**') + '=' + expr(k.value) for k in node.keywords],
                               "resolution": "unresolved-source-reference", **location(node)}
            call.update({"positionalArguments": [expr(a) for a in node.args],
                         "keywordArguments": [{"name": k.arg, "expression": expr(k.value)} for k in node.keywords],
                         "resultTargets": self.result_targets.get(id(node), []), "guards": list(self.guards), "loopDepth": len(self.stack)})
            parts = target.split('.')
            if len(parts) == 1 and target in linkable:
                call['bindingReference'] = {"kind": 'local-function', "targetName": target}
            elif parts[0] in import_bindings:
                binding = import_bindings[parts[0]]
                member = parts[1:]
                if binding['symbol'] is not None and not member:
                    call['bindingReference'] = {"kind": 'imported-function', "targetName": binding['symbol'], **binding}
                elif binding['symbol'] is None and member[:len(binding['prefix'])] == binding['prefix'] and len(member) == len(binding['prefix']) + 1:
                    call['bindingReference'] = {"kind": 'imported-function', "targetName": member[-1], **binding}
            self.calls.append(call)
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('execute', 'executemany', 'sql', 'read_sql', 'read_sql_query') and node.args and literal(node.args[0]) is not None:
                query = literal(node.args[0])
                if re.match(r'^\s*(SELECT|INSERT|UPDATE|CREATE\s+TABLE|WITH)\b', query, re.I):
                    self.sql.append({"call": target, "queryExpression": expr(node.args[0]), "tables": sql_references(query),
                                     "basis": 'literal query passed to a SQL-like method; execution and connection identity unverified', **location(node)})
            keywords = {k.arg: k.value for k in node.keywords if k.arg is not None}
            member = node.func.attr if isinstance(node.func, ast.Attribute) else None
            receiver_node = node.func.value if isinstance(node.func, ast.Attribute) else None
            receiver = name(receiver_node)
            # Facts retain syntax and guards. An unknown receiver is never
            # treated as a verified file, checkpoint, executor or live worker.
            if member in ('read_bytes', 'read_text', 'write_bytes', 'write_text'):
                operation = 'load' if member.startswith('read') else 'save'
                self.fact(node, 'persistence', operation=operation, pathExpression=expr(receiver_node),
                          literalPath=self.path_value(receiver_node), basis='member-call syntax; receiver type unverified')
                if operation == 'load':
                    self.fact(node, 'whole-materialization', basis='whole-value read method syntax; size unknown')
            if member in ('exists', 'is_file'):
                self.fact(node, 'existence-check', pathExpression=expr(receiver_node), literalPath=self.path_value(receiver_node),
                          basis='member-call syntax; existence alone does not prove identity or completeness')
            persistence_calls = {'pickle.load': 'load', 'pickle.dump': 'save', 'json.load': 'load', 'json.dump': 'save',
                                 'torch.load': 'load', 'torch.save': 'save', 'numpy.load': 'load', 'numpy.save': 'save'}
            if resolved in persistence_calls and parts[0] in imports:
                operation = persistence_calls[resolved]
                index = 1 if operation == 'save' and resolved != 'numpy.save' else 0
                operand = node.args[index] if len(node.args) > index else keywords.get('file')
                self.fact(node, 'persistence', operation=operation, pathExpression=expr(operand), literalPath=self.path_value(operand),
                          basis='recognized imported persistence call; handle/path identity unverified')
            if any(word in target.lower() for word in ('checkpoint', 'save_state', 'load_state', 'restore_state', 'receipt')):
                self.fact(node, 'checkpoint-helper', operation='load' if any(w in target.lower() for w in ('load', 'restore', 'read')) else 'save' if any(w in target.lower() for w in ('save', 'write')) else 'unknown',
                          pathExpression=expr(node.args[0]) if node.args else 'unknown', literalPath=None,
                          basis='helper name only; inspect its implementation and checkpoint policy')
            if member in ('append', 'extend', 'update', 'add') and receiver in self.collections:
                self.fact(node, 'collection-growth', receiver=receiver, **self.collections[receiver])
            if member in ('pop', 'clear', 'popleft') and receiver:
                self.fact(node, 'collection-release', receiver=receiver, basis='release-call syntax; execution/retention unknown')
            if (target in ('list', 'tuple', 'set', 'dict', 'sorted') and target not in bound and target not in imports and node.args) or (member in ('read', 'readlines', 'fetchall') and not node.args and not node.keywords):
                self.fact(node, 'whole-materialization', basis='whole-result construction/read syntax; size and type unknown')
            if resolved in ('pandas.read_csv', 'pandas.read_parquet') and parts[0] in imports:
                chunked = 'chunksize' in keywords and not (isinstance(keywords['chunksize'], ast.Constant) and keywords['chunksize'].value is None)
                self.fact(node, 'bounded-read-cue' if chunked else 'whole-materialization', basis='chunk parameter supplied; bounds unverified' if chunked else 'table-reader syntax; result size unknown')
            if resolved in ('concurrent.futures.ThreadPoolExecutor', 'concurrent.futures.ProcessPoolExecutor', 'multiprocessing.Pool') and parts[0] in imports:
                workers = keywords.get('max_workers', keywords.get('processes', node.args[0] if node.args else None))
                self.fact(node, 'worker-pool', workersExpression=expr(workers), basis='recognized pool constructor; runtime worker topology unknown')
            if member in ('submit', 'result', 'join', 'wait', 'map', 'imap', 'imap_unordered') or resolved in ('subprocess.run', 'concurrent.futures.wait', 'os.sched_setaffinity'):
                self.fact(node, 'execution-control', target=target, member=member or resolved.rsplit('.', 1)[-1], receiver=receiver,
                          basis='control-call syntax; blocking, independence and actual scheduling unverified')
            if any(word in resolved.lower() for word in ('cache', 'lazy', 'subset', 'scheduler', 'checkpoint', 'receipt', 'indexed', 'fft', 'reuse')):
                self.cues.append({"expression": expr(node), "basis": "name-only; behavior unverified", **location(node)})
            product = operation = None
            root = target.split('.')[0]
            if resolved in ('pandas.read_csv', 'pandas.read_parquet', 'pandas.read_pickle', 'numpy.load') and root in imports:
                product = self.path_value(node.args[0]) if node.args else next((self.path_value(k.value) for k in node.keywords if k.arg in ('filepath_or_buffer', 'path', 'file')), None)
                operation = 'read'
            elif target == 'open' and 'open' not in bound and 'open' not in imports:
                product = self.path_value(node.args[0]) if node.args else next((self.path_value(k.value) for k in node.keywords if k.arg == 'file'), None)
                mode_node = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == 'mode'), ast.Constant(value='r'))
                mode = literal(mode_node)
                if mode is not None:
                    operation = 'read-write' if '+' in mode else 'write' if any(c in mode for c in 'wax') else 'read'
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ('to_csv', 'to_parquet', 'to_pickle'):
                product = literal(node.args[0]) if node.args else next((literal(k.value) for k in node.keywords if k.arg in ('path', 'path_or_buf')), None)
                operation = 'write'
            elif resolved == 'numpy.save' and root in imports:
                product = literal(node.args[0]) if node.args else None
                operation = 'write'
            if operation:
                path_node = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in ('filepath_or_buffer', 'path', 'path_or_buf', 'file')), None)
                self.io.append({"pathExpression": product if product is not None else expr(path_node), "pathKind": 'literal' if product is not None else 'symbolic', "operand": path_operand(path_node), "operation": operation, "call": target,
                                "basis": "literal-or-unique-constant-path-syntax", "loopDepth": len(self.stack),
                                "guards": list(self.guards), "resultTargets": self.result_targets.get(id(node), []), **location(node)})
                if product is not None:
                    self.fact(node, 'persistence', operation='load' if operation == 'read' else 'save' if operation == 'write' else 'load-save',
                              pathExpression=product, literalPath=product, basis='literal file-I/O call syntax; saved-product semantics unknown')
            self.generic_visit(node)

    records = []
    scopes = [(qualified, n.body, n, kind) for qualified, n, kind in definitions]
    module_body = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if module_body:
        scopes.insert(0, ('<module>', module_body, None, 'module'))
    for function_name, body, fn, scope_kind in scopes:
        reader = Reader()
        # Resolve only single-assignment literal/path constants. No evaluation,
        # branch execution, parameter substitution or mutable alias inference.
        local_stores = Counter(n.id for statement in body for n in ast.walk(statement)
                               if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)))
        for statement in body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                value = reader.path_value(statement.value)
                for target in targets:
                    if isinstance(target, ast.Name) and local_stores[target.id] == 1 and value is not None:
                        reader.constants[target.id] = value
        for statement in body:
            reader.visit(statement)
        args = fn.args if fn else None
        parameters = ([a.arg for a in args.posonlyargs + args.args] + (["*" + args.vararg.arg] if args.vararg else []) + [a.arg for a in args.kwonlyargs] + (["**" + args.kwarg.arg] if args.kwarg else [])) if args else []
        decorators = [{"expression": expr(d), "basis": "decorator syntax; effect unverified", **location(d)} for d in fn.decorator_list] if fn else []
        records.append({"name": function_name, "language": "Python", "scopeKind": scope_kind, "sourceLinkable": function_name in linkable,
                        "exported": False, "async": isinstance(fn, ast.AsyncFunctionDef), "generator": reader.yields > 0,
                        "parameters": parameters, "calls": reader.calls, "returns": reader.returns,
                        "documentation": ast.get_docstring(fn) if fn else ast.get_docstring(tree),
                        "steps": reader.steps,
                        "fieldAccesses": reader.field_accesses, "sql": reader.sql,
                        "conditions": reader.conditions, "loops": reader.loops, "throws": reader.throws,
                        "line": fn.lineno if fn else 1, "column": fn.col_offset + 1 if fn else 1, "endLine": fn.end_lineno if fn else len(source.splitlines()),
                        "summary": f"{function_name} declares {len(parameters)} parameters, {len(reader.calls)} call sites and {reader.loops} loop constructs. Paths and branches may never run.",
                        "io": reader.io, "loopPaths": reader.loop_paths, "reuseCues": reader.cues, "decorators": decorators,
                        "transformations": reader.transformations, "comprehensions": reader.comprehensions, "facts": reader.facts})
    return {"status": "parsed", "reason": "Parsed Python source syntax using isolated standard-library AST; target code was not executed.", "functions": records}


if __name__ == '__main__':
    inputs = json.load(sys.stdin)
    outputs = []
    for item in inputs:
        try:
            outputs.append(analyze(item['source']))
        except (RecursionError, MemoryError, ValueError) as error:
            outputs.append({"status": "analysis-limit", "reason": "Python syntax analysis limit: " + type(error).__name__, "functions": []})
    json.dump(outputs, sys.stdout)
