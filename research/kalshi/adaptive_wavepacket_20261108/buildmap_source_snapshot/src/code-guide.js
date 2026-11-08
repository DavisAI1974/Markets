import { javascriptWorkflow } from './javascript-workflow.js';
// Deterministic explanations of parsed syntax. No target code is executed;
// names, argument counts and return expressions do not establish runtime types.
const isFunction = n => ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(n?.type);
const loc = n => ({ line: n.loc.start.line, column: n.loc.start.column + 1 });
const literalKey = n => n?.type === 'Identifier' ? n.name : n?.type === 'Literal' ? String(n.value) : '[computed key]';

function reference(n) {
  if (n?.type === 'Identifier') return n.name;
  if (n?.type === 'ThisExpression') return 'this';
  if (n?.type === 'MemberExpression') {
    const base = reference(n.object);
    const key = n.computed ? (n.property.type === 'Literal' ? `[${n.property.raw ?? String(n.property.value)}]` : '[computed key]') : `.${n.property.name}`;
    return base ? base + key : null;
  }
  return null;
}

function expression(n, depth = 0) {
  if (!n) return 'no explicit value';
  if (depth > 4) return 'a nested expression (not expanded further)';
  const name = reference(n);
  if (name) return `the value at ${name}`;
  if (n.type === 'Literal') return n.regex ? 'a regular-expression literal' : `a ${n.value === null ? 'null' : typeof n.value} literal`;
  if (n.type === 'BinaryExpression' || n.type === 'LogicalExpression') return `an expression using ${n.operator} on ${expression(n.left, depth + 1)} and ${expression(n.right, depth + 1)}`;
  if (n.type === 'CallExpression') return `the result of calling ${reference(n.callee) || 'a computed callable'}`;
  if (n.type === 'NewExpression') return `a value constructed with ${reference(n.callee) || 'a computed constructor'}`;
  if (n.type === 'ObjectExpression') return 'an object';
  if (n.type === 'ArrayExpression') return 'an array';
  if (n.type === 'TemplateLiteral') return 'text assembled by a template';
  if (n.type === 'ConditionalExpression') return 'a value chosen by a condition';
  if (n.type === 'AwaitExpression') return `the awaited result of ${expression(n.argument, depth + 1)}`;
  if (n.type === 'SpreadElement') return `spread values from ${expression(n.argument, depth + 1)}`;
  if (isFunction(n)) return 'a function';
  return `${n.type} syntax (not interpreted further)`;
}

function parameter(n) {
  if (n.type === 'Identifier') return n.name;
  if (n.type === 'AssignmentPattern') return `${parameter(n.left)} (default: ${expression(n.right)})`;
  if (n.type === 'RestElement') return `remaining arguments in ${parameter(n.argument)}`;
  if (n.type === 'ObjectPattern') return `object fields: ${n.properties.map(p => p.type === 'RestElement' ? parameter(p) : p.computed ? '[computed key]' : literalKey(p.key)).join(', ')}`;
  if (n.type === 'ArrayPattern') return `array positions: ${n.elements.map(p => p ? parameter(p) : 'skipped position').join(', ')}`;
  return `${n.type} parameter pattern`;
}

export function explainFunctions(ast, bindingCounts, source = '') {
  const definitions = [];
  const exportedNames = new Set();
  for (const top of ast.body) {
    if (top.type === 'ExportDefaultDeclaration' && top.declaration.type === 'Identifier') exportedNames.add(top.declaration.name);
    if (top.type === 'ExportNamedDeclaration' && !top.source) top.specifiers.forEach(s => exportedNames.add(s.local.name));
    const statement = ['ExportNamedDeclaration', 'ExportDefaultDeclaration'].includes(top.type) ? top.declaration : top;
    const exported = top.type.startsWith('Export');
    if (isFunction(statement)) definitions.push({ name: statement.id?.name || 'default', fn: statement, exported });
    if (statement?.type === 'VariableDeclaration') for (const d of statement.declarations) {
      if (d.id.type === 'Identifier' && isFunction(d.init)) definitions.push({ name: d.id.name, fn: d.init, exported });
    }
  }
  const byName = new Map(definitions.filter(d => bindingCounts.get(d.name) === 1).map(d => [d.name, d.fn]));
  return definitions.map(({ name, fn, exported }) => {
    const calls = [], returns = []; let conditions = 0, loops = 0, throws = 0;
    const stack = [fn.body];
    const returnDescription = (value, at) => ({ summary: expression(value), kind: value?.type || 'empty', ...loc(at),
      ...(value?.type === 'ObjectExpression' ? { fields: value.properties.map(p => p.type === 'SpreadElement'
        ? { name: '[spread]', summary: expression(p.argument) } : { name: p.computed ? '[computed key]' : literalKey(p.key), summary: expression(p.value) }) } : {}) });
    if (fn.body.type !== 'BlockStatement') returns.push(returnDescription(fn.body, fn.body));
    while (stack.length) {
      const n = stack.pop();
      if (!n?.type || isFunction(n)) continue; // Nested bodies belong to other functions.
      if (n.type === 'CallExpression' || n.type === 'NewExpression') {
        const target = reference(n.callee) || 'computed callable';
        const local = n.callee.type === 'Identifier' && byName.get(target);
        calls.push({ target, kind: n.type === 'NewExpression' ? 'construction' : 'call', argumentCount: n.arguments.length,
          arguments: n.arguments.map(a => expression(a)),
          resolution: local ? 'same-file-function' : 'unresolved-source-reference', ...(local ? { targetLocation: loc(local) } : {}), ...loc(n) });
      }
      if (n.type === 'ReturnStatement') returns.push(returnDescription(n.argument, n));
      if (['IfStatement', 'ConditionalExpression', 'SwitchStatement'].includes(n.type)) conditions++;
      if (['ForStatement', 'ForInStatement', 'ForOfStatement', 'WhileStatement', 'DoWhileStatement'].includes(n.type)) loops++;
      if (n.type === 'ThrowStatement') throws++;
      for (const value of Object.values(n)) {
        if (Array.isArray(value)) { for (const child of value) if (child?.type) stack.push(child); }
        else if (value?.type) stack.push(value);
      }
    }
    const workflow = javascriptWorkflow(ast, bindingCounts, source, fn, byName, expression);
    const comment=source.slice(Math.max(0,fn.start-4000),fn.start).match(/\/\*\*((?:(?!\*\/)[\s\S])*)\*\/\s*(?:export\s+(?:default\s+)?)?(?:(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*)?$/);
    const documentation=comment?comment[1].split('\n').map(line=>line.replace(/^\s*\*\s?/, '').trimEnd()).join('\n').trim():null;
    for (const c of calls) Object.assign(c, workflow.calls.get(`${c.line}:${c.column}`) || {});
    const order = (a,b) => a.line - b.line || a.column - b.column;
    return { name, exported: exported || exportedNames.has(name), async: Boolean(fn.async), generator: Boolean(fn.generator),
      language: 'JavaScript', scopeKind: 'function', sourceLinkable: byName.has(name), documentation,
      io: workflow.io, transformations: workflow.transformations, loopPaths: workflow.loopPaths, comprehensions: [],
      facts: workflow.facts, reuseCues: workflow.reuseCues, steps: workflow.steps, decorators: [],
      parameters: fn.params.map(parameter), calls: calls.sort(order), returns: returns.sort(order), conditions, loops, throws,
      parameterNames: fn.params.map(p => p.type === 'Identifier' ? p.name : p.type === 'AssignmentPattern' && p.left.type === 'Identifier' ? p.left.name : null),
      ...loc(fn), endLine: fn.loc.end.line,
      summary: `${name} declares ${fn.params.length} parameter${fn.params.length === 1 ? '' : 's'} and contains ${calls.length} call/construction site${calls.length === 1 ? '' : 's'} and ${returns.length} return site${returns.length === 1 ? '' : 's'}.` };
  });
}

export const CODE_GUIDE_LIMITS = [
  'Source syntax only: listed calls and return paths may never execute. Source order is not runtime order or observed data flow.',
  'Catalog covers top-level JavaScript functions and identifier-assigned function expressions/arrows. Nested callbacks, class/object methods and functions inside blocks are not catalogued.',
  'Same-file call targets are matched only for uniquely bound bare names; other references stay unresolved. Arguments, types, values, side effects and business meaning are not inferred.',
  'Return descriptions identify syntax, not actual outputs. Imported call targets, dynamic dispatch, cross-file function tracing, TypeScript and other languages are not interpreted.',
  'Call sites are counted only in the function body; default-parameter expressions are summarized separately. Spread arguments do not establish the runtime argument count.'
];
