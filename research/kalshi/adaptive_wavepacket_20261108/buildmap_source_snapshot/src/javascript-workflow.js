// Bounded syntax adapter for the same calculation review used by Python.
// Never imports a mapped module or evaluates its expressions.
export function javascriptWorkflow(ast, bindings, source, fn, definitions, describe = n=>'the written expression') {
  const at = n => ({ line: n.loc.start.line, column: n.loc.start.column + 1 });
  const raw = n => { if (!n) return 'no explicit value'; const text = source.slice(n.start, n.end); return text.length > 240 ? text.slice(0,237)+'...' : text; };
  const literal = n => n?.type === 'Literal' && typeof n.value === 'string' ? n.value : null;
  const ref = n => n?.type === 'Identifier' ? n.name : n?.type === 'MemberExpression' && !n.computed ? `${ref(n.object)}.${n.property.name}` : '';
  const imports = new Map(), constants = new Map();
  for (const n of ast.body) if (n.type === 'ImportDeclaration') for (const s of n.specifiers) {
    if (bindings.get(s.local.name) === 1) imports.set(s.local.name, { module: n.source.value, symbol: s.type === 'ImportSpecifier' ? s.imported.name : null, ...at(n) });
  }
  const value = n => literal(n) ?? (n?.type === 'Identifier' ? constants.get(n.name) ?? null : null);
  const operand = n => !n ? { kind:'unknown',text:'unknown' } : n.type==='Identifier' ? {kind:'name',name:n.name}
    : n.type==='Literal' ? {kind:'literal',value:n.value} : n.type==='CallExpression' ? {kind:'call',target:ref(n.callee),arguments:n.arguments.map(operand)}
    : {kind:'unknown',text:raw(n)};
  const result = { io: [], transformations: [], loopPaths: [], comprehensions: [], facts: [], reuseCues: [], steps: [] };
  const calls = new Map();
  function walk(n, axes = [], guards = [], resultTargets = []) {
    if (!n?.type || ['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression','ClassDeclaration','ClassExpression'].includes(n.type) && n !== fn) return;
    if (n.type === 'VariableDeclarator') {
      if (n.id.type === 'Identifier' && bindings.get(n.id.name) === 1 && literal(n.init) !== null) constants.set(n.id.name, literal(n.init));
      const summary = raw(n), targets = [raw(n.id)];
      result.transformations.push({ summary, kind: n.type, ...at(n) });
      result.steps.push({ kind: n.init ? 'assign' : 'declare', targets, expression: raw(n.init), explanation:n.init?`Builds ${describe(n.init)}. Source syntax does not establish runtime values.`:null, guards, ...at(n) });
      walk(n.init, axes, guards, targets); return;
    }
    if (n.type === 'ReturnStatement') result.steps.push({ kind: 'return', expression: raw(n.argument), guards, ...at(n) });
    if (n.type === 'IfStatement') {
      walk(n.test, axes, guards);
      const guard = { test: raw(n.test), ...at(n) };
      walk(n.consequent, axes, [...guards, { ...guard, branch: 'then' }]);
      walk(n.alternate, axes, [...guards, { ...guard, branch: 'else' }]); return;
    }
    if (['ForStatement','ForInStatement','ForOfStatement','WhileStatement','DoWhileStatement'].includes(n.type)) {
      const axis = { target: raw(n.left || n.init), iterable: raw(n.right || n.test), literalRangeCount: null, ...at(n) };
      const next = [...axes, axis];
      if (next.length >= 2) result.loopPaths.push(next);
      for (const key of ['init','left','right','test','update']) walk(n[key], axes, guards);
      walk(n.body, next, guards); return;
    }
    if (['CallExpression','NewExpression'].includes(n.type)) {
      const target = ref(n.callee) || 'computed callable', parts = target.split('.'), imported = imports.get(parts[0]);
      const call = { ...at(n), positionalArguments: n.arguments.map(raw), keywordArguments: [], resultTargets, guards, loopDepth: axes.length };
      if (parts.length === 1 && definitions.has(target)) call.bindingReference = { kind: 'local-function', targetName: target };
      else if (imported && imported.module.startsWith('.')) {
        const targetName = imported.symbol && parts.length === 1 ? imported.symbol : !imported.symbol && parts.length === 2 ? parts[1] : null;
        if (targetName) call.bindingReference = { kind: 'javascript-import', module: imported.module, targetName, ...at(n) };
      }
      calls.set(`${n.loc.start.line}:${n.loc.start.column + 1}`, call);
      const member = parts.at(-1), fs = imported && ['fs','node:fs','fs/promises','node:fs/promises'].includes(imported.module);
      const operation = (imported?.symbol || member).match(/^(readFile|readFileSync|createReadStream)$/) ? 'read'
        : (imported?.symbol || member).match(/^(writeFile|writeFileSync|appendFile|appendFileSync|createWriteStream)$/) ? 'write' : null;
      if (fs && operation && n.arguments[0]) {
        const literalPath=value(n.arguments[0]);
        const io = { pathExpression: literalPath ?? raw(n.arguments[0]), pathKind:literalPath===null?'symbolic':'literal',operand:operand(n.arguments[0]),operation, call: target, basis: 'node-fs-path-syntax; actual path unobserved', loopDepth: axes.length, guards, resultTargets, ...at(n) };
        result.io.push(io);
        result.facts.push({ kind: 'persistence', operation: operation === 'read' ? 'load' : 'save', literalPath, pathExpression: io.pathExpression, expression: raw(n), loopDepth: axes.length, guards, ...at(n) });
      }
      if (/cache|memo|lazy|checkpoint|reuse|indexed/i.test(target)) result.reuseCues.push({ expression: raw(n), basis: 'name-only; behavior unverified', ...at(n) });
      if (target === 'Array.from' || fs && /readFile/.test(imported.symbol || member)) result.facts.push({ kind: 'whole-materialization', expression: raw(n), loopDepth: axes.length, guards, ...at(n) });
    }
    for (const [key, child] of Object.entries(n)) {
      if (['loc','start','end'].includes(key)) continue;
      if (Array.isArray(child)) child.forEach(c => walk(c, axes, guards)); else if (child?.type) walk(child, axes, guards);
    }
  }
  walk(fn.body);
  return { ...result, calls };
}
